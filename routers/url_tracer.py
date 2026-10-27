# routers/url_tracer.py
import asyncio
import ipaddress
import re
import socket
import time
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

import httpx
from fastapi import APIRouter, HTTPException, status

from schemas.url_tracer import HopItem, TraceRequest, TraceResponse

router = APIRouter()

MAX_HOPS = 12
CONNECT_TIMEOUT = 4.0
TOTAL_TIMEOUT = 18.0

USER_AGENTS = {
    "desktop": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "googlebot": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
    "slackbot": "Slackbot-LinkExpanding 1.0 (+https://api.slack.com/robots)",
    "curl": "curl/8.5.0",
}

TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "fbclid",
    "gclid",
    "gclsrc",
    "dclid",
    "msclkid",
    "mc_eid",
    "yclid",
    "_hsenc",
    "_hsmi",
    "igshid",
    "s_kwcid",
    "si",
    "ref",
    "ref_src",
}


def is_restricted_ip(ip_str: str) -> bool:
    """SSRF Guard against private, loopback, multicast, or cloud metadata IPs."""
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
            return True
        if isinstance(ip, ipaddress.IPv4Address) and ip in ipaddress.IPv4Network(
            "100.64.0.0/10"
        ):
            return True
        return False
    except ValueError:
        return True


async def resolve_host_ip(hostname: str) -> str:
    """Asynchronously resolves a hostname and verifies it is not an SSRF threat."""
    try:
        ipaddress.ip_address(hostname)
        ip = hostname
    except ValueError:
        loop = asyncio.get_running_loop()
        try:
            addrinfo = await loop.getaddrinfo(
                hostname, None, family=socket.AF_UNSPEC, type=socket.SOCK_STREAM
            )
            if not addrinfo:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Could not resolve hostname: {hostname}",
                )
            ip = addrinfo[0][4][0]
        except socket.gaierror:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"DNS resolution failed for hostname: {hostname}",
            )

    if is_restricted_ip(ip):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Target IP {ip} is in a restricted or private range.",
        )
    return ip


def defang_url(url: str) -> str:
    """Defangs a URL for safe sharing (hxxps[://]domain[.]com)."""
    defanged = re.sub(r"^http://", "hxxp://", url, flags=re.IGNORECASE)
    defanged = re.sub(r"^https://", "hxxps://", defanged, flags=re.IGNORECASE)
    defanged = defanged.replace("://", "[://]")
    parts = defanged.split("/", 3)
    if len(parts) >= 3:
        parts[2] = parts[2].replace(".", "[.]")
        return "/".join(parts)
    return defanged.replace(".", "[.]")


def strip_tracking_params(url: str) -> tuple[str, list[str]]:
    """Strips invasive analytics and social media tracking query parameters."""
    parsed = urlsplit(url)
    if not parsed.query:
        return url, []

    pairs = parse_qsl(parsed.query, keep_blank_values=True)
    kept_pairs = []
    stripped_keys = []

    for k, v in pairs:
        if k.lower() in TRACKING_PARAMS or k.lower().startswith("utm_"):
            stripped_keys.append(k)
        else:
            kept_pairs.append((k, v))

    clean_query = urlencode(kept_pairs)
    clean_url = urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path, clean_query, parsed.fragment)
    )
    return clean_url, stripped_keys


@router.post("", response_model=TraceResponse)
async def trace_url_redirects(req: TraceRequest):
    raw_url = req.url.strip()
    if not raw_url.startswith(("http://", "https://")):
        raw_url = "https://" + raw_url

    selected_ua = USER_AGENTS.get(req.userAgentProfile, USER_AGENTS["desktop"])
    current_url = raw_url
    hops: list[HopItem] = []
    page_title: str | None = None
    overall_start = time.perf_counter()

    async with httpx.AsyncClient(
        follow_redirects=False,
        verify=False,  # Still observe invalid/self-signed cert targets
        timeout=httpx.Timeout(CONNECT_TIMEOUT, read=CONNECT_TIMEOUT),
        headers={"User-Agent": selected_ua, "Accept": "*/*"},
    ) as client:
        for hop_index in range(1, MAX_HOPS + 1):
            parsed = urlsplit(current_url)
            if not parsed.hostname:
                raise HTTPException(
                    status_code=400, detail="Invalid target URL structure."
                )

            # Strict SSRF check before requesting each hop
            resolved_ip = await resolve_host_ip(parsed.hostname)

            hop_start = time.perf_counter()
            try:
                # Issue GET request with limited payload stream to extract title if HTML
                response = await client.get(current_url)
                latency = int((time.perf_counter() - hop_start) * 1000)
            except (httpx.RequestError, httpx.TimeoutException) as exc:
                latency = int((time.perf_counter() - hop_start) * 1000)
                hops.append(
                    HopItem(
                        hop=hop_index,
                        url=current_url,
                        statusCode=0,
                        statusText=f"Connection Error: {exc.__class__.__name__}",
                        latencyMs=latency,
                        resolvedIp=resolved_ip,
                    )
                )
                break

            status_code = response.status_code
            status_text = response.reason_phrase or str(status_code)
            server_header = response.headers.get("server")
            content_type = response.headers.get("content-type")
            location_header = response.headers.get("location")

            # Extract HTML page title if available on final/intermediate page
            if content_type and "text/html" in content_type:
                content_sample = response.text[:8192]
                match = re.search(
                    r"<title[^>]*>(.*?)</title>",
                    content_sample,
                    re.IGNORECASE | re.DOTALL,
                )
                match = re.search(
                    r"<title[^>]*>(.*?)</title>",
                    content_sample,
                    re.IGNORECASE | re.DOTALL,
                )
                if match:
                    cleaned_title = re.sub(r"\s+", " ", match.group(1)).strip()
                    if cleaned_title:
                        page_title = cleaned_title[:180]

            resolved_location = None
            if location_header:
                resolved_location = urljoin(current_url, location_header)

            hops.append(
                HopItem(
                    hop=hop_index,
                    url=current_url,
                    statusCode=status_code,
                    statusText=status_text,
                    latencyMs=latency,
                    server=server_header,
                    contentType=content_type.split(";")[0] if content_type else None,
                    location=resolved_location,
                    resolvedIp=resolved_ip,
                )
            )

            # Check if status code signals redirection
            if status_code in (301, 302, 303, 307, 308) and resolved_location:
                current_url = resolved_location
            else:
                # Terminal destination reached
                break

    total_duration = int((time.perf_counter() - overall_start) * 1000)
    final_url = hops[-1].url if hops else raw_url
    clean_url, stripped = strip_tracking_params(final_url)
    defanged = defang_url(final_url)

    return TraceResponse(
        inputUrl=raw_url,
        finalUrl=final_url,
        cleanUrl=clean_url,
        defangedUrl=defanged,
        pageTitle=page_title,
        totalDurationMs=total_duration,
        totalHops=len(hops),
        strippedParams=stripped,
        hops=hops,
    )
