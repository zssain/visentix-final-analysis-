"""Admin endpoints — system configuration and catalog management."""

from typing import Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.auth import AuthenticatedUser, require_role

router = APIRouter(prefix="/admin", tags=["admin"])


class TriggerAssessmentRequest(BaseModel):
    org_id: Optional[str] = None
    notice_ids: Optional[list[str]] = None


@router.get("/status")
async def admin_status(
    user: AuthenticatedUser = require_role("admin"),
):
    """Real admin system status: db, ollama, gate mode, last job runs, pending
    reviews, model versions. Replaces the not_implemented stub."""
    import httpx

    from app.config import settings
    from app.db import supabase_rest_get
    from app.services.jobs.framework import JOB_DEFAULTS, last_run

    # db_ok — a cheap read
    try:
        r = await supabase_rest_get("platform_setting", select="key", limit=1)
        db_ok = r.status_code == 200
    except Exception:  # noqa: BLE001
        db_ok = False

    # ollama_ok — best-effort ping
    ollama_ok = False
    try:
        async with httpx.AsyncClient(timeout=2) as c:
            ollama_ok = (await c.get(f"{settings.ollama_base_url}/api/tags")).status_code == 200
    except Exception:  # noqa: BLE001
        ollama_ok = False

    gate = await supabase_rest_get("platform_setting", select="value", filters="key=eq.gate_mode", limit=1)
    gate_mode = (gate.json()[0]["value"] if gate.status_code == 200 and gate.json() else "strict")

    last_job_runs = [await last_run(name) for name in JOB_DEFAULTS]

    pr = await supabase_rest_get("review_queue_item", select="id",
                                 filters="needs_review=eq.true&cleared=eq.false", limit=1000)
    pending_reviews = len(pr.json()) if pr.status_code == 200 else None

    return {
        "db_ok": db_ok,
        "ollama_ok": ollama_ok,
        "gate_mode": gate_mode,
        "last_job_runs": [r for r in last_job_runs if r],
        "pending_reviews": pending_reviews,
        "model_versions": {
            "scoring_model_version": settings.scoring_model_version,
            "source_corpus_version": settings.source_corpus_version,
            "embedding_model": settings.embedding_model,
            "qwen_local_model": settings.qwen_local_model,
        },
    }


# ── F07 job control (admin only) ─────────────────────────────

class JobToggle(BaseModel):
    enabled: bool


_JOB_BODIES = {}   # lazily populated name -> body coro


def _job_bodies() -> dict:
    if not _JOB_BODIES:
        from app.services.jobs import monitor_notices, pull_regulators, refresh_benchmarks
        _JOB_BODIES.update({
            "monitor_notices": monitor_notices._body,
            "pull_regulators": pull_regulators._body,
            "refresh_benchmarks": refresh_benchmarks._body,
        })
    return _JOB_BODIES


@router.get("/jobs")
async def list_jobs(user: AuthenticatedUser = require_role("admin")):
    from app.services.jobs.framework import JOB_DEFAULTS, job_config, last_run
    out = []
    for name in JOB_DEFAULTS:
        cfg = await job_config(name)
        out.append({"job_name": name, "enabled": cfg["enabled"], "cron": cfg["cron"],
                    "last_run": await last_run(name)})
    return out


@router.post("/jobs/{name}/run", status_code=status.HTTP_202_ACCEPTED)
async def run_job(name: str, user: AuthenticatedUser = require_role("admin")):
    from app.services.jobs.framework import trigger_background
    bodies = _job_bodies()
    if name not in bodies:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"unknown job: {name}")
    run_id = await trigger_background(name, bodies[name], triggered_by="manual")
    if run_id is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "job already running")
    return {"job_run_id": run_id}


@router.post("/jobs/{name}/toggle")
async def toggle_job(name: str, body: JobToggle, user: AuthenticatedUser = require_role("admin")):
    from app.services import scheduler
    from app.services.jobs.framework import JOB_DEFAULTS, job_config, set_setting
    if name not in JOB_DEFAULTS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"unknown job: {name}")
    await set_setting(f"job.{name}.enabled", "true" if body.enabled else "false", user.email or "admin")
    cfg = await job_config(name)
    scheduler.reschedule(name, body.enabled, cfg["cron"])
    return {"job_name": name, "enabled": body.enabled, "cron": cfg["cron"]}


@router.post("/trigger-assessment")
async def trigger_assessment(
    body: TriggerAssessmentRequest,
    user: AuthenticatedUser = require_role("admin"),
):
    """Run the scoring pipeline over an org's notices (or an explicit set).

    Admin-gated (F09). Returns the run identifier and per-notice results.
    """
    from app.services.reassessment import trigger_reassessment

    try:
        return await trigger_reassessment(
            org_id=body.org_id,
            notice_ids=body.notice_ids,
            triggered_by=user.email or user.user_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/training-stats")
async def training_stats(
    user: AuthenticatedUser = require_role("admin"),
):
    """Training label statistics — counts by action, domain, over time."""
    from app.services.training import get_training_stats
    return get_training_stats()
