"""QA-011 — server-side intake job state for asynchronous assessment intake.

Backed by the `assessment_job` table (migration 0043). Progress lives here, in
SERVER state, so a browser refresh recovers it. All access is via the
service-role REST client; the `/assessments/{id}/status` endpoint enforces org
ownership in app code (the table is RLS-deny-by-default, backend-only).

If the table isn't present yet (0043 not applied to the environment), these
helpers surface a clear error the caller turns into an honest failure — never a
fabricated success.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from app.db import supabase_rest_get, supabase_rest_patch, supabase_rest_post

# Fine-grained pipeline stages (server-authoritative). The intake POST path ends
# at `complete`; `awaiting_review`/`generating_report` are valid downstream states
# the status endpoint may also report.
STAGES = (
    "queued", "fetching", "extracting", "segmenting", "classifying",
    "profiling", "benchmarking", "scoring", "generating_findings",
    "awaiting_review", "generating_report", "complete", "failed",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def find_by_idempotency_key(key: str | None) -> dict | None:
    if not key:
        return None
    r = await supabase_rest_get(
        "assessment_job", select="*", filters=f"idempotency_key=eq.{key}", limit=1)
    rows = r.json() if r.status_code == 200 else []
    return rows[0] if rows else None


async def create_job(*, organization_id: str | None, created_by: str | None,
                     idempotency_key: str | None = None) -> dict:
    """Create a queued job. On an idempotency-key race (unique-index conflict),
    return the existing job instead of creating a duplicate."""
    job_id = str(uuid4())
    payload = {
        "job_id": job_id,
        "organization_id": organization_id,
        "created_by": created_by,
        "idempotency_key": idempotency_key,
        "status": "queued",
        "stage": "queued",
        "created_at": _now(),
        "updated_at": _now(),
    }
    r = await supabase_rest_post("assessment_job", payload)
    if r.status_code == 409 and idempotency_key:
        existing = await find_by_idempotency_key(idempotency_key)
        if existing:
            return existing
    if r.status_code >= 400:
        raise RuntimeError(f"could not create assessment_job (HTTP {r.status_code})")
    return payload


async def set_stage(job_id: str, stage: str, *, status: str = "running") -> None:
    await supabase_rest_patch(
        "assessment_job", f"job_id=eq.{job_id}",
        {"stage": stage, "status": status, "updated_at": _now()})


async def complete_job(job_id: str, *, assessment_id: str | None, result: dict) -> None:
    await supabase_rest_patch(
        "assessment_job", f"job_id=eq.{job_id}",
        {"status": "complete", "stage": "complete", "assessment_id": assessment_id,
         "result": result, "updated_at": _now()})


async def fail_job(job_id: str, error: str) -> None:
    await supabase_rest_patch(
        "assessment_job", f"job_id=eq.{job_id}",
        {"status": "failed", "stage": "failed", "error": (error or "")[:2000],
         "updated_at": _now()})


async def get_job(job_id: str) -> dict | None:
    r = await supabase_rest_get(
        "assessment_job", select="*", filters=f"job_id=eq.{job_id}", limit=1)
    rows = r.json() if r.status_code == 200 else []
    return rows[0] if rows else None
