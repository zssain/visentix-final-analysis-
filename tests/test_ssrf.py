"""SEC-002 / SEC-004 — SSRF validation, IP pinning, and fetch behaviour.

Closes the report's "no direct SSRF unit test" gap. `socket.getaddrinfo` is
mocked so we control what a hostname resolves to (including hostile/rebinding
answers) without real DNS or network.
"""

import socket
from unittest.mock import patch
from urllib.parse import urlparse

import httpcore
import httpx
import pytest

import app.services.intake.extract as E
from app.services.intake.extract import _PinnedResolverBackend, _fetch_ssrf_safe
from app.services.intake.ssrf import (
    SSRFError,
    resolve_and_validate,
    validate_url,
)

PUBLIC_IP = "93.184.216.34"  # example.com — a normal public address


def _ai(*ips):
    """Build a socket.getaddrinfo-shaped result for the given IP strings."""
    out = []
    for ip in ips:
        fam = socket.AF_INET6 if ":" in ip else socket.AF_INET
        sockaddr = (ip, 0) if fam == socket.AF_INET else (ip, 0, 0, 0)
        out.append((fam, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", sockaddr))
    return out


def _resolves_to(*ips):
    """Patch getaddrinfo (as imported in ssrf) to resolve to the given IPs."""
    return patch("app.services.intake.ssrf.socket.getaddrinfo", lambda *a, **k: _ai(*ips))


# ── validate_url / resolve_and_validate: block list ──────────────

@pytest.mark.parametrize("ip", [
    "127.0.0.1",            # loopback
    "10.0.0.1",             # RFC1918
    "10.255.255.255",
    "192.168.1.1",          # RFC1918
    "172.16.0.5",           # RFC1918
    "169.254.169.254",      # cloud metadata / link-local
    "169.254.1.1",          # link-local
    "::1",                  # IPv6 loopback
    "fc00::1",              # IPv6 ULA
    "fd12:3456::1",         # IPv6 ULA
    "::ffff:169.254.169.254",  # IPv4-mapped IPv6 (bypass form)
    "::ffff:10.0.0.1",         # IPv4-mapped RFC1918
    "0.0.0.0",              # unspecified
])
def test_blocked_ips_rejected(ip):
    with _resolves_to(ip):
        with pytest.raises(SSRFError):
            resolve_and_validate("https://evil.example.com/policy")


def test_localhost_hostname_blocked():
    # localhost resolves to loopback → blocked
    with _resolves_to("127.0.0.1"):
        with pytest.raises(SSRFError):
            validate_url("http://localhost/admin")


def test_metadata_hostname_blocked():
    with pytest.raises(SSRFError):
        validate_url("http://metadata.google.internal/computeMetadata/v1/")


@pytest.mark.parametrize("url", [
    "ftp://example.com/x",
    "file:///etc/passwd",
    "gopher://example.com/",
    "http://example.com:6379/",     # Redis — nonstandard port
    "http://example.com:11434/",    # Ollama
    "http://example.com:5432/",     # Postgres
    "https://example.com:8000/",
])
def test_scheme_and_port_allowlist(url):
    # Port checks happen before resolution, so no getaddrinfo mock is needed;
    # provide one anyway so a scheme that slips through can't hit real DNS.
    with _resolves_to(PUBLIC_IP):
        with pytest.raises(SSRFError):
            resolve_and_validate(url)


def test_unresolvable_host_blocked():
    with patch("app.services.intake.ssrf.socket.getaddrinfo",
               side_effect=socket.gaierror("nope")):
        with pytest.raises(SSRFError):
            validate_url("https://does-not-exist.invalid/x")


def test_round_robin_rebinding_rejected():
    # A hostile resolver returns a public AND a private address; any blocked
    # address in the set must reject the whole URL.
    with _resolves_to(PUBLIC_IP, "10.0.0.5"):
        with pytest.raises(SSRFError):
            resolve_and_validate("https://mixed.example.com/x")


# ── valid path + pinning ────────────────────────────────────────

def test_valid_https_returns_url_and_pins_ip():
    with _resolves_to(PUBLIC_IP):
        url, ip, port = resolve_and_validate("https://example.com/privacy")
    assert url == "https://example.com/privacy"
    assert ip == PUBLIC_IP
    assert port == 443
    with _resolves_to(PUBLIC_IP):
        assert validate_url("https://example.com/privacy") == "https://example.com/privacy"


def test_default_ports_allowed():
    with _resolves_to(PUBLIC_IP):
        assert resolve_and_validate("http://example.com/x")[2] == 80
        assert resolve_and_validate("https://example.com/x")[2] == 443


@pytest.mark.anyio
async def test_pinned_backend_dials_ip_not_hostname():
    """The pinning backend must connect to the validated IP, not re-resolve the host."""
    captured = {}

    async def fake_connect(self, host, port, timeout=None, local_address=None,
                           socket_options=None):
        captured["host"] = host
        captured["port"] = port
        return object()

    with patch.object(httpcore.AnyIOBackend, "connect_tcp", fake_connect):
        backend = _PinnedResolverBackend({"example.com": PUBLIC_IP})
        await backend.connect_tcp("example.com", 443)
    assert captured["host"] == PUBLIC_IP, "socket must dial the pinned IP, not the hostname"
    assert captured["port"] == 443


# ── fetch behaviour (redirect re-validation) ────────────────────

@pytest.mark.anyio
async def test_fetch_rejects_redirect_to_private():
    """A redirect Location pointing at a private host must be re-validated + rejected."""
    def fake_rv(u):
        host = urlparse(u).hostname
        if host == "evil.internal":
            raise SSRFError("blocked private redirect target")
        return (u, PUBLIC_IP, 443)

    def handler(request):
        return httpx.Response(302, headers={"location": "http://evil.internal/latest/meta-data/"})

    mock = httpx.MockTransport(handler)
    with patch.object(E, "resolve_and_validate", fake_rv):
        with pytest.raises(SSRFError):
            await _fetch_ssrf_safe("https://good.example.com/policy", transport=mock)


@pytest.mark.anyio
async def test_fetch_returns_ok_response():
    def fake_rv(u):
        return (u, PUBLIC_IP, 443)

    def handler(request):
        return httpx.Response(200, text="<html><body>Privacy policy body.</body></html>",
                              headers={"content-type": "text/html"})

    mock = httpx.MockTransport(handler)
    with patch.object(E, "resolve_and_validate", fake_rv):
        resp = await _fetch_ssrf_safe("https://good.example.com/policy", transport=mock)
    assert resp.status_code == 200
