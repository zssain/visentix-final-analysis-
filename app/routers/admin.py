"""Admin endpoints — system configuration and catalog management."""

from fastapi import APIRouter

from app.auth import AuthenticatedUser, require_role

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/status")
async def admin_status(
    user: AuthenticatedUser = require_role("admin"),
):
    """Admin system status. Implemented in Phase 5."""
    return {"detail": "not_implemented", "admin": user.email}


@router.post("/trigger-assessment")
async def trigger_assessment(
    user: AuthenticatedUser = require_role("admin"),
):
    """Trigger a new assessment run. Implemented in Phase 3."""
    return {"detail": "not_implemented"}
