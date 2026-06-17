"""Report endpoints — generate and retrieve intelligence reports."""

from fastapi import APIRouter

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/")
async def list_reports():
    """List reports. Implemented in Phase 5."""
    return {"detail": "not_implemented"}
