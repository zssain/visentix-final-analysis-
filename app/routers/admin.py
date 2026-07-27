"""Admin endpoints — system configuration and catalog management."""

from typing import Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.auth import AuthenticatedUser, require_role

router = APIRouter(prefix="/admin", tags=["admin"])


class TriggerAssessmentRequest(BaseModel):
    org_id: Optional[str] = None
    notice_ids: Optional[list[str]] = None


@router.get("/status")
async def admin_status(
    user: AuthenticatedUser = require_role("admin"),
):
    """Admin system status. Implemented in Phase 5."""
    return {"detail": "not_implemented", "admin": user.email}


@router.post("/trigger-assessment")
async def trigger_assessment(
    body: TriggerAssessmentRequest,
    user: AuthenticatedUser = require_role("admin"),
):
    """Run the scoring pipeline over an org's notices (or an explicit set).

    Admin-gated (F09). Returns the run identifier and per-notice results.
    """
    from app.services.reassessment import trigger_reassessment

    try:
        return await trigger_reassessment(
            org_id=body.org_id,
            notice_ids=body.notice_ids,
            triggered_by=user.email or user.user_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/training-stats")
async def training_stats(
    user: AuthenticatedUser = require_role("admin"),
):
    """Training label statistics — counts by action, domain, over time."""
    from app.services.training import get_training_stats
    return get_training_stats()
