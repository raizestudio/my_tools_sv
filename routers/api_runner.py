import asyncio
import ipaddress
import re
import socket
import time
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx
from fastapi import APIRouter, HTTPException, status

from schemas.api_runner import (
    ApiRunRequest,
    ApiRunResponse,
    HeaderItem,
    TimingBreakdown,
)

router = APIRouter()

MAX_BODY_BYTES = 1536 * 1024
DEFAULT_USER_AGENT = "0w-Stateless-HttpRunner/1.0"


def is_restricted_ip(ip_str: str) -> bool:
    """Return whether an address is not globally routable."""
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return True

    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped

    return not ip.is_global


async def validate_target_url(target_url: str) -> tuple[str, int]:
    """Normalize a URL and reject targets resolving to non-public IP addresses."""
    target_url = target_url.strip()
    if not target_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A target URL is required.",
        )

    scheme_match = re.match(r"^[A-Za-z][A-Za-z0-9+.-]*://", target_url)
    if scheme_match:
        if target_url[: scheme_match.end() - 3].lower() not in {"http", "https"}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only HTTP and HTTPS URLs are supported.",
            )
    else:
        target_url = f"https://{target_url}"

    try:
        parsed = urlsplit(target_url)
        hostname = parsed.hostname
        port = parsed.port  # Accessing port validates its syntax and range.
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid URL structure.",
        ) from exc

    if (
        not hostname
        or parsed.scheme.lower() not in {"http", "https"}
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid URL structure.",
        )

    target_url = urlunsplit(parsed._replace(scheme=parsed.scheme.lower()))
    dns_start = time.perf_counter()
    try:
        addrinfo = await asyncio.get_running_loop().getaddrinfo(
            hostname,
            port,
            family=socket.AF_UNSPEC,
            type=socket.SOCK_STREAM,
        )
    except socket.gaierror as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"DNS lookup failed for {hostname}.",
        ) from exc

    dns_duration = int((time.perf_counter() - dns_start) * 1000)
    if not addrinfo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not resolve target hostname.",
        )

    resolved_ips = {str(entry[4][0]) for entry in addrinfo}
    restricted_ips = sorted(ip for ip in resolved_ips if is_restricted_ip(ip))
    if restricted_ips:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Target resolves to a restricted or private IP address: "
                f"{restricted_ips[0]}."
            ),
        )

    return target_url, dns_duration


@router.post("", response_model=ApiRunResponse)
async def execute_stateless_http_request(req: ApiRunRequest) -> ApiRunResponse:
    overall_start = time.perf_counter()
    target_url, dns_duration = await validate_target_url(req.url)

    headers: dict[str, str] = {}
    for item in req.headers:
        key = item.key.strip()
        if key:
            headers[key] = item.value.strip()
    if not any(key.lower() == "user-agent" for key in headers):
        headers["User-Agent"] = DEFAULT_USER_AGENT

    async def validate_redirect(response: httpx.Response) -> None:
        nonlocal dns_duration
        if response.is_redirect and (location := response.headers.get("location")):
            redirect_url = urljoin(str(response.request.url), location)
            _, redirect_dns_ms = await validate_target_url(redirect_url)
            dns_duration += redirect_dns_ms

    try:
        request = httpx.Request(
            method=req.method,
            url=target_url,
            headers=headers,
            content=req.body.encode("utf-8") if req.body else None,
        )
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=httpx.Timeout(req.timeoutSeconds),
            verify=True,
            trust_env=False,
            event_hooks={"response": [validate_redirect]},
        ) as client:
            ttfb_start = time.perf_counter()
            response = await client.send(request, stream=True)
            ttfb_duration = int((time.perf_counter() - ttfb_start) * 1000)

            download_start = time.perf_counter()
            chunks: list[bytes] = []
            total_bytes = 0
            is_truncated = False
            try:
                async for chunk in response.aiter_bytes(chunk_size=8192):
                    remaining = MAX_BODY_BYTES - total_bytes
                    if len(chunk) > remaining:
                        if remaining:
                            chunks.append(chunk[:remaining])
                            total_bytes += remaining
                        is_truncated = True
                        break
                    chunks.append(chunk)
                    total_bytes += len(chunk)
            finally:
                await response.aclose()
            download_duration = int((time.perf_counter() - download_start) * 1000)

    except httpx.TimeoutException as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Upstream request timed out.",
        ) from exc
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Connection failed: {exc.__class__.__name__}.",
        ) from exc

    total_duration = int((time.perf_counter() - overall_start) * 1000)
    raw_payload = b"".join(chunks)
    try:
        decoded_body = raw_payload.decode("utf-8")
    except UnicodeDecodeError:
        decoded_body = f"[Binary data: {len(raw_payload)} bytes]"

    content_type = response.headers.get("content-type", "")
    media_type = content_type.partition(";")[0].strip().lower()
    is_json = media_type == "application/json" or media_type.endswith("+json")

    return ApiRunResponse(
        statusCode=response.status_code,
        statusText=response.reason_phrase or str(response.status_code),
        timing=TimingBreakdown(
            dnsMs=dns_duration,
            ttfbMs=ttfb_duration,
            downloadMs=download_duration,
            totalMs=total_duration,
        ),
        headers=[
            HeaderItem(key=key, value=value)
            for key, value in response.headers.multi_items()
        ],
        body=decoded_body,
        isJson=is_json,
        isTruncated=is_truncated,
        sizeBytes=total_bytes,
    )
