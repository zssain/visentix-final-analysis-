"""Report endpoints — generate and retrieve intelligence reports."""

from fastapi import APIRouter

from app.auth import AuthenticatedUser, require_role

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/")
async def list_reports(
    user: AuthenticatedUser = require_role("customer", "sme", "admin"),
):
    """List reports visible to the current user. Implemented in Phase 5."""
    return {"detail": "not_implemented", "role": user.role}
