"""SEC-011 — webhook_url is a second-order SSRF sink; validate at SAVE and re-pin
at SEND.

Closes the gap where `put_notifications` stored a `webhook_url` unvalidated and
`alerts._default_http_post` POSTed to it via a raw httpx call, bypassing all the
intake SSRF hardening. `socket.getaddrinfo` is mocked (as in tests/test_ssrf.py)
so we control what a hostname resolves to — including hostile rebinding answers —
without real DNS or network.
"""

import socket
import time
from unittest.mock import patch

import jwt as pyjwt
import pytest
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.main import app
from app.services import alerts
from app.services.intake.ssrf import SSRFError

PUBLIC_IP = "93.184.216.34"  # example.com — a normal public address


# ── DNS mocking (mirrors tests/test_ssrf.py) ─────────────────

def _ai(*ips):
    out = []
    for ip in ips:
        fam = socket.AF_INET6 if ":" in ip else socket.AF_INET
        sockaddr = (ip, 0) if fam == socket.AF_INET else (ip, 0, 0, 0)
        out.append((fam, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", sockaddr))
    return out


def _resolves_to(*ips):
    return patch("app.services.intake.ssrf.socket.getaddrinfo", lambda *a, **k: _ai(*ips))


# ── auth helpers ─────────────────────────────────────────────

def _hdr(role="customer", org="ORG-A"):
    now = int(time.time())
    tok = pyjwt.encode({"sub": "u", "aud": "authenticated", "iat": now - 60, "exp": now + 3600,
                        "app_role": role, "organization_id": org},
                       settings.supabase_jwt_secret, algorithm="HS256")
    return {"Authorization": f"Bearer {tok}"}


class _Resp:
    def __init__(self, status_code=200, data=None):
        self.status_code, self._data, self.text = status_code, data or [], ""

    def json(self):
        return self._data


async def _put_webhook(url: str):
    """PUT a webhook_url through the real router. DB layer is stubbed so we only
    exercise the SEC-011 validation path (no network / no Supabase)."""
    async def fake_get(*a, **k):
        return _Resp(200, [])  # no existing settings

    async def fake_post(*a, **k):
        return _Resp(200, [{}])  # save succeeds

    transport = ASGITransport(app=app)
    with patch("app.routers.notifications.supabase_rest_get", fake_get), \
         patch("app.routers.notifications.supabase_rest_post", fake_post):
        async with AsyncClient(transport=transport, base_url="http://t") as c:
            return await c.put("/orgs/ORG-A/notifications",
                               json={"webhook_url": url}, headers=_hdr())


# ── SAVE-path validation ─────────────────────────────────────

@pytest.mark.anyio
@pytest.mark.parametrize("ip", [
    "127.0.0.1",            # loopback
    "10.0.0.1",             # RFC1918
    "192.168.1.1",          # RFC1918
    "169.254.169.254",      # cloud metadata / link-local
    "::1",                  # IPv6 loopback
    "fc00::1",              # IPv6 ULA
    "::ffff:10.0.0.1",      # IPv4-mapped RFC1918 (bypass form)
])
async def test_save_rejects_private_webhook(ip):
    with _resolves_to(ip):
        r = await _put_webhook("https://evil.example.com/hook")
    assert r.status_code == 400, r.text


@pytest.mark.anyio
async def test_save_rejects_http_webhook():
    # https is required for webhooks even if the host is otherwise public-safe.
    with _resolves_to(PUBLIC_IP):
        r = await _put_webhook("http://example.com/hook")
    assert r.status_code == 400
    assert "https" in r.text.lower()


@pytest.mark.anyio
async def test_save_rejects_nonstandard_port():
    with _resolves_to(PUBLIC_IP):
        r = await _put_webhook("https://example.com:6379/hook")
    assert r.status_code == 400


@pytest.mark.anyio
async def test_save_accepts_public_https_webhook():
    with _resolves_to(PUBLIC_IP):
        r = await _put_webhook("https://example.com/hook")
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is True


# ── SEND-path re-validation (DNS rebinding) ──────────────────

@pytest.mark.anyio
async def test_send_refuses_rebound_webhook_no_post(monkeypatch):
    """A URL that passed SAVE now resolves to a private IP at SEND time. The send
    path must re-validate, refuse to POST, and record a failure (never 'sent')."""
    posted = {"count": 0}

    def spy_post(self, url, json=None, headers=None, **kw):  # would be the real POST
        posted["count"] += 1
        return _Resp(200)

    # Patch resolve_and_validate WHERE _default_http_post imports it from, so the
    # send-time re-validation raises for the (now-hostile) webhook host.
    def rebound_rv(url):
        raise SSRFError("rebound to private IP")

    monkeypatch.setattr("app.services.intake.ssrf.resolve_and_validate", rebound_rv)
    monkeypatch.setattr("httpx.Client.post", spy_post)

    # SSRFError from the pinning re-validation must propagate out of _default_http_post
    with pytest.raises(SSRFError):
        alerts._default_http_post("https://example.com/hook", {"a": 1}, "sig")

    assert posted["count"] == 0, "must NOT POST when the URL fails re-validation"


@pytest.mark.anyio
async def test_deliver_records_failed_not_sent_on_rebinding(monkeypatch):
    """End-to-end through deliver_for_event: a rebound webhook is recorded as
    failed (ssrf_blocked), never 'sent'."""
    recorded = []

    async def fake_thresholds():
        return {"severe": 0.0, "platform_min_severity": "low"}

    async def fake_org_settings(org_id):
        return {"webhook_url": "https://example.com/hook", "webhook_secret": "s"}

    async def fake_record(event_id, org_id, channel, destination, status, error=None):
        recorded.append({"channel": channel, "status": status, "error": error})

    def rebound_http_post(url, body, signature):
        raise SSRFError("rebound to 10.0.0.1")

    monkeypatch.setattr(alerts, "_thresholds", fake_thresholds)
    monkeypatch.setattr(alerts, "_org_settings", fake_org_settings)
    monkeypatch.setattr(alerts, "_record", fake_record)

    out = await alerts.deliver_for_event(
        {"event_id": "e1", "organization_id": "ORG-A", "event_type": "notice_changed",
         "payload": {}},
        http_post=rebound_http_post,
    )

    webhook_deliveries = [d for d in out if d.get("channel") == "webhook"]
    assert webhook_deliveries, out
    assert all(d["status"] == "failed" for d in webhook_deliveries)
    assert any(r["channel"] == "webhook" and r["status"] == "failed" for r in recorded)
    assert not any(r["status"] == "sent" for r in recorded), "must never record 'sent'"


@pytest.mark.anyio
async def test_send_pins_validated_ip_and_posts_when_safe(monkeypatch):
    """Happy path: a valid public host is pinned and the POST is made to it."""
    captured = {}

    def spy_post(self, url, json=None, headers=None, **kw):
        captured["url"] = url
        captured["headers"] = headers
        return _Resp(200)

    monkeypatch.setattr("httpx.Client.post", spy_post)

    with _resolves_to(PUBLIC_IP):
        code = alerts._default_http_post("https://example.com/hook", {"a": 1}, "sig")

    assert code == 200
    assert captured["url"] == "https://example.com/hook"
    assert captured["headers"]["X-Visentix-Signature"] == "sig"
