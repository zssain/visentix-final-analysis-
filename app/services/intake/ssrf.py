"""SSRF defense — validates URLs before server-side fetch.

Blocks: private ranges (10/8, 172.16/12, 192.168/16, 127/8), link-local
(169.254/16), loopback (::1), reserved, multicast, IPv6 ULA (fc00::/7), and
cloud metadata (169.254.169.254). IPv4-mapped IPv6 (::ffff:a.b.c.d) is rejected
outright. Only http/https, only ports 80/443.

SEC-002 (DNS-rebinding TOCTOU): `resolve_and_validate` resolves the host ONCE,
validates every resolved address, and returns a single pinned IP. The fetch
(`extract._fetch_ssrf_safe`) then connects to that pinned IP via a custom httpx
network backend while preserving the hostname for TLS SNI + the Host header — so
the IP that was validated is the IP that is connected to. `validate_url` remains
as a thin, backward-compatible wrapper (used by connectors/discover).
"""

import ipaddress
import socket
from urllib.parse import urlparse


class SSRFError(ValueError):
    """Raised when a URL targets a blocked network range."""


BLOCKED_HOSTNAMES = {"metadata.google.internal", "metadata.gce.internal"}

# SEC-004: only standard web ports. A public-resolving host must not be usable to
# reach :6379 (Redis), :11434 (Ollama), :5432 (Postgres), :8000, etc.
ALLOWED_PORTS = {80, 443}

# IPv6 Unique Local Addresses (RFC 4193). `is_private` already covers these, but
# we check explicitly (SEC-004) so the intent is unmistakable.
_IPV6_ULA = ipaddress.ip_network("fc00::/7")

# Max response size: 10 MB
MAX_RESPONSE_BYTES = 10 * 1024 * 1024

# Fetch timeout
FETCH_TIMEOUT_SECONDS = 30


def _normalize_hostname(hostname: str) -> str:
    """Lower-case, strip a trailing FQDN dot, and IDNA-encode unicode hosts."""
    h = hostname.strip().rstrip(".").lower()
    try:
        h = h.encode("idna").decode("ascii")
    except (UnicodeError, ValueError):
        # Leave as-is; getaddrinfo will reject a genuinely bad host.
        pass
    return h


def _check_ip(ip_str: str) -> None:
    """Raise SSRFError if `ip_str` is in any blocked range."""
    ip = ipaddress.ip_address(ip_str)

    # IPv4-mapped IPv6 (::ffff:169.254.169.254) — reject outright; no legitimate
    # host needs it and it is a classic filter-bypass form (SEC-004).
    if ip.version == 6 and ip.ipv4_mapped is not None:
        raise SSRFError(f"Blocked IPv4-mapped IPv6 address: {ip_str}")

    if ip.is_private:
        raise SSRFError(f"Blocked private IP: {ip_str}")
    if ip.is_loopback:
        raise SSRFError(f"Blocked loopback IP: {ip_str}")
    if ip.is_link_local:
        raise SSRFError(f"Blocked link-local IP: {ip_str}")
    if ip.is_reserved:
        raise SSRFError(f"Blocked reserved IP: {ip_str}")
    if ip.is_multicast:
        raise SSRFError(f"Blocked multicast IP: {ip_str}")
    if ip.is_unspecified:
        raise SSRFError(f"Blocked unspecified IP: {ip_str}")
    if ip.version == 6 and ip in _IPV6_ULA:
        raise SSRFError(f"Blocked IPv6 ULA: {ip_str}")

    # Explicit cloud metadata check (169.254.169.254 is also link-local above,
    # but keep the named check for clarity and future non-link-local metadata IPs).
    if ip_str == "169.254.169.254":
        raise SSRFError("Blocked cloud metadata endpoint")


def resolve_and_validate(url: str) -> tuple[str, str, int]:
    """Validate a URL and resolve it to a single safe IP to PIN the fetch to.

    Returns (url, pinned_ip, port). Raises SSRFError if the scheme/port is
    disallowed, the host can't resolve, or ANY resolved address is in a blocked
    range (rejecting round-robin rebinding). The returned IP is the one the
    caller must connect to; TLS SNI / Host stay on the hostname.
    """
    parsed = urlparse(url)

    if parsed.scheme not in ("http", "https"):
        raise SSRFError(f"Blocked scheme: {parsed.scheme}. Only http/https allowed.")

    hostname = parsed.hostname
    if not hostname:
        raise SSRFError("No hostname in URL.")
    hostname = _normalize_hostname(hostname)

    if hostname in BLOCKED_HOSTNAMES:
        raise SSRFError(f"Blocked hostname: {hostname}")

    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    if port not in ALLOWED_PORTS:
        raise SSRFError(f"Blocked port: {port}. Only ports {sorted(ALLOWED_PORTS)} allowed.")

    try:
        addrinfo = socket.getaddrinfo(hostname, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        raise SSRFError(f"Cannot resolve hostname: {hostname}")
    if not addrinfo:
        raise SSRFError(f"Cannot resolve hostname: {hostname}")

    pinned_ip: str | None = None
    for _family, _type, _proto, _canon, sockaddr in addrinfo:
        ip_str = sockaddr[0]
        _check_ip(ip_str)  # raises if ANY resolved address is blocked
        if pinned_ip is None:
            pinned_ip = ip_str

    assert pinned_ip is not None  # addrinfo was non-empty and none raised
    return url, pinned_ip, port


def validate_url(url: str) -> str:
    """Validate a URL for safe server-side fetching. Returns the URL if safe.

    Backward-compatible wrapper over `resolve_and_validate` (used by connectors
    and `discover.py`). It now also enforces the port allowlist and IPv6
    hardening (SEC-004). Callers that need to pin the connection IP should use
    `resolve_and_validate` directly (see `extract._fetch_ssrf_safe`).
    """
    resolve_and_validate(url)
    return url
