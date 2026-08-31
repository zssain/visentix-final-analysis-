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
    """List assessments pending SME review, each identified by what it IS.

    The queue used to return bare `assessment_review` rows, so the workbench had
    nothing to show but a UUID — an identifier with no meaning attached, which is
    the one thing DDR-011 says must never occupy a reader's primary surface. An
    SME could not tell which organization they were about to review, what was
    assessed, or how much work the item represented.

    Each row is enriched from data that already exists: the organization, what was
    submitted (URL / uploaded file / pasted text), when it was captured, and how
    many findings are decided out of the total. Nothing here is computed or
    inferred — a missing value renders as absent rather than a guess.
    """
    from app.db import supabase_rest_get

    queue = [asdict(r) for r in get_pending_queue()]
    if not queue:
        return queue

    def rows(resp) -> list[dict]:
        """Labels are a convenience; the QUEUE ITSELF is the SME's work list.
        A failed or unexpected enrichment response degrades to no labels — it
        must never take the queue down with it."""
        try:
            data = resp.json()
        except Exception:  # noqa: BLE001 — non-JSON error body
            return []
        return [d for d in data if isinstance(d, dict)] if isinstance(data, list) else []

    ids = ",".join(f'"{r["assessment_id"]}"' for r in queue)

    nr = await supabase_rest_get(
        "privacy_notice",
        select="notice_id,organization_id,source_url,capture_date,notice_version,"
               "intake_method,upload_filename",
        filters=f"notice_id=in.({ids})", limit=1000)
    notices = {str(n["notice_id"]): n for n in rows(nr) if n.get("notice_id")}

    org_ids = sorted({str(n["organization_id"]) for n in notices.values() if n.get("organization_id")})
    orgs: dict[str, dict] = {}
    if org_ids:
        o = ",".join(f'"{i}"' for i in org_ids)
        orr = await supabase_rest_get(
            "organization", select="organization_id,name,domain,industry",
            filters=f"organization_id=in.({o})", limit=1000)
        orgs = {str(x["organization_id"]): x for x in rows(orr) if x.get("organization_id")}

    fr = await supabase_rest_get(
        "risk_finding", select="finding_id,notice_id",
        filters=f"notice_id=in.({ids})", limit=5000)
    counts: dict[str, int] = {}
    for row in rows(fr):
        nid = str(row.get("notice_id") or "")
        if nid:
            counts[nid] = counts.get(nid, 0) + 1

    for r in queue:
        aid = r["assessment_id"]
        n = notices.get(aid) or {}
        org = orgs.get(str(n.get("organization_id") or "")) or {}
        reviews = r.get("finding_reviews")
        decided = sum(1 for fr_ in (reviews.values() if isinstance(reviews, dict) else [])
                      if isinstance(fr_, dict) and fr_.get("action"))
        r["organization_name"] = org.get("name")
        r["organization_domain"] = org.get("domain")
        r["industry"] = org.get("industry")
        # What was actually submitted — the SME's real handle on the item.
        r["source_label"] = (
            n.get("source_url")
            or n.get("upload_filename")
            or ("Pasted text" if n.get("intake_method") == "text" else None)
        )
        r["captured_at"] = n.get("capture_date")
        r["notice_version"] = n.get("notice_version")
        r["total_findings"] = counts.get(aid, 0)
        r["decided_findings"] = decided
    return queue


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
    """Approve an assessment, freezing the customer-visible snapshot.

    F06 AC-3 — the gate must actually gate. Under STRICT (the spec's
    `expert_review`, and the default), approval is REFUSED while any finding is
    still undecided. This was previously unenforced: approve committed the freeze
    without ever asking whether the findings had been reviewed, so the control
    that makes a report client-shippable passed assessments nobody had read.
    """
    if get_gate_mode() == GateMode.STRICT:
        pending = await _unreviewed_findings(assessment_id)
        if pending:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": "findings_pending_review",
                    "message": (
                        f"{len(pending)} finding(s) still need a decision before this "
                        "assessment can be approved."
                    ),
                    "pending_finding_ids": pending,
                },
            )
    try:
        review = approve_assessment(assessment_id, user.user_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    # F05: assemble + FREEZE recommendation evidence stacks at approval (once,
    # idempotent → DIR-010 byte-identity). Never fails the approval.
    from app.services.evidence import freeze_evidence_on_approval
    await freeze_evidence_on_approval(assessment_id)
    return asdict(review)


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


# NOTE: this catch-all dynamic GET is registered LAST so it never shadows the
# static-path routes above (/queue, /gate-mode, /exemplars). FastAPI matches in
# registration order — a GET /{assessment_id} declared earlier would swallow
# GET /review/gate-mode and GET /review/exemplars (Stage-3 routing fix).
async def _unreviewed_findings(assessment_id: str) -> list[str]:
    """Finding ids for this assessment with no SME decision recorded.

    A finding that exists in the database but carries no decision is exactly the
    case the old code could not see, because it never fetched per-assessment
    findings at all (see review_findings below).
    """
    from app.db import supabase_rest_get
    r = await supabase_rest_get(
        "risk_finding", select="finding_id",
        filters=f"notice_id=eq.{assessment_id}", limit=500)
    ids = [str(row["finding_id"]) for row in (r.json() or []) if row.get("finding_id")]
    review = get_or_create_review(assessment_id)
    return [fid for fid in ids
            if not (review.finding_reviews.get(fid) and review.finding_reviews[fid].action)]


@router.get("/{assessment_id}/findings")
async def review_findings(
    assessment_id: str,
    user: AuthenticatedUser = require_role("sme", "admin"),
):
    """Findings for ONE assessment, each with its real cited clause evidence and
    the SME's current decision.

    Why this exists (FUNC-001): the workbench previously called `GET /findings/`,
    which for an SME returns every organization's findings ordered by score and
    capped at 200, then filtered client-side by notice_id. An assessment whose
    findings fell outside that global top-200 rendered as an EMPTY finding list
    while the Approve button stayed live — the review gate could pass an
    assessment whose findings were never shown. This endpoint is scoped to the
    one assessment and is not truncated by anyone else's scores.

    Evidence comes from the `finding_clause` link table — the same citation the
    report uses — never "some clause in the same domain".
    """
    from app.db import supabase_rest_get

    r = await supabase_rest_get(
        "risk_finding",
        select="finding_id,finding_type_code,severity,score,domain,confidence_score,"
               "notice_id,formula_version_id,benchmark_deviation_score",
        filters=f"notice_id=eq.{assessment_id}",
        limit=500,
    )
    findings = r.json() or []

    finding_ids = [str(f["finding_id"]) for f in findings if f.get("finding_id")]
    clause_map: dict[str, list[str]] = {}
    if finding_ids:
        ids = ",".join(f'"{fid}"' for fid in finding_ids)
        lr = await supabase_rest_get(
            "finding_clause", select="finding_id,clause_id",
            filters=f"finding_id=in.({ids})", limit=2000)
        for link in lr.json() or []:
            clause_map.setdefault(str(link["finding_id"]), []).append(str(link["clause_id"]))

    clause_ids = sorted({cid for ids_ in clause_map.values() for cid in ids_})
    clauses: dict[str, dict] = {}
    if clause_ids:
        chunk = ",".join(f'"{c}"' for c in clause_ids)
        cr = await supabase_rest_get(
            "disclosure_clause", select="clause_id,raw_text,normalized_text,category,category_v2",
            filters=f"clause_id=in.({chunk})", limit=2000)
        for row in cr.json() or []:
            clauses[str(row["clause_id"])] = row

    review = get_or_create_review(assessment_id)
    out = []
    for f in sorted(findings, key=lambda x: str(x.get("finding_type_code") or "")):
        fid = str(f.get("finding_id") or "")
        fr = review.finding_reviews.get(fid)
        evidence = []
        for cid in clause_map.get(fid, []):
            row = clauses.get(cid)
            if not row:
                continue
            evidence.append({
                "clause_id": cid,
                "text": row.get("raw_text") or row.get("normalized_text") or "",
                "domain": row.get("category_v2") or row.get("category"),
            })
        out.append({
            **f,
            # Honest absence: a finding with no linked clause says so; it is never
            # backfilled with an unrelated clause from the same domain.
            "evidence": evidence,
            "decision": fr.action.value if fr and fr.action else None,
        })

    reviewed = sum(1 for f in out if f["decision"])
    return {
        "assessment_id": assessment_id,
        "status": review.status.value,
        "findings": out,
        "reviewed_count": reviewed,
        "total_count": len(out),
        "all_reviewed": len(out) > 0 and reviewed == len(out),
    }


@router.get("/{assessment_id}")
async def review_assessment(
    assessment_id: str,
    user: AuthenticatedUser = require_role("sme", "admin"),
):
    """View an assessment's findings and review state."""
    review = get_or_create_review(assessment_id)
    return asdict(review)
