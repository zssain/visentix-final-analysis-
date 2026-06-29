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


# ══════════════════════════════════════════════════════════════
# Exemplar review routes (SME/admin only)
# ══════════════════════════════════════════════════════════════

class ExemplarCleanRequest(BaseModel):
    cleaned_text: str
    maturity_note: str


class ExemplarApproveRequest(BaseModel):
    pass  # approval uses the already-cleaned text


@router.get("/exemplars")
async def list_candidate_exemplars(
    user: AuthenticatedUser = require_role("sme", "admin"),
):
    """List exemplar candidates (sme_cleaned=false) for review."""
    from app.db import supabase_rest_get
    r = await supabase_rest_get(
        "exemplar",
        select="id,domain,clause_text,maturity_note,source_internal_ref,sme_cleaned",
        filters="sme_cleaned=eq.false",
        limit=100,
    )
    return r.json()


@router.post("/exemplar/{exemplar_id}/clean")
async def clean_exemplar(
    exemplar_id: str,
    body: ExemplarCleanRequest,
    user: AuthenticatedUser = require_role("sme", "admin"),
):
    """Submit de-identified cleaned text for an exemplar."""
    from app.services.exemplar_review import validate_deidentification
    from app.db import get_service_headers
    import httpx as hx
    from app.config import settings

    # Validate de-identification
    identifiers = validate_deidentification(body.cleaned_text)
    if identifiers:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cleaned text contains identifying tokens: {identifiers}. Remove them first.",
        )

    headers = {**get_service_headers(), "Content-Type": "application/json", "Prefer": "return=representation"}
    async with hx.AsyncClient(timeout=15) as client:
        r = await client.patch(
            f"{settings.supabase_url}/rest/v1/exemplar?id=eq.{exemplar_id}",
            headers=headers,
            json={
                "clause_text": body.cleaned_text,
                "maturity_note": body.maturity_note,
            },
        )
    if r.status_code >= 400:
        raise HTTPException(status_code=r.status_code, detail="Failed to update exemplar")

    return {"status": "cleaned", "exemplar_id": exemplar_id}


@router.post("/exemplar/{exemplar_id}/approve")
async def approve_exemplar(
    exemplar_id: str,
    user: AuthenticatedUser = require_role("sme", "admin"),
):
    """Approve an exemplar — sets sme_cleaned=true. Requires cleaned text."""
    from app.services.exemplar_review import validate_exemplar_for_approval
    from app.db import get_service_headers
    import httpx as hx
    from app.config import settings

    # Fetch current exemplar
    headers = get_service_headers()
    async with hx.AsyncClient(timeout=15) as client:
        r = await client.get(
            f"{settings.supabase_url}/rest/v1/exemplar?select=clause_text,maturity_note,sme_cleaned&id=eq.{exemplar_id}&limit=1",
            headers=headers,
        )
    rows = r.json()
    if not rows:
        raise HTTPException(status_code=404, detail="Exemplar not found")

    exemplar = rows[0]
    if exemplar.get("sme_cleaned"):
        return {"status": "already_approved", "exemplar_id": exemplar_id}

    # Validate readiness
    error = validate_exemplar_for_approval(exemplar.get("clause_text"), exemplar.get("maturity_note"))
    if error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error)

    # Approve
    headers_write = {**get_service_headers(), "Content-Type": "application/json", "Prefer": "return=minimal"}
    async with hx.AsyncClient(timeout=15) as client:
        r = await client.patch(
            f"{settings.supabase_url}/rest/v1/exemplar?id=eq.{exemplar_id}",
            headers=headers_write,
            json={"sme_cleaned": True},
        )
    if r.status_code >= 400:
        raise HTTPException(status_code=r.status_code, detail="Failed to approve exemplar")

    return {"status": "approved", "exemplar_id": exemplar_id, "sme_cleaned": True}
