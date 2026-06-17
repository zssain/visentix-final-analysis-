"""Assessment endpoints — CRUD for privacy notice assessments."""

from fastapi import APIRouter

router = APIRouter(prefix="/assessments", tags=["assessments"])


@router.get("/")
async def list_assessments():
    """List all assessments. Implemented in Phase 3."""
    return {"detail": "not_implemented"}
