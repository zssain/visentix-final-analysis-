"""SSRF defense — validates URLs before server-side fetch.

Blocks: private ranges (10/8, 172.16/12, 192.168/16, 127/8),
link-local (169.254/16), loopback (::1), and cloud metadata (169.254.169.254).
Only allows http/https schemes.
"""

import ipaddress
import socket
from urllib.parse import urlparse


class SSRFError(ValueError):
    """Raised when a URL targets a blocked network range."""


BLOCKED_HOSTNAMES = {"metadata.google.internal", "metadata.gce.internal"}

# Max response size: 10 MB
MAX_RESPONSE_BYTES = 10 * 1024 * 1024

# Fetch timeout
FETCH_TIMEOUT_SECONDS = 30


def validate_url(url: str) -> str:
    """Validate a URL for safe server-side fetching. Returns the URL if safe."""
    parsed = urlparse(url)

    # Scheme check
    if parsed.scheme not in ("http", "https"):
        raise SSRFError(f"Blocked scheme: {parsed.scheme}. Only http/https allowed.")

    hostname = parsed.hostname
    if not hostname:
        raise SSRFError("No hostname in URL.")

    # Block known metadata hostnames
    if hostname.lower() in BLOCKED_HOSTNAMES:
        raise SSRFError(f"Blocked hostname: {hostname}")

    # Resolve hostname to IP(s) and check each
    try:
        addrinfo = socket.getaddrinfo(hostname, parsed.port or 443, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        raise SSRFError(f"Cannot resolve hostname: {hostname}")

    for family, _, _, _, sockaddr in addrinfo:
        ip_str = sockaddr[0]
        ip = ipaddress.ip_address(ip_str)

        if ip.is_private:
            raise SSRFError(f"Blocked private IP: {ip_str}")
        if ip.is_loopback:
            raise SSRFError(f"Blocked loopback IP: {ip_str}")
        if ip.is_link_local:
            raise SSRFError(f"Blocked link-local IP: {ip_str}")
        if ip.is_reserved:
            raise SSRFError(f"Blocked reserved IP: {ip_str}")

        # Explicit cloud metadata check (169.254.169.254)
        if ip_str == "169.254.169.254":
            raise SSRFError("Blocked cloud metadata endpoint")

    return url
