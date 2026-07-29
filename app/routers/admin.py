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

    # ── Settings-drift check ────────────────────────────────────
    # Prod must not silently sit in demo state (e.g. gate_mode=instant_draft, jobs
    # enabled in a v1 pilot). Compare the LIVE platform_settings against the active
    # release's baseline (release_version platform_setting, default v1) and surface
    # any mismatch so it's visible on /admin/status. The authoritative source is
    # releases/<version>.yaml — mirrored here so the check runs inside the image.
    from app.services.jobs.framework import job_config
    _RELEASE_BASELINE = {
        "v1": {"gate_mode": "strict", "jobs": {"monitor_notices": False, "pull_regulators": False, "refresh_benchmarks": False}},
        "v2": {"gate_mode": "strict", "jobs": {"monitor_notices": True, "pull_regulators": True, "refresh_benchmarks": True}},
    }
    rv = await supabase_rest_get("platform_setting", select="value", filters="key=eq.release_version", limit=1)
    active_version = (rv.json()[0]["value"] if rv.status_code == 200 and rv.json() else "v1")
    baseline = _RELEASE_BASELINE.get(active_version if active_version in _RELEASE_BASELINE else "v1",
                                     _RELEASE_BASELINE["v2"])  # v3+ inherit v2 job posture
    settings_drift = []
    if gate_mode != baseline["gate_mode"]:
        settings_drift.append(f"gate_mode: live={gate_mode} expected={baseline['gate_mode']} ({active_version})")
    for jn, exp_enabled in baseline["jobs"].items():
        cfg = await job_config(jn)
        if bool(cfg.get("enabled")) != exp_enabled:
            settings_drift.append(f"job.{jn}.enabled: live={cfg.get('enabled')} expected={exp_enabled} ({active_version})")

    pr = await supabase_rest_get("review_queue_item", select="id",
                                 filters="needs_review=eq.true&cleared=eq.false", limit=1000)
    pending_reviews = len(pr.json()) if pr.status_code == 200 else None

    # Alert delivery paused? (F-013 thresholds unset → suppressed_no_threshold rows)
    sup = await supabase_rest_get("alert_delivery", select="id",
                                  filters="status=eq.suppressed_no_threshold", limit=1000)
    alerts_suppressed = len(sup.json()) if sup.status_code == 200 else 0

    return {
        "db_ok": db_ok,
        "ollama_ok": ollama_ok,
        "gate_mode": gate_mode,
        "last_job_runs": [r for r in last_job_runs if r],
        "pending_reviews": pending_reviews,
        "alerts_suppressed": alerts_suppressed,
        "release_version": active_version,
        "settings_drift": settings_drift,        # [] = live config matches the release baseline
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
