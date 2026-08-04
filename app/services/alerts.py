"""F07 alert pipeline — runs after each job over new monitoring_events.

For each event: compute F-013 escalation (existing formula). IF platform F-013
severity thresholds are UNSET in platform_setting → write
alert_delivery(status='suppressed_no_threshold') and DO NOT send (an admin banner
surfaces this). We NEVER invent thresholds (Hard Rule / MUST NOT). Only when
thresholds exist AND severity ≥ threshold do we render + send email / webhook.

Senders are injectable so tests assert ZERO real sends. Delivery is strictly
org-scoped: an event's org only ever reaches that org's own settings.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone
from uuid import uuid4

import httpcore  # transitive dep of httpx — used to pin the validated IP (SEC-011)
import httpx
from jinja2 import Template

from app.config import settings
from app.db import supabase_rest_get, supabase_rest_post
from app.services.intake.ssrf import SSRFError
from app.services.jobs.framework import get_setting
from app.services.scoring.formulas_advanced import compute_f013

log = logging.getLogger(__name__)

# platform_setting key holding the expert-approved F-013 severity thresholds.
# Absent → alert delivery is PAUSED (suppressed_no_threshold). MUST NOT set it here.
F013_THRESHOLD_KEY = "f013_severity_thresholds"

_SEVERITY_ORDER = {"low": 0, "moderate": 1, "high": 2, "severe": 3}

_EMAIL_TEMPLATE = Template(
    "Hello,\n\n"
    "There is a new update on a privacy notice you're monitoring: "
    "{{ headline }}.\n\n"
    "View the details on your monitoring dashboard: {{ link }}\n\n"
    "— Visentix\n"
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _headline(event: dict) -> str:
    t = event.get("event_type")
    p = event.get("payload") or {}
    if t == "score_moved":
        return f"a monitored notice's {p.get('domain', 'domain')} position moved from {p.get('from')} to {p.get('to')}"
    if t == "notice_changed":
        return "a monitored notice changed"
    if t == "regulator_signal":
        return "a regulator signal matched one of your weaker domains"
    if t == "cohort_rebenchmarked":
        return "your benchmark cohort was refreshed"
    return "a monitoring update"


def _f013_inputs(event: dict) -> dict:
    """Derive F-013 inputs from the event (existing formula; no thresholds set)."""
    p = event.get("payload") or {}
    risk_increase = 0.0
    if event.get("event_type") == "score_moved" and p.get("from") is not None and p.get("to") is not None:
        risk_increase = max(0.0, (float(p["from"]) - float(p["to"])) / 100.0)  # a drop = risk up
    enforcement_corr = 0.6 if event.get("event_type") == "regulator_signal" else 0.2
    return {"risk_increase": risk_increase, "enforcement_correlation": enforcement_corr,
            "monitoring_priority": 0.5, "confidence": 0.6, "has_monitoring_data": True,
            "monitoring_event_id": event.get("event_id", "")}


async def _thresholds() -> dict | None:
    raw = await get_setting(F013_THRESHOLD_KEY)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None


def _severity_band(f013_score: float, thresholds: dict) -> str:
    """Map an F-013 score to a band using EXPERT-provided thresholds (only when set)."""
    for band in ("severe", "high", "moderate", "low"):
        if band in thresholds and f013_score >= thresholds[band]:
            return band
    return "low"


async def _org_settings(org_id: str) -> dict | None:
    r = await supabase_rest_get("org_notification_setting", select="*",
                                filters=f"org_id=eq.{org_id}", limit=1)
    rows = r.json() if r.status_code == 200 else []
    return rows[0] if rows else None


async def _record(event_id: str, org_id: str | None, channel: str | None,
                  destination: str | None, status: str, error: str | None = None) -> None:
    await supabase_rest_post("alert_delivery", {
        "id": str(uuid4()), "monitoring_event_id": event_id, "org_id": org_id,
        "channel": channel, "destination": destination, "status": status,
        "sent_at": _now() if status == "sent" else None, "error": error,
        "created_at": _now(),
    })


def _default_smtp_send(to: str, subject: str, body: str) -> None:  # pragma: no cover - real IO
    import smtplib
    from email.mime.text import MIMEText
    host = getattr(settings, "smtp_host", None)
    if not host:
        raise RuntimeError("SMTP not configured (SMTP_HOST unset)")
    msg = MIMEText(body)
    msg["Subject"], msg["From"], msg["To"] = subject, getattr(settings, "smtp_from", "alerts@visentix"), to
    with smtplib.SMTP(host, int(getattr(settings, "smtp_port", 587))) as s:
        user = getattr(settings, "smtp_user", None)
        if user:
            s.starttls()
            s.login(user, getattr(settings, "smtp_pass", ""))
        s.send_message(msg)


class _SyncPinnedBackend(httpcore.SyncBackend):
    """SEC-002: sync mirror of extract._PinnedResolverBackend — dials the
    pre-validated IP instead of re-resolving the host at connect time (the
    DNS-rebinding TOCTOU). TLS SNI + cert verification still use the origin
    hostname, so HTTPS integrity is preserved."""

    def __init__(self, host_to_ip: dict[str, str]):
        self._host_to_ip = host_to_ip
        super().__init__()

    def connect_tcp(self, host, port, timeout=None, local_address=None,
                    socket_options=None):
        target = self._host_to_ip.get(host.lower(), host)
        return super().connect_tcp(
            target, port, timeout=timeout,
            local_address=local_address, socket_options=socket_options,
        )


class _SyncPinnedTransport(httpx.HTTPTransport):
    """httpx sync transport whose pool dials pinned IPs (see backend)."""

    def __init__(self, host_to_ip: dict[str, str], **kwargs):
        super().__init__(**kwargs)
        # `_pool` / `_network_backend` are httpx/httpcore internals, stable in 0.28.x.
        self._pool._network_backend = _SyncPinnedBackend(host_to_ip)


def _default_http_post(url: str, body: dict, signature: str) -> int:
    """SEC-011 / SEC-002: re-validate + IP-pin the webhook POST at send time.

    A URL that was public-safe at SAVE may resolve to a private/metadata address
    at SEND (DNS rebinding). So we re-run resolve_and_validate here (raises
    SSRFError on any blocked/nonstandard target — the caller does NOT POST and
    records a failure, never a silent success) and pin the socket to the exact IP
    that was just validated, keeping the hostname for TLS SNI + the Host header.
    Redirects are not followed (a 3xx Location could point at an internal host).
    """
    from urllib.parse import urlparse

    from app.services.intake.ssrf import resolve_and_validate as _rv

    _, ip, _port = _rv(url)  # raises SSRFError → caught by deliver_for_event → recorded failed
    host = (urlparse(url).hostname or "").strip().rstrip(".").lower()
    transport = _SyncPinnedTransport({host: ip})
    with httpx.Client(transport=transport, timeout=10, follow_redirects=False) as client:
        r = client.post(url, json=body, headers={"X-Visentix-Signature": signature})
    return r.status_code


def sign_webhook(secret: str, body: dict) -> str:
    """HMAC-SHA256 over the canonical JSON body — verifiable by the receiver."""
    raw = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    return hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()


async def deliver_for_event(event: dict, *, smtp_send=_default_smtp_send,
                            http_post=_default_http_post) -> list[dict]:
    """Process one monitoring_event → alert_delivery rows. Returns the deliveries.

    Suppresses (no send) when F-013 thresholds are unset. Otherwise sends only to
    THIS event's org via its own settings (never another org)."""
    event_id = event["event_id"]
    org_id = event.get("organization_id")
    f013 = compute_f013(**_f013_inputs(event))

    thresholds = await _thresholds()
    if not thresholds:
        # Alert delivery paused pending expert severity thresholds. Never send.
        await _record(event_id, org_id, None, None, "suppressed_no_threshold")
        return [{"status": "suppressed_no_threshold", "f013": f013.score}]

    band = _severity_band(f013.score, thresholds)
    st = await _org_settings(org_id) if org_id else None
    min_sev = (st or {}).get("min_severity") or thresholds.get("platform_min_severity", "high")
    if _SEVERITY_ORDER.get(band, 0) < _SEVERITY_ORDER.get(min_sev, 2):
        return [{"status": "below_min_severity", "band": band}]

    deliveries: list[dict] = []
    link = f"{getattr(settings, 'public_base_url', 'https://app.visentix')}/monitor"
    if st and st.get("email_to"):
        try:
            smtp_send(st["email_to"], "Visentix monitoring update",
                      _EMAIL_TEMPLATE.render(headline=_headline(event), link=link))
            await _record(event_id, org_id, "email", st["email_to"], "sent")
            deliveries.append({"channel": "email", "status": "sent"})
        except Exception as e:  # noqa: BLE001
            await _record(event_id, org_id, "email", st["email_to"], "failed", str(e))
            deliveries.append({"channel": "email", "status": "failed"})
    if st and st.get("webhook_url"):
        body = {"event_id": event_id, "org_id": org_id, "type": event.get("event_type"),
                "severity": band, "occurred_at": event.get("ts") or _now(), "link": link}
        secret = st.get("webhook_secret") or ""
        try:
            code = http_post(st["webhook_url"], body, sign_webhook(secret, body))
            ok = 200 <= code < 300
            await _record(event_id, org_id, "webhook", st["webhook_url"],
                          "sent" if ok else "failed", None if ok else f"HTTP {code}")
            deliveries.append({"channel": "webhook", "status": "sent" if ok else "failed"})
        except SSRFError as e:
            # SEC-011: the stored URL now resolves to a blocked target (rebinding)
            # or the pinning transport refused it. Do NOT POST — record + skip.
            log.warning("webhook SSRF refused for org=%s: %s", org_id, e)
            await _record(event_id, org_id, "webhook", st["webhook_url"], "failed", f"SSRF blocked: {e}")
            deliveries.append({"channel": "webhook", "status": "failed", "reason": "ssrf_blocked"})
        except Exception as e:  # noqa: BLE001
            await _record(event_id, org_id, "webhook", st["webhook_url"], "failed", str(e))
            deliveries.append({"channel": "webhook", "status": "failed"})
    return deliveries or [{"status": "no_channel_configured", "band": band}]
