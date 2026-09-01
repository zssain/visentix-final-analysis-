"""Background tasks — one system for every user-triggered long operation.

Generalized from `intake/jobs.py`, which was the only asynchronous path in the
product. Everything else either grew its own job concept or blocked the HTTP
request end to end.

Backed by `assessment_job` with a `kind` discriminator (migration 0049).
`assessment_id` stays intake's column and is simply null for other kinds; a
non-intake task reports what it produced through `result.result_id`.

`job_run` (scheduled cron work) is NOT part of this. Cron jobs have nobody
waiting on them, and a progress bar nobody is watching is a lie about what the
tracker is for.

Rule this module exists to keep: **a task that outlives a reader's patience
still reports honestly.** A stage is only ever set from real progress; nothing
here advances a stage on a timer.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import uuid4

from app.db import supabase_rest_get, supabase_rest_patch, supabase_rest_post

log = logging.getLogger(__name__)

TABLE = "assessment_job"

#: Kinds this module accepts. Mirrored on the client in web/src/jobs/tasks.ts —
#: the two lists must agree or the tracker cannot resolve a status URL.
KINDS = ("intake", "reassessment", "quarterly_build", "report_pdf")

#: Ordered stages per kind. Mirrored client-side ONLY to compute progress; an
#: unrecognised stage renders indeterminate there rather than guessing a
#: percentage (Hard Rule 7). Adding a stage here means adding it there too.
STAGES: dict[str, tuple[str, ...]] = {
    "intake": (
        "queued", "fetching", "extracting", "segmenting", "classifying",
        "profiling", "benchmarking", "scoring", "generating_findings",
    ),
    "reassessment": ("queued", "loading_notices", "scoring", "writing_snapshots"),
    "quarterly_build": ("queued", "aggregating", "suppressing", "rendering"),
    "report_pdf": ("queued", "rendering"),
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def create(
    *,
    kind: str,
    organization_id: str | None = None,
    created_by: str | None = None,
    idempotency_key: str | None = None,
) -> dict:
    """Create a queued task.

    On an idempotency-key race (unique-index conflict) the EXISTING task is
    returned rather than a duplicate created — a double-submit must never start
    the same expensive work twice.
    """
    if kind not in KINDS:
        raise ValueError(f"unknown task kind: {kind!r}")

    task_id = str(uuid4())
    payload = {
        "job_id": task_id,
        "kind": kind,
        "organization_id": organization_id,
        "created_by": created_by,
        "idempotency_key": idempotency_key,
        "status": "queued",
        "stage": "queued",
        "created_at": _now(),
        "updated_at": _now(),
    }
    r = await supabase_rest_post(TABLE, payload)
    if r.status_code == 409 and idempotency_key:
        existing = await find_by_idempotency_key(idempotency_key)
        if existing:
            return {**existing, "_idempotent_replay": True}
    if r.status_code >= 400:
        raise RuntimeError(f"could not create {TABLE} (HTTP {r.status_code})")
    return payload


async def find_by_idempotency_key(key: str | None) -> dict | None:
    if not key:
        return None
    r = await supabase_rest_get(
        TABLE, select="*", filters=f"idempotency_key=eq.{key}", limit=1)
    rows = r.json() if r.status_code == 200 else []
    return rows[0] if rows else None


async def set_stage(task_id: str, stage: str, *, status: str = "running") -> None:
    await supabase_rest_patch(
        TABLE, f"job_id=eq.{task_id}",
        {"stage": stage, "status": status, "updated_at": _now()})


async def complete(task_id: str, *, result: dict, result_id: str | None = None) -> None:
    """Mark a task complete.

    `result_id` is what the reader can open next — a snapshot id, a report id.
    It is stored inside `result` so the shape stays kind-agnostic; only intake
    also writes the dedicated `assessment_id` column, which predates this module.
    """
    patch = {
        "status": "complete", "stage": "complete",
        "result": {**result, "result_id": result_id} if result_id else result,
        "updated_at": _now(),
    }
    await supabase_rest_patch(TABLE, f"job_id=eq.{task_id}", patch)


async def fail(task_id: str, error: str) -> None:
    await supabase_rest_patch(
        TABLE, f"job_id=eq.{task_id}",
        {"status": "failed", "stage": "failed", "error": (error or "")[:2000],
         "updated_at": _now()})


async def get(task_id: str) -> dict | None:
    r = await supabase_rest_get(
        TABLE, select="*", filters=f"job_id=eq.{task_id}", limit=1)
    rows = r.json() if r.status_code == 200 else []
    return rows[0] if rows else None


def to_status(row: dict) -> dict:
    """Shape a row into the status payload the tracker polls.

    Deliberately narrow: status, stage, an optional openable id, and an error.
    The tracker must not be able to read anything it should not, and a status
    endpoint is the easiest place to leak a whole row by accident.
    """
    result = row.get("result") or {}
    return {
        "status": row.get("status") or "queued",
        "stage": row.get("stage") or "queued",
        "kind": row.get("kind") or "intake",
        "result_id": result.get("result_id") or row.get("assessment_id"),
        "error": row.get("error"),
    }
