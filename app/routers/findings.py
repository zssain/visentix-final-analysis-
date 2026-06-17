"""Findings endpoints — risk findings for an organization/notice."""

from fastapi import APIRouter

from app.auth import AuthenticatedUser, require_role

router = APIRouter(prefix="/findings", tags=["findings"])


@router.get("/")
async def list_findings(
    user: AuthenticatedUser = require_role("customer", "sme", "admin"),
):
    """List findings visible to the current user. Implemented in Phase 4."""
    return {"detail": "not_implemented", "role": user.role}
