"""F07 job framework — job_run lifecycle, concurrency guard, platform_setting config.

Every job body: (1) open job_run(running), (2) idempotent batched work, (3) close
job_run with counts. A job is skipped if the same job_name is already running.
Cadence + enabled state live in platform_setting keys job.<name>.cron / .enabled
(SLA defaults below), so ops can toggle without a deploy.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Awaitable, Callable
from uuid import uuid4

from app.db import supabase_rest_get, supabase_rest_patch, supabase_rest_post

log = logging.getLogger(__name__)

# SLA defaults (Derived Catalog "Recurring Update Operating Model"): cron + enabled.
JOB_DEFAULTS: dict[str, dict] = {
    "monitor_notices": {"cron": "0 2 * * *", "enabled": True},      # daily 02:00 UTC
    "pull_regulators": {"cron": "0 3 * * 1", "enabled": True},      # weekly Mon 03:00
    "refresh_benchmarks": {"cron": "0 4 1 * *", "enabled": True},   # monthly 1st 04:00
}

# BACK-001: a job_run left in `status=running` past this wall-clock budget is
# treated as DEAD (orphaned). A worker SIGKILL'd/OOM'd between _open_run and
# _close_run can never close its row (a `finally` cannot survive SIGKILL), so
# without a staleness bound `is_running` would report "running" forever and
# monitor_notices/pull_regulators/refresh_benchmarks would be skipped on every
# subsequent tick — monitoring stops silently. Per-job override, else default.
DEFAULT_MAX_RUNTIME_S = 3600  # 1 hour
JOB_MAX_RUNTIME_S: dict[str, int] = {
    "monitor_notices": 3600,      # daily corpus diff
    "pull_regulators": 3600,      # weekly regulator pull
    "refresh_benchmarks": 7200,   # monthly cohort rebuild — allow longer
}


def _max_runtime_s(job_name: str) -> int:
    return JOB_MAX_RUNTIME_S.get(job_name, DEFAULT_MAX_RUNTIME_S)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stale_cutoff_iso(job_name: str) -> str:
    """ISO timestamp before which a still-`running` row is considered orphaned."""
    return (datetime.now(timezone.utc) - timedelta(seconds=_max_runtime_s(job_name))).isoformat()


# ── platform_setting config ──────────────────────────────────

async def get_setting(key: str) -> str | None:
    r = await supabase_rest_get("platform_setting", select="value", filters=f"key=eq.{key}", limit=1)
    rows = r.json() if r.status_code == 200 else []
    return rows[0]["value"] if rows else None


async def set_setting(key: str, value: str, updated_by: str = "admin") -> None:
    await supabase_rest_post("platform_setting",
                             {"key": key, "value": value, "updated_at": _now()},
                             on_conflict="key", upsert=True)


async def job_config(job_name: str) -> dict:
    d = JOB_DEFAULTS.get(job_name, {"cron": "", "enabled": False})
    cron = await get_setting(f"job.{job_name}.cron") or d["cron"]
    enabled_raw = await get_setting(f"job.{job_name}.enabled")
    enabled = d["enabled"] if enabled_raw is None else (enabled_raw.lower() == "true")
    return {"job_name": job_name, "cron": cron, "enabled": enabled}


# ── job_run lifecycle ────────────────────────────────────────

async def emit_event(organization_id: str | None, event_type: str, *, prior=None,
                     current=None, payload: dict | None = None, severity: str | None = None,
                     source_id: str | None = None) -> str:
    """Insert one monitoring_event. event_type ∈ the four §2.8 values ONLY.

    Sets both `trigger_type` (read-layer vocabulary) and the additive
    `event_type`/`organization_id`/`payload` columns so old URL-scoped and new
    org-scoped readers both work. Returns the event_id.
    """
    assert event_type in ("notice_changed", "score_moved", "regulator_signal", "cohort_rebenchmarked")
    event_id = str(uuid4())
    await supabase_rest_post("monitoring_event", {
        "event_id": event_id, "trigger_type": event_type, "event_type": event_type,
        "organization_id": organization_id, "source_id": source_id,
        "prior_value": None if prior is None else str(prior),
        "current_value": None if current is None else str(current),
        "payload": payload, "severity": severity, "ts": _now(),
    })
    return event_id


async def is_running(job_name: str) -> bool:
    """True only if a job_run is running AND fresh (started within max runtime).

    BACK-001: a `running` row older than the job's max runtime is treated as dead
    (orphaned by SIGKILL/OOM) and does NOT count as live, so the job can run
    again. Stale rows are reclaimed by `reap_stale_runs`.
    """
    cutoff = _stale_cutoff_iso(job_name)
    r = await supabase_rest_get(
        "job_run", select="id",
        filters=f"job_name=eq.{job_name}&status=eq.running&started_at=gte.{cutoff}",
        limit=1)
    return bool(r.json()) if r.status_code == 200 else False


async def reap_stale_runs(job_name: str | None = None) -> int:
    """Mark orphaned `running` rows (older than max runtime) as `failed`.

    Returns the count reaped. Called at startup (startup reaper) and defensively
    before opening a new run, so a hard-crashed worker cannot permanently disable
    a job. Idempotent: a row already failed/succeeded is not matched.
    """
    names = [job_name] if job_name else list(JOB_DEFAULTS.keys())
    reaped = 0
    for name in names:
        cutoff = _stale_cutoff_iso(name)
        r = await supabase_rest_get(
            "job_run", select="id,started_at",
            filters=f"job_name=eq.{name}&status=eq.running&started_at=lt.{cutoff}",
            limit=100)
        rows = r.json() if r.status_code == 200 else []
        for row in rows:
            await supabase_rest_patch("job_run", f"id=eq.{row['id']}", {
                "status": "failed", "finished_at": _now(),
                "error": ("reaped: run exceeded max runtime "
                          f"({_max_runtime_s(name)}s) — orphaned (worker likely SIGKILL/OOM)"),
            })
            reaped += 1
        if rows:
            log.warning("reaped %d stale '%s' run(s) left in 'running'", len(rows), name)
    return reaped


async def stale_run_count(job_name: str | None = None) -> int:
    """Count `running` rows past their max runtime — surfaced on /admin/status."""
    names = [job_name] if job_name else list(JOB_DEFAULTS.keys())
    total = 0
    for name in names:
        cutoff = _stale_cutoff_iso(name)
        r = await supabase_rest_get(
            "job_run", select="id",
            filters=f"job_name=eq.{name}&status=eq.running&started_at=lt.{cutoff}",
            limit=1000)
        total += len(r.json()) if r.status_code == 200 else 0
    return total


async def _open_run(job_name: str, triggered_by: str) -> str:
    run_id = str(uuid4())
    await supabase_rest_post("job_run", {
        "id": run_id, "job_name": job_name, "status": "running",
        "triggered_by": triggered_by, "started_at": _now(),
    })
    return run_id


async def _close_run(run_id: str, status: str, processed: int, changed: int, error: str | None) -> None:
    await supabase_rest_patch("job_run", f"id=eq.{run_id}", {
        "status": status, "finished_at": _now(),
        "items_processed": processed, "items_changed": changed, "error": error,
    })


async def last_run(job_name: str) -> dict | None:
    r = await supabase_rest_get(
        "job_run",
        select="id,job_name,started_at,finished_at,status,items_processed,items_changed,error,triggered_by",
        filters=f"job_name=eq.{job_name}&order=started_at.desc", limit=1)
    rows = r.json() if r.status_code == 200 else []
    return rows[0] if rows else None


async def execute(job_name: str, triggered_by: str,
                  body: Callable[[str], Awaitable[tuple[int, int]]]) -> dict:
    """Run a job body under the job_run lifecycle + concurrency guard.

    body(run_id) -> (items_processed, items_changed). Returns a status dict.
    """
    await reap_stale_runs(job_name)  # BACK-001: reclaim orphaned runs before the guard
    if await is_running(job_name):
        log.info("job %s already running — skipping (%s)", job_name, triggered_by)
        return {"skipped": True, "reason": "already_running", "job_name": job_name}

    run_id = await _open_run(job_name, triggered_by)
    try:
        processed, changed = await body(run_id)
        await _close_run(run_id, "succeeded", processed, changed, None)
        log.info("job %s succeeded: processed=%d changed=%d", job_name, processed, changed)
        return {"job_run_id": run_id, "status": "succeeded",
                "items_processed": processed, "items_changed": changed}
    except Exception as e:  # noqa: BLE001 — record failure honestly, re-raise nothing
        log.exception("job %s failed", job_name)
        await _close_run(run_id, "failed", 0, 0, f"{type(e).__name__}: {e}")
        return {"job_run_id": run_id, "status": "failed", "error": str(e)}


async def trigger_background(job_name: str, body: Callable[[str], Awaitable[tuple[int, int]]],
                            triggered_by: str = "manual") -> str | None:
    """Open a job_run NOW (returns its id for a 202), run the body in the background.

    Returns None if the job is already running (concurrency guard)."""
    await reap_stale_runs(job_name)  # BACK-001: reclaim orphaned runs before the guard
    if await is_running(job_name):
        return None
    run_id = await _open_run(job_name, triggered_by)

    async def _bg() -> None:
        try:
            processed, changed = await body(run_id)
            await _close_run(run_id, "succeeded", processed, changed, None)
        except Exception as e:  # noqa: BLE001
            log.exception("background job %s failed", job_name)
            await _close_run(run_id, "failed", 0, 0, f"{type(e).__name__}: {e}")

    asyncio.create_task(_bg())
    return run_id
