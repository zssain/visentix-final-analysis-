"""Findings endpoints — risk findings for an organization/notice."""

from fastapi import APIRouter

router = APIRouter(prefix="/findings", tags=["findings"])


@router.get("/")
async def list_findings():
    """List findings. Implemented in Phase 4."""
    return {"detail": "not_implemented"}
