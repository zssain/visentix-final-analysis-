"""SME review routes — queue, review, finding actions, approve."""

from dataclasses import asdict
from typing import Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.auth import AuthenticatedUser, require_role
from app.services.review import (
    AssessmentStatus,
    FindingAction,
    GateMode,
    approve_assessment,
    customer_can_view,
    get_active_findings,
    get_gate_mode,
    get_or_create_review,
    get_pending_queue,
    get_review,
    set_gate_mode,
    submit_finding_action,
)

router = APIRouter(prefix="/review", tags=["review"])


class FindingActionRequest(BaseModel):
    action: FindingAction
    edited_fields: Optional[dict] = None


class GateModeRequest(BaseModel):
    mode: GateMode


@router.get("/queue")
async def review_queue(
    user: AuthenticatedUser = require_role("sme", "admin"),
):
    """List assessments pending SME review."""
    queue = get_pending_queue()
    return [asdict(r) for r in queue]


@router.get("/{assessment_id}")
async def review_assessment(
    assessment_id: str,
    user: AuthenticatedUser = require_role("sme", "admin"),
):
    """View an assessment's findings and review state."""
    review = get_or_create_review(assessment_id)
    return asdict(review)


@router.post("/finding/{assessment_id}/{finding_id}")
async def review_finding(
    assessment_id: str,
    finding_id: str,
    body: FindingActionRequest,
    user: AuthenticatedUser = require_role("sme", "admin"),
):
    """Submit a review action on a finding: confirm, edit, or dismiss."""
    try:
        fr = submit_finding_action(
            assessment_id=assessment_id,
            finding_id=finding_id,
            action=body.action,
            edited_fields=body.edited_fields,
            reviewer_id=user.user_id,
        )
        return asdict(fr)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{assessment_id}/approve")
async def approve(
    assessment_id: str,
    user: AuthenticatedUser = require_role("sme", "admin"),
):
    """Approve an assessment, freezing the customer-visible snapshot."""
    try:
        review = approve_assessment(assessment_id, user.user_id)
        return asdict(review)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/gate-mode")
async def get_current_gate_mode(
    user: AuthenticatedUser = require_role("admin"),
):
    """Get the current gate mode."""
    return {"mode": get_gate_mode().value}


@router.post("/gate-mode")
async def set_current_gate_mode(
    body: GateModeRequest,
    user: AuthenticatedUser = require_role("admin"),
):
    """Set the gate mode (admin only)."""
    set_gate_mode(body.mode)
    return {"mode": body.mode.value}
