# routers/probe.py
import asyncio
import ipaddress
import socket
import time
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, status

from schemas.probe import PortResult, ProbeRequest, ProbeResponse

router = APIRouter()

COMMON_SERVICES: dict[int, str] = {
    21: "FTP",
    22: "SSH",
    23: "Telnet",
    25: "SMTP",
    53: "DNS",
    80: "HTTP",
    110: "POP3",
    143: "IMAP",
    443: "HTTPS",
    465: "SMTPS",
    587: "SMTP Submission",
    993: "IMAPS",
    995: "POP3S",
    3306: "MySQL",
    3389: "RDP",
    5432: "PostgreSQL",
    6379: "Redis",
    8080: "HTTP-Proxy",
    8443: "HTTPS-Alt",
    27017: "MongoDB",
}


def is_restricted_ip(ip_str: str) -> bool:
    """
    SSRF Guard: Validates that the target IP is publicly routable and not
    part of private, loopback, link-local, carrier NAT, or cloud metadata ranges.
    """
    try:
        ip = ipaddress.ip_address(ip_str)

        # Standard IPv4 & IPv6 restricted checks
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            return True

        # Carrier-Grade NAT (RFC 6598: 100.64.0.0/10)
        if isinstance(ip, ipaddress.IPv4Address):
            if ip in ipaddress.IPv4Network("100.64.0.0/10"):
                return True

        return False
    except ValueError:
        return True


async def probe_single_port(ip: str, port: int, timeout: float = 2.0) -> PortResult:
    """
    Attempts non-blocking TCP connection, measures round-trip time,
    and grabs initial service banner if emitted.
    """
    start_time = time.perf_counter()
    service = COMMON_SERVICES.get(port, "Custom")

    try:
        connect_coro = asyncio.open_connection(ip, port)
        reader, writer = await asyncio.wait_for(connect_coro, timeout=timeout)
    except TimeoutError:
        latency_ms = int((time.perf_counter() - start_time) * 1000)
        return PortResult(
            port=port,
            status="filtered",
            service=service,
            latencyMs=latency_ms,
            banner=None,
        )
    except (ConnectionRefusedError, OSError):
        latency_ms = int((time.perf_counter() - start_time) * 1000)
        return PortResult(
            port=port,
            status="closed",
            service=service,
            latencyMs=latency_ms,
            banner=None,
        )

    # Port is open
    latency_ms = int((time.perf_counter() - start_time) * 1000)
    banner: str | None = None

    try:
        # Send gentle protocol trigger
        if port in (80, 8080):
            writer.write(b"HEAD / HTTP/1.0\r\nHost: probe\r\n\r\n")
        elif port in (21, 25, 110, 143):
            # Daemons automatically emit welcome banners upon handshake
            pass
        else:
            writer.write(b"\r\n")
        await writer.drain()

        # Capture banner up to 512 bytes with short read deadline
        raw_banner = await asyncio.wait_for(reader.read(512), timeout=0.6)
        if raw_banner:
            decoded = raw_banner.decode("utf-8", errors="replace").strip()
            # Retain only printable characters
            cleaned = "".join(ch for ch in decoded if ch.isprintable() or ch in " \t")
            banner = cleaned[:250] if cleaned else None
    except (TimeoutError, Exception):
        banner = None
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass

    return PortResult(
        port=port,
        status="open",
        service=service,
        latencyMs=latency_ms,
        banner=banner,
    )


@router.post("", response_model=ProbeResponse)
async def run_network_probe(req: ProbeRequest):
    loop = asyncio.get_running_loop()
    target_clean = req.target.strip()

    # 1. Resolve host to IP
    try:
        ipaddress.ip_address(target_clean)
        resolved_ip = target_clean
    except ValueError:
        try:
            addrinfo = await loop.getaddrinfo(
                target_clean, None, family=socket.AF_UNSPEC, type=socket.SOCK_STREAM
            )
            if not addrinfo:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="DNS lookup returned no records for target host.",
                )
            resolved_ip = addrinfo[0][4][0]
        except socket.gaierror:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="DNS lookup failed for target host.",
            )

    # 2. Enforce SSRF & Private Network Block
    if is_restricted_ip(resolved_ip):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access to private, loopback, or cloud-internal addresses is restricted.",
        )

    # 3. Parallel port scans
    tasks = [probe_single_port(resolved_ip, p) for p in req.ports]
    results = await asyncio.gather(*tasks)
    results.sort(key=lambda x: x.port)

    return ProbeResponse(
        target=target_clean,
        resolvedIp=resolved_ip,
        timestamp=datetime.now(UTC).isoformat(),
        results=results,
    )
