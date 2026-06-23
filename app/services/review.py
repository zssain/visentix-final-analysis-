"""SME review service — status model, finding actions, gate mode.

Status flow: draft → in_review → approved
Gate modes: strict | instant_draft (default) | client_reviews

Finding actions: confirm | edit | dismiss
Dismissed findings are excluded from the customer-visible report.
Approval freezes the customer-visible snapshot.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class AssessmentStatus(str, Enum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    APPROVED = "approved"


class GateMode(str, Enum):
    STRICT = "strict"           # Customer sees nothing until approved
    INSTANT_DRAFT = "instant_draft"  # Customer sees draft + banner (DEFAULT)
    CLIENT_REVIEWS = "client_reviews"  # Client can see and comment on draft


class FindingAction(str, Enum):
    CONFIRM = "confirm"
    EDIT = "edit"
    DISMISS = "dismiss"


DEFAULT_GATE_MODE = GateMode.INSTANT_DRAFT


@dataclass
class FindingReview:
    """Review state for a single finding."""

    finding_id: str
    action: FindingAction | None = None
    edited_fields: dict[str, Any] = field(default_factory=dict)
    reviewer_id: str = ""
    reviewed_at: str = ""


@dataclass
class AssessmentReview:
    """Review state for an assessment."""

    assessment_id: str
    status: AssessmentStatus = AssessmentStatus.DRAFT
    finding_reviews: dict[str, FindingReview] = field(default_factory=dict)
    approved_by: str = ""
    approved_at: str = ""


# In-memory store for MVP (would be DB-backed in production)
_reviews: dict[str, AssessmentReview] = {}
_gate_mode: GateMode = DEFAULT_GATE_MODE


def get_gate_mode() -> GateMode:
    return _gate_mode


def set_gate_mode(mode: GateMode) -> None:
    global _gate_mode
    _gate_mode = mode


def get_or_create_review(assessment_id: str) -> AssessmentReview:
    if assessment_id not in _reviews:
        _reviews[assessment_id] = AssessmentReview(assessment_id=assessment_id)
    return _reviews[assessment_id]


def get_review(assessment_id: str) -> AssessmentReview | None:
    return _reviews.get(assessment_id)


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

    # Move to in_review on first action
    if review.status == AssessmentStatus.DRAFT:
        review.status = AssessmentStatus.IN_REVIEW

    # Capture previous state for training label
    previous = review.finding_reviews.get(finding_id)
    original_state = {"finding_id": finding_id, "action": previous.action if previous else None}

    fr = FindingReview(
        finding_id=finding_id,
        action=action,
        edited_fields=edited_fields or {},
        reviewer_id=reviewer_id,
        reviewed_at=datetime.now(timezone.utc).isoformat(),
    )
    review.finding_reviews[finding_id] = fr

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
) -> AssessmentReview:
    """Approve an assessment, freezing the customer-visible snapshot."""
    review = get_or_create_review(assessment_id)

    if review.status == AssessmentStatus.APPROVED:
        raise ValueError("Assessment already approved")

    review.status = AssessmentStatus.APPROVED
    review.approved_by = approver_id
    review.approved_at = datetime.now(timezone.utc).isoformat()
    return review


def get_active_findings(assessment_id: str, all_findings: list[dict]) -> list[dict]:
    """Return findings excluding dismissed ones."""
    review = get_review(assessment_id)
    if not review:
        return all_findings

    active = []
    for f in all_findings:
        fid = f.get("finding_id") or f.get("code", "")
        fr = review.finding_reviews.get(fid)
        if fr and fr.action == FindingAction.DISMISS:
            continue

        # Apply edits if any
        if fr and fr.action == FindingAction.EDIT and fr.edited_fields:
            f = {**f, **fr.edited_fields}

        active.append(f)
    return active


def customer_can_view(assessment_id: str) -> tuple[bool, str]:
    """Check if the customer can view the report under current gate_mode.

    Returns (can_view, banner_text).
    """
    review = get_review(assessment_id)
    status = review.status if review else AssessmentStatus.DRAFT
    mode = get_gate_mode()

    if status == AssessmentStatus.APPROVED:
        return True, ""

    if mode == GateMode.STRICT:
        return False, ""

    if mode == GateMode.INSTANT_DRAFT:
        banner = "DRAFT — pending expert review. Scores and findings may change."
        return True, banner

    if mode == GateMode.CLIENT_REVIEWS:
        banner = "DRAFT — open for review. Your feedback is welcome."
        return True, banner

    return False, ""


def get_pending_queue() -> list[AssessmentReview]:
    """Return assessments that need review (not yet approved)."""
    return [
        r for r in _reviews.values()
        if r.status != AssessmentStatus.APPROVED
    ]


def reset_reviews():
    """Reset all reviews (for testing only)."""
    _reviews.clear()
    global _gate_mode
    _gate_mode = DEFAULT_GATE_MODE
