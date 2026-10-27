# routers/api_runner.py
import asyncio
import ipaddress
import socket
import time
from urllib.parse import urlsplit

import httpx
from fastapi import APIRouter, HTTPException, status
from schemas.api_runner import (
    ApiRunRequest,
    ApiRunResponse,
    HeaderItem,
    TimingBreakdown,
)

router = APIRouter()

MAX_BODY_BYTES = 1024 * 1024 * 1.5  # 1.5 MB memory cap


def is_restricted_ip(ip_str: str) -> bool:
    """SSRF Guard against private, loopback, link-local, carrier NAT, and cloud metadata IPs."""
    try:
        ip = ipaddress.ip_address(ip_str)
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            if isinstance(ip, ipaddress.IPv4Address) and ip in ipaddress.IPv4Network(
                "100.64.0.0/10"
            ):
                return True
        return False
    except ValueError:
        return True


@router.post("", response_model=ApiRunResponse)
async def execute_stateless_http_request(req: ApiRunRequest):
    target_url = req.url.strip()
    if not target_url.startswith(("http://", "https://")):
        target_url = "https://" + target_url

    parsed = urlsplit(target_url)
    if not parsed.hostname:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid URL structure.",
        )

    # 1. DNS Resolution & SSRF Guard with timing measurement
    loop = asyncio.get_running_loop()
    dns_start = time.perf_counter()
    try:
        addrinfo = await loop.getaddrinfo(
            parsed.hostname, None, family=socket.AF_UNSPEC, type=socket.SOCK_STREAM
        )
        dns_duration = int((time.perf_counter() - dns_start) * 1000)
        if not addrinfo:
            raise HTTPException(
                status_code=400, detail="Could not resolve target hostname."
            )
        resolved_ip = addrinfo[0][4][0]
    except socket.gaierror:
        raise HTTPException(
            status_code=400, detail=f"DNS lookup failed for {parsed.hostname}"
        )
        raise HTTPException(
            status_code=400, detail=f"DNS lookup failed for {parsed.hostname}"
        )
        resolved_ip = addrinfo[0][4][0]
    except socket.gaierror:
        raise HTTPException(
            status_code=400, detail=f"DNS lookup failed for {parsed.hostname}"
        )
        raise HTTPException(status_code=400, detail=f"DNS lookup failed for {parsed.hostname}")

    if is_restricted_ip(resolved_ip):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Target IP {resolved_ip} is in a restricted or private range.",
        )

    # 2. Build Request Headers
    header_dict: dict[str, str] = {}
    for item in req.headers:
        k = item.key.strip()
        if k:
            header_dict[k] = item.value.strip()

    if "user-agent" not in {k.lower() for k in header_dict}:
        header_dict["User-Agent"] = "0w-Stateless-HttpRunner/1.0"

    overall_start = time.perf_counter()
    is_truncated = False

    # 3. Non-blocking HTTP Execution
    try:
        async with httpx.AsyncClient(
            verify=False,  # Allow inspecting development/staging SSL endpoints
            follow_redirects=True,
            timeout=httpx.Timeout(req.timeoutSeconds),
        ) as client:
            request_obj = client.build_request(
                method=req.method,
                url=target_url,
                headers=header_dict,
                content=req.body.encode("utf-8") if req.body else None,
            )

            ttfb_start = time.perf_counter()
            response = await client.send(request_obj, stream=True)
            ttfb_duration = int((time.perf_counter() - ttfb_start) * 1000)

            # Stream body with buffer limit
            download_start = time.perf_counter()
            chunks: list[bytes] = []
            total_bytes = 0

            async for chunk in response.aiter_bytes(chunk_size=8192):
                chunks.append(chunk)
                total_bytes += len(chunk)
                if total_bytes > MAX_BODY_BYTES:
                    is_truncated = True
                    break

            await response.aclose()
            download_duration = int((time.perf_counter() - download_start) * 1000)

    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Upstream request timed out.")
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Connection failed: {exc.__class__.__name__}",
        )

    total_duration = int((time.perf_counter() - overall_start) * 1000)
    raw_payload = b"".join(chunks)

    # Response headers
    response_headers = [
        HeaderItem(key=k, value=v) for k, v in response.headers.multi_items()
    ]

    # Content Type & JSON detection
    content_type = response.headers.get("content-type", "")
    is_json = "application/json" in content_type.lower()

    try:
        decoded_body = raw_payload.decode("utf-8")
    except UnicodeDecodeError:
        decoded_body = f"[Binary data: {len(raw_payload)} bytes]"

    return ApiRunResponse(
        statusCode=response.status_code,
        statusText=response.reason_phrase or str(response.status_code),
        timing=TimingBreakdown(
            dnsMs=dns_duration,
            ttfbMs=ttfb_duration,
            downloadMs=download_duration,
            totalMs=total_duration,
        ),
        headers=response_headers,
        body=decoded_body,
        isJson=is_json,
        isTruncated=is_truncated,
        sizeBytes=total_bytes,
    )
