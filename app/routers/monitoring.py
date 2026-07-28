"""Continuous-monitoring endpoints (F07 — M-06/M-07/M-08).

Three org-scoped, read-only views over stored data:
- GET /api/monitoring/trend?org_id   → F-012 trend deltas (M-06)
- GET /api/monitoring/events?org_id   → change feed (M-07)
- GET /api/monitoring/alerts?org_id   → F-013 escalations + resolved enforcement (M-08)

Org scoping (F10): a `customer` may only read its own `organization_id`; a
mismatched `org_id` is a cross-tenant read and is refused. `sme`/`admin` may
read any org and must pass `org_id` explicitly.
"""

from fastapi import APIRouter, HTTPException, Query, status

from app.auth import AuthenticatedUser, require_role
from app.services import monitoring

router = APIRouter(prefix="/api/monitoring", tags=["monitoring"])


def _resolve_org(user: AuthenticatedUser, org_id: str | None) -> str:
    """Apply F10 org isolation and return the org_id to query."""
    if user.role == "customer":
        own = user.organization_id
        if not own:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No organization is associated with this account.",
            )
        if org_id and org_id != own:
            # Cross-tenant read attempt — refuse (F10 AC-1).
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not permitted to read another organization's monitoring data.",
            )
        return own

    # sme / admin
    if not org_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="org_id is required.",
        )
    return org_id


@router.get("/trend")
async def monitoring_trend(
    org_id: str | None = Query(None),
    user: AuthenticatedUser = require_role("customer", "sme", "admin"),
):
    """F-012 trend deltas over the org's snapshot score history (M-06)."""
    return await monitoring.get_trend(_resolve_org(user, org_id))


@router.get("/events")
async def monitoring_events(
    org_id: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    user: AuthenticatedUser = require_role("customer", "sme", "admin"),
):
    """Change feed of `monitoring_event` rows for the org, newest first (M-07)."""
    return await monitoring.get_events(_resolve_org(user, org_id), limit=limit)


@router.get("/alerts")
async def monitoring_alerts(
    org_id: str | None = Query(None),
    user: AuthenticatedUser = require_role("customer", "sme", "admin"),
):
    """F-013 escalations joined to resolved enforcement only (M-08)."""
    return await monitoring.get_alerts(_resolve_org(user, org_id))


@router.get("/deliveries")
async def monitoring_deliveries(
    org_id: str | None = Query(None),
    user: AuthenticatedUser = require_role("customer", "sme", "admin"),
):
    """Per-event alert-delivery status for the org (drives the /monitor delivery
    chip: emailed / webhook / in-app only). Org-scoped like the other views."""
    from app.db import supabase_rest_get
    oid = _resolve_org(user, org_id)
    r = await supabase_rest_get("alert_delivery", select="monitoring_event_id,channel,status",
                                filters=f"org_id=eq.{oid}&order=created_at.desc", limit=1000)
    rows = r.json() if r.status_code == 200 else []
    by_event: dict[str, dict] = {}
    for row in rows:
        eid = row.get("monitoring_event_id")
        if eid and eid not in by_event:   # newest per event
            by_event[eid] = {"channel": row.get("channel"), "status": row.get("status")}
    return {"org_id": oid, "deliveries": by_event}
