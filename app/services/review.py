"""SME review service — status model, finding actions, gate mode.

Status flow: draft → in_review → approved
Gate modes: strict | instant_draft (default) | client_reviews
  (OD-08: canonical enum names vs the spec's instant_draft/expert_review are
   still open — do NOT rename here.)

Finding actions: confirm | edit | dismiss. Dismissed findings are excluded from
the customer-visible report. Approval freezes the customer-visible snapshot.

F06 persistence hardening: the DATABASE is the authoritative store.
  review state       → assessment_review
  VCI analyst queue  → review_queue_item
  gate mode          → platform_setting (key=gate_mode)
A thin process cache write-through keeps same-process reads fast; on a cache
miss (e.g. a fresh process after restart) reads reload from the DB.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

import httpx

from app.config import settings
from app.db import get_service_headers


class AssessmentStatus(str, Enum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    APPROVED = "approved"


class GateMode(str, Enum):
    STRICT = "strict"                  # Customer sees nothing until approved (== spec "expert_review")
    INSTANT_DRAFT = "instant_draft"    # Customer sees draft + banner
    CLIENT_REVIEWS = "client_reviews"  # Client can see and comment on draft


class FindingAction(str, Enum):
    CONFIRM = "confirm"
    EDIT = "edit"
    DISMISS = "dismiss"


# Safe-by-default: when platform_setting has no gate_mode row (fresh prod), the
# gate is STRICT — customers see nothing until an SME approves (spec: expert_review).
# A pilot must never default to showing drafts. STRICT is the canonical name for
# expert_review; the enum-naming reconciliation is OD-08 (open). (Stage-3 D1/C5.)
DEFAULT_GATE_MODE = GateMode.STRICT


@dataclass
class FindingReview:
    finding_id: str
    action: FindingAction | None = None
    edited_fields: dict[str, Any] = field(default_factory=dict)
    reviewer_id: str = ""
    reviewed_at: str = ""


@dataclass
class AssessmentReview:
    assessment_id: str
    status: AssessmentStatus = AssessmentStatus.DRAFT
    finding_reviews: dict[str, FindingReview] = field(default_factory=dict)
    approved_by: str = ""
    approved_at: str = ""


# ── Process write-through cache (DB is the source of truth) ──────────
_reviews: dict[str, AssessmentReview] = {}
_gate_mode_cache: GateMode | None = None

# Synthetic ids used by tests — reset_reviews() cleans these from the DB.
_TEST_IDS = {"a1", "a2", "assess-1", "assess-2"}
_touched: set[str] = set()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _url(table: str) -> str:
    return f"{settings.supabase_url}/rest/v1/{table}"


# ── Serialization ───────────────────────────────────────────────────

def _review_to_row(r: AssessmentReview) -> dict:
    return {
        "assessment_id": r.assessment_id,
        "status": r.status.value,
        "finding_reviews": {
            fid: {
                "action": fr.action.value if fr.action else None,
                "edited_fields": fr.edited_fields,
                "reviewer_id": fr.reviewer_id,
                "reviewed_at": fr.reviewed_at,
            } for fid, fr in r.finding_reviews.items()
        },
        "approved_by": r.approved_by or None,
        "approved_at": r.approved_at or None,
        "updated_at": _now(),
    }


def _row_to_review(row: dict) -> AssessmentReview:
    r = AssessmentReview(
        assessment_id=row["assessment_id"],
        status=AssessmentStatus(row["status"]),
        approved_by=row.get("approved_by") or "",
        approved_at=row.get("approved_at") or "",
    )
    for fid, d in (row.get("finding_reviews") or {}).items():
        r.finding_reviews[fid] = FindingReview(
            finding_id=fid,
            action=FindingAction(d["action"]) if d.get("action") else None,
            edited_fields=d.get("edited_fields") or {},
            reviewer_id=d.get("reviewer_id", ""),
            reviewed_at=d.get("reviewed_at", ""),
        )
    return r


def _persist_review(r: AssessmentReview) -> None:
    headers = {**get_service_headers(), "Content-Type": "application/json",
               "Prefer": "resolution=merge-duplicates,return=minimal"}
    resp = httpx.post(f"{_url('assessment_review')}?on_conflict=assessment_id",
                      headers=headers, json=_review_to_row(r), timeout=15)
    if resp.status_code >= 300:
        raise RuntimeError(f"assessment_review persist failed: HTTP {resp.status_code}")
    _touched.add(r.assessment_id)
    _reviews[r.assessment_id] = r


def _load_review(assessment_id: str) -> AssessmentReview | None:
    headers = get_service_headers()
    r = httpx.get(f"{_url('assessment_review')}?select=*&assessment_id=eq.{assessment_id}&limit=1",
                  headers=headers, timeout=15)
    rows = r.json() if r.status_code < 300 else []
    return _row_to_review(rows[0]) if rows else None


# ── Gate mode (platform_setting key=gate_mode) ──────────────────────

def get_gate_mode() -> GateMode:
    global _gate_mode_cache
    if _gate_mode_cache is not None:
        return _gate_mode_cache
    r = httpx.get(f"{_url('platform_setting')}?select=value&key=eq.gate_mode&limit=1",
                  headers=get_service_headers(), timeout=15)
    rows = r.json() if r.status_code < 300 else []
    _gate_mode_cache = GateMode(rows[0]["value"]) if rows else DEFAULT_GATE_MODE
    return _gate_mode_cache


def set_gate_mode(mode: GateMode) -> None:
    global _gate_mode_cache
    headers = {**get_service_headers(), "Content-Type": "application/json",
               "Prefer": "resolution=merge-duplicates,return=minimal"}
    httpx.post(f"{_url('platform_setting')}?on_conflict=key", headers=headers, json={
        "key": "gate_mode", "value": mode.value, "updated_at": _now(),
    }, timeout=15)
    _gate_mode_cache = mode


# ── Review state ────────────────────────────────────────────────────

def get_or_create_review(assessment_id: str) -> AssessmentReview:
    if assessment_id in _reviews:
        return _reviews[assessment_id]
    existing = _load_review(assessment_id)
    if existing is not None:
        _reviews[assessment_id] = existing
        return existing
    review = AssessmentReview(assessment_id=assessment_id)
    _persist_review(review)
    return review


def get_review(assessment_id: str) -> AssessmentReview | None:
    if assessment_id in _reviews:
        return _reviews[assessment_id]
    existing = _load_review(assessment_id)
    if existing is not None:
        _reviews[assessment_id] = existing
    return existing


def submit_finding_action(
    assessment_id: str,
    finding_id: str,
    action: FindingAction,
    edited_fields: dict | None = None,
    reviewer_id: str = "",
) -> FindingReview:
    """Submit a review action on a finding."""
    review = get_or_create_review(assessment_id)

    if review.status == AssessmentStatus.APPROVED:
        raise ValueError("Cannot modify findings on an approved assessment")

    if review.status == AssessmentStatus.DRAFT:
        review.status = AssessmentStatus.IN_REVIEW

    previous = review.finding_reviews.get(finding_id)
    original_state = {
        "finding_id": finding_id,
        "action": previous.action.value if previous and previous.action else None,
    }

    fr = FindingReview(
        finding_id=finding_id,
        action=action,
        edited_fields=edited_fields or {},
        reviewer_id=reviewer_id,
        reviewed_at=_now(),
    )
    review.finding_reviews[finding_id] = fr
    _persist_review(review)

    # Capture training label (non-blocking)
    from app.services.training import capture_label
    capture_label(
        assessment_id=assessment_id,
        finding_id=finding_id,
        action=action.value,
        original=original_state,
        corrected={"action": action.value, **(edited_fields or {})},
        field="finding",
        sme_user_id=reviewer_id,
    )

    return fr


def approve_assessment(
    assessment_id: str,
    approver_id: str,
    snapshot_id: str | None = None,
) -> AssessmentReview:
    """Approve an assessment. When a snapshot_id is supplied, approval AND the
    report_snapshot freeze commit in ONE transaction via approve_and_freeze()
    — a failed freeze rolls back the approval (never half-approved)."""
    review = get_or_create_review(assessment_id)

    if review.status == AssessmentStatus.APPROVED:
        raise ValueError("Assessment already approved")

    headers = {**get_service_headers(), "Content-Type": "application/json",
               "Prefer": "return=minimal"}
    resp = httpx.post(f"{_url('rpc/approve_and_freeze')}", headers=headers, json={
        "p_assessment_id": assessment_id,
        "p_approver": approver_id,
        "p_snapshot_id": snapshot_id,
    }, timeout=15)
    if resp.status_code >= 300:
        # Atomic: nothing was committed (approval rolled back with the freeze).
        raise RuntimeError(f"approve_and_freeze failed: HTTP {resp.status_code}")

    review.status = AssessmentStatus.APPROVED
    review.approved_by = approver_id
    review.approved_at = _now()
    _reviews[assessment_id] = review
    _touched.add(assessment_id)

    # F20: freeze partner branding onto the snapshot AT APPROVAL (when everything
    # else freezes). No-op for non-partner assessments; never fails the approval.
    from app.services.partner import record_branding_on_approval
    record_branding_on_approval(assessment_id, snapshot_id)

    return review


def get_active_findings(assessment_id: str, all_findings: list[dict]) -> list[dict]:
    """Return findings excluding dismissed ones (with edits applied)."""
    review = get_review(assessment_id)
    if not review:
        return all_findings

    active = []
    for f in all_findings:
        fid = f.get("finding_id") or f.get("code", "")
        fr = review.finding_reviews.get(fid)
        if fr and fr.action == FindingAction.DISMISS:
            continue
        if fr and fr.action == FindingAction.EDIT and fr.edited_fields:
            f = {**f, **fr.edited_fields}
        active.append(f)
    return active


def customer_can_view(assessment_id: str) -> tuple[bool, str]:
    """Check if the customer can view the report under current gate_mode."""
    review = get_review(assessment_id)
    status = review.status if review else AssessmentStatus.DRAFT
    mode = get_gate_mode()

    if status == AssessmentStatus.APPROVED:
        return True, ""
    if mode == GateMode.STRICT:
        return False, ""
    if mode == GateMode.INSTANT_DRAFT:
        return True, "DRAFT — pending expert review. Scores and findings may change."
    if mode == GateMode.CLIENT_REVIEWS:
        return True, "DRAFT — open for review. Your feedback is welcome."
    return False, ""


def get_pending_queue() -> list[AssessmentReview]:
    """Return assessments that need review (not yet approved)."""
    r = httpx.get(f"{_url('assessment_review')}?select=*&status=neq.approved&limit=1000",
                  headers=get_service_headers(), timeout=15)
    rows = r.json() if r.status_code < 300 else []
    return [_row_to_review(row) for row in rows]


# ── VCI-based analyst review queue (review_queue_item) ──────────────

def flag_low_vci_object(
    assessment_id: str,
    object_type: str,
    vci_score: float,
    score: float,
) -> None:
    """Flag a derived object for analyst review based on VCI threshold."""
    from app.services.products.mapping import needs_analyst_review
    if not needs_analyst_review(vci_score):
        return
    headers = {**get_service_headers(), "Content-Type": "application/json",
               "Prefer": "resolution=merge-duplicates,return=minimal"}
    httpx.post(f"{_url('review_queue_item')}?on_conflict=assessment_id,object_type",
               headers=headers, json={
                   "assessment_id": assessment_id, "object_type": object_type,
                   "vci_score": vci_score, "score": score,
                   "is_definitive": vci_score >= 40, "needs_review": True, "cleared": False,
               }, timeout=15)
    _touched.add(assessment_id)


def clear_low_vci_object(assessment_id: str, object_type: str) -> None:
    """SME/admin clears a low-VCI object after analyst review."""
    headers = {**get_service_headers(), "Content-Type": "application/json",
               "Prefer": "return=minimal"}
    httpx.patch(
        f"{_url('review_queue_item')}?assessment_id=eq.{assessment_id}&object_type=eq.{object_type}",
        headers=headers, json={"cleared": True, "cleared_at": _now()}, timeout=15)


def get_low_vci_objects(assessment_id: str) -> list[dict]:
    """Return objects pending analyst review for an assessment."""
    r = httpx.get(
        f"{_url('review_queue_item')}?select=object_type,vci_score,score,needs_review,is_definitive"
        f"&assessment_id=eq.{assessment_id}&cleared=eq.false",
        headers=get_service_headers(), timeout=15)
    return r.json() if r.status_code < 300 else []


def get_analyst_review_banner(assessment_id: str) -> str | None:
    """Return a banner message if any objects are pending analyst review."""
    pending = get_low_vci_objects(assessment_id)
    if not pending:
        return None
    types = [o["object_type"].replace("_", " ").title() for o in pending]
    return (
        f"Some scores have lower confidence and are pending analyst review: "
        f"{', '.join(types)}. These should not be presented as definitive."
    )


# ── Test helpers ────────────────────────────────────────────────────

def _clear_caches() -> None:
    """Drop the in-process caches WITHOUT touching the DB — simulates a fresh
    process (restart). Reads then reload from the DB."""
    global _gate_mode_cache
    _reviews.clear()
    _gate_mode_cache = None


def reset_reviews():
    """Clear caches AND delete this process's + known-test review rows from the
    DB, and reset gate mode to default (testing only — never called in prod)."""
    _clear_caches()
    ids = _touched | _TEST_IDS
    quoted = ",".join(f'"{i}"' for i in ids)
    headers = {**get_service_headers(), "Prefer": "return=minimal"}
    for table in ("assessment_review", "review_queue_item"):
        try:
            httpx.delete(f"{_url(table)}?assessment_id=in.({quoted})", headers=headers, timeout=15)
        except Exception:  # noqa: BLE001
            pass
    try:
        httpx.delete(f"{_url('platform_setting')}?key=eq.gate_mode", headers=headers, timeout=15)
    except Exception:  # noqa: BLE001
        pass
    _touched.clear()
