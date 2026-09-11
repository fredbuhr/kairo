"""Bounded public HTML reads: connect to the validated IP, preserve HTTP Host and TLS SNI."""
import asyncio
import ipaddress
import socket
from urllib.parse import urljoin

import httpx

MAX_BYTES = 2_500_000
MAX_SECONDS = 30
REDIRECTS = {301, 302, 303, 307, 308}


def _public(address: str) -> bool:
    ip = ipaddress.ip_address(address)
    if not ip.is_global or ip.is_multicast or ip.is_unspecified:
        return False
    if isinstance(ip, ipaddress.IPv6Address):
        # Reject scoped/transition addresses, including NAT64 representations of private IPv4.
        if ip.ipv4_mapped or ip.sixtofour or ip.teredo or ip in ipaddress.ip_network("64:ff9b::/96"):
            return False
    return True


async def resolve_public(value: str) -> tuple[httpx.URL, str] | None:
    try:
        if len(value) > 2048 or any(ord(c) < 33 for c in value) or "\\" in value:
            return None
        url = httpx.URL(value)
        if url.scheme not in {"http", "https"} or not url.host or url.userinfo:
            return None
        if url.port not in {None, 80, 443} or "%" in url.host:
            return None
        hostname = url.host.rstrip(".").lower()
        if hostname == "localhost" or hostname.endswith((".local", ".localhost", ".internal")):
            return None
        try:
            ipaddress.ip_address(hostname)
            addresses = [hostname]
        except ValueError:
            async with asyncio.timeout(5):
                infos = await asyncio.get_running_loop().getaddrinfo(
                    hostname, url.port or (443 if url.scheme == "https" else 80),
                    type=socket.SOCK_STREAM,
                )
            addresses = list(dict.fromkeys(str(info[4][0]) for info in infos))
        if not addresses or not all(_public(address) for address in addresses):
            return None
        return url, addresses[0]
    except (ValueError, httpx.InvalidURL, OSError, TimeoutError):
        return None


async def fetch_public_html(value: str) -> httpx.Response | None:
    current = value
    async with asyncio.timeout(MAX_SECONDS):
        for _ in range(4):
            target = await resolve_public(current)
            if target is None:
                return None
            url, address = target
            # A fresh client per hop prevents cookies/credentials and pooled TLS connections from
            # crossing origins that share an IP. Environment proxies cannot re-resolve the name.
            async with httpx.AsyncClient(
                trust_env=False, follow_redirects=False,
                timeout=httpx.Timeout(10, connect=5),
                limits=httpx.Limits(max_connections=1, max_keepalive_connections=0),
            ) as client:
                headers = {
                    "Host": url.netloc.decode("ascii"),
                    "User-Agent": "Nevolium-Research/0.2",
                    "Accept": "text/html,application/xhtml+xml",
                    "Accept-Encoding": "identity",
                }
                async with client.stream(
                    "GET", url.copy_with(host=address), headers=headers,
                    extensions={"sni_hostname": url.host},
                ) as response:
                    if response.status_code in REDIRECTS:
                        location = response.headers.get("location")
                        if not location:
                            return None
                        current = urljoin(str(url), location)
                        continue
                    # Refuse compression before decoding, so decompression bombs never allocate.
                    if response.headers.get("content-encoding", "identity").lower() != "identity":
                        return None
                    if "html" not in response.headers.get("content-type", "").lower():
                        return None
                    length = response.headers.get("content-length")
                    if length is not None and (not length.isdecimal() or int(length) > MAX_BYTES):
                        return None
                    body = bytearray()
                    async for chunk in response.aiter_raw():
                        if len(body) + len(chunk) > MAX_BYTES:
                            return None
                        body.extend(chunk)
                    return httpx.Response(
                        response.status_code, headers=response.headers, content=bytes(body),
                        request=httpx.Request("GET", url),
                    )
    return None
