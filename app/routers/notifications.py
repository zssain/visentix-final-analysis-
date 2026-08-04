"""F07 org notification settings (org-scoped). A customer may only read/write its
OWN org's settings; admin/sme may act on any. Feeds the alert pipeline's email /
webhook delivery. Generating a webhook_url also mints a per-org HMAC secret.
"""

from __future__ import annotations

import secrets

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.auth import AuthenticatedUser, require_role
from app.db import supabase_rest_get, supabase_rest_post
from app.services.intake.ssrf import SSRFError, resolve_and_validate

router = APIRouter(prefix="/orgs", tags=["notifications"])

_SEVERITIES = {"low", "moderate", "high", "severe"}


def _validate_webhook_url(url: str) -> None:
    """SEC-011: reject a webhook_url that is not a safe public https target.

    Webhooks are outbound POSTs the platform makes on the org's behalf, so an
    unvalidated URL is a second-order SSRF sink. We require https (a webhook
    endpoint must be encrypted) and run the full intake SSRF check
    (port allowlist + private/loopback/link-local/metadata/ULA/mapped-v6
    rejection). Only a URL that passes here is ever stored.
    """
    from urllib.parse import urlparse

    if urlparse(url).scheme != "https":
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "webhook_url must use https")
    try:
        resolve_and_validate(url)
    except SSRFError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            f"webhook_url rejected: {e}")


class NotificationSetting(BaseModel):
    email_to: str | None = None
    webhook_url: str | None = None
    min_severity: str | None = None


def _guard(user: AuthenticatedUser, org_id: str) -> None:
    if user.role in ("admin", "sme"):
        return
    if user.organization_id != org_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not permitted for this organization")


async def _load(org_id: str) -> dict | None:
    r = await supabase_rest_get("org_notification_setting", select="*",
                                filters=f"org_id=eq.{org_id}", limit=1)
    rows = r.json() if r.status_code == 200 else []
    return rows[0] if rows else None


@router.get("/{org_id}/notifications")
async def get_notifications(org_id: str, user: AuthenticatedUser = require_role("customer", "sme", "admin")):
    _guard(user, org_id)
    row = await _load(org_id)
    if not row:
        return {"org_id": org_id, "email_to": None, "webhook_url": None,
                "min_severity": None, "webhook_configured": False}
    return {"org_id": org_id, "email_to": row.get("email_to"),
            "webhook_url": row.get("webhook_url"), "min_severity": row.get("min_severity"),
            "webhook_configured": bool(row.get("webhook_secret"))}


@router.put("/{org_id}/notifications")
async def put_notifications(org_id: str, body: NotificationSetting,
                            user: AuthenticatedUser = require_role("customer", "sme", "admin")):
    _guard(user, org_id)
    if body.min_severity and body.min_severity not in _SEVERITIES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"bad min_severity: {body.min_severity}")
    # SEC-011: validate the webhook_url at SAVE — only a safe URL is ever stored.
    if body.webhook_url:
        _validate_webhook_url(body.webhook_url)
    existing = await _load(org_id)
    payload = {"org_id": org_id, "email_to": body.email_to, "webhook_url": body.webhook_url,
               "min_severity": body.min_severity}
    # Mint a per-org HMAC secret the first time a webhook is configured.
    if body.webhook_url and not (existing and existing.get("webhook_secret")):
        payload["webhook_secret"] = secrets.token_hex(32)
    r = await supabase_rest_post("org_notification_setting", payload,
                                 on_conflict="org_id", upsert=True)
    if r.status_code >= 400:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "failed to save settings")
    return {"ok": True, "org_id": org_id}


@router.post("/{org_id}/notifications/test")
async def test_send(org_id: str, user: AuthenticatedUser = require_role("customer", "sme", "admin")):
    """Send a test payload to the configured channels; honest success/fail."""
    _guard(user, org_id)
    from app.services.alerts import deliver_for_event
    row = await _load(org_id)
    if not row or not (row.get("email_to") or row.get("webhook_url")):
        return {"ok": False, "reason": "no channel configured"}
    # A test event is delivered through the same pipeline — which will report
    # 'suppressed_no_threshold' honestly while F-013 thresholds are unset.
    from app.services.jobs.framework import emit_event
    ev = await emit_event(org_id, "notice_changed", payload={"test": True})
    result = await deliver_for_event({"event_id": ev, "organization_id": org_id,
                                      "event_type": "notice_changed", "payload": {"test": True}})
    return {"ok": True, "result": result}
