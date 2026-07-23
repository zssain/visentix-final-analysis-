"""Training label capture — logs SME corrections as fine-tuning data.

Every confirm/edit/dismiss writes a `training_label` ROW (the DB is the
authoritative store — see F06 persistence hardening). Writing is non-blocking:
failures are logged but never block the review flow.

No secrets or unrelated PII are captured — only finding-level data.
"""

from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

import httpx

from app.config import settings
from app.db import get_service_headers

log = logging.getLogger(__name__)

_TABLE = "training_label"
# Synthetic assessment ids used by tests — reset_labels() cleans these from the
# DB so live unit tests stay isolated. Also cleans anything captured this process.
_TEST_IDS = {"a1", "a2", "assess-1", "assess-2"}
_touched: set[str] = set()


def _base() -> str:
    return f"{settings.supabase_url}/rest/v1/{_TABLE}"


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
    """Capture a training label from an SME review action → one `training_label`
    row. Non-blocking: logs errors but never raises to the caller."""
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
        headers = {**get_service_headers(), "Content-Type": "application/json",
                   "Prefer": "return=minimal"}
        r = httpx.post(_base(), headers=headers, json={
            "id": label.id, "assessment_id": label.assessment_id,
            "finding_id": label.finding_id, "original": label.original,
            "corrected": label.corrected, "action": label.action,
            "field": label.field, "sme_user_id": label.sme_user_id,
            "created_at": label.created_at,
        }, timeout=15)
        if r.status_code >= 300:
            log.error("training_label insert failed: HTTP %d (non-blocking)", r.status_code)
            return None
        _touched.add(assessment_id)
        log.info("Training label captured: assessment=%s finding=%s action=%s",
                 assessment_id[:12], finding_id[:12], action)
        return label
    except Exception as e:  # noqa: BLE001 — capture must never break the review flow
        log.error("Failed to capture training label: %s (non-blocking)", e)
        return None


def get_labels(assessment_id: str | None = None) -> list[dict]:
    """Read training labels from the DB (source of truth), oldest first."""
    try:
        headers = get_service_headers()
        qs = "select=*&order=created_at.asc&limit=10000"
        if assessment_id:
            qs += f"&assessment_id=eq.{assessment_id}"
        r = httpx.get(f"{_base()}?{qs}", headers=headers, timeout=15)
        return r.json() if r.status_code < 300 else []
    except Exception as e:  # noqa: BLE001
        log.error("get_labels failed: %s", e)
        return []


def get_training_stats() -> dict:
    """Compute training stats for the admin dashboard from the DB."""
    labels = get_labels()
    by_action = Counter(l.get("action") for l in labels)
    by_domain = Counter((l.get("original") or {}).get("domain", "unknown") for l in labels)
    by_month = Counter(l.get("created_at", "")[:7] for l in labels if l.get("created_at"))
    return {
        "total_labels": len(labels),
        "by_action": dict(by_action),
        "by_domain": dict(by_domain),
        "by_month": dict(by_month),
    }


def reset_labels():
    """Delete this process's + known test assessment labels from the DB (testing
    only — production never calls this)."""
    ids = _touched | _TEST_IDS
    headers = {**get_service_headers(), "Prefer": "return=minimal"}
    quoted = ",".join(f'"{i}"' for i in ids)
    try:
        httpx.delete(f"{_base()}?assessment_id=in.({quoted})", headers=headers, timeout=15)
    except Exception as e:  # noqa: BLE001
        log.error("reset_labels failed: %s", e)
    _touched.clear()
