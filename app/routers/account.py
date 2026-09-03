"""Authenticated account metadata endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.auth import AuthenticatedUser, require_role
from app.db import supabase_rest_get
from app.services.tenancy import customer_org_scope

router = APIRouter(prefix="/account", tags=["account"])


@router.get("/audit")
async def list_my_audit_events(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0, le=100_000),
    user: AuthenticatedUser = require_role("customer", "sme", "admin", "partner_admin"),
):
    """Return the caller's own content-free activity history, newest first."""
    scope = customer_org_scope(user)
    if not user.organization_id or (user.role == "customer" and not scope.allowed):
        return {"items": [], "limit": limit, "offset": offset}

    # This endpoint is caller-only for every role. Even a platform role cannot
    # use it as an organization-wide user surveillance endpoint.
    filters = (
        f"organization_id=eq.{user.organization_id}"
        f"&user_id=eq.{user.user_id}"
        f"&order=at.desc&offset={offset}"
    )
    response = await supabase_rest_get(
        "audit_event",
        select="id,action,resource_type,resource_id,at,request_id,expires_at",
        filters=filters,
        limit=limit,
    )
    items = response.json() if response.status_code == 200 else []
    return {"items": items, "limit": limit, "offset": offset}

