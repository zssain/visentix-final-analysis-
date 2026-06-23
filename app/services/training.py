"""Training label capture — logs SME corrections as fine-tuning data.

Every confirm/edit/dismiss writes a training_label row capturing the
before/after state. Writing is non-blocking: failures are logged but
never block the review flow.

No secrets or unrelated PII are captured — only finding-level data.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

log = logging.getLogger(__name__)

# In-memory store for MVP (would be DB-backed via Supabase REST in production)
_labels: list[dict] = []


@dataclass
class TrainingLabel:
    id: str
    assessment_id: str
    finding_id: str
    original: dict
    corrected: dict
    action: str
    field: str
    sme_user_id: str
    created_at: str


def capture_label(
    assessment_id: str,
    finding_id: str,
    action: str,
    original: dict | None = None,
    corrected: dict | None = None,
    field: str = "finding",
    sme_user_id: str = "",
) -> TrainingLabel | None:
    """Capture a training label from an SME review action.

    Non-blocking: logs errors but never raises to the caller.
    """
    try:
        label = TrainingLabel(
            id=str(uuid4()),
            assessment_id=assessment_id,
            finding_id=finding_id,
            original=original or {},
            corrected=corrected or {},
            action=action,
            field=field,
            sme_user_id=sme_user_id,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

        _labels.append({
            "id": label.id,
            "assessment_id": label.assessment_id,
            "finding_id": label.finding_id,
            "original": label.original,
            "corrected": label.corrected,
            "action": label.action,
            "field": label.field,
            "sme_user_id": label.sme_user_id,
            "created_at": label.created_at,
        })

        log.info(
            "Training label captured: assessment=%s finding=%s action=%s",
            assessment_id[:12], finding_id[:12], action,
        )
        return label

    except Exception as e:
        log.error("Failed to capture training label: %s (non-blocking)", e)
        return None


def get_labels(assessment_id: str | None = None) -> list[dict]:
    """Get all training labels, optionally filtered by assessment."""
    if assessment_id:
        return [l for l in _labels if l["assessment_id"] == assessment_id]
    return list(_labels)


def get_training_stats() -> dict:
    """Compute training stats for the admin dashboard."""
    from collections import Counter

    by_action = Counter(l["action"] for l in _labels)

    # Domain extraction from original/corrected
    by_domain = Counter()
    for l in _labels:
        domain = (l.get("original") or {}).get("domain", "unknown")
        by_domain[domain] += 1

    # By month
    by_month = Counter()
    for l in _labels:
        ts = l.get("created_at", "")[:7]  # YYYY-MM
        if ts:
            by_month[ts] += 1

    return {
        "total_labels": len(_labels),
        "by_action": dict(by_action),
        "by_domain": dict(by_domain),
        "by_month": dict(by_month),
    }


def reset_labels():
    """Reset labels (for testing only)."""
    _labels.clear()
