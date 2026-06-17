"""Assessment endpoints — CRUD for privacy notice assessments."""

from fastapi import APIRouter

from app.auth import AuthenticatedUser, require_role

router = APIRouter(prefix="/assessments", tags=["assessments"])


@router.get("/")
async def list_assessments(
    user: AuthenticatedUser = require_role("customer", "sme", "admin"),
):
    """List assessments visible to the current user. Implemented in Phase 3."""
    return {"detail": "not_implemented", "role": user.role}
