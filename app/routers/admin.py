"""Admin endpoints — system configuration and catalog management."""

from fastapi import APIRouter

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/status")
async def admin_status():
    """Admin system status. Implemented in Phase 5."""
    return {"detail": "not_implemented"}
