"""F07 scheduler — in-process APScheduler with a Postgres (SQLAlchemy) job store.

Survives restart (job store persists). Started ONLY from the FastAPI lifespan when
SCHEDULER_ENABLED=true — never at import, so tests and CI never spin it up. Each
job's cron + enabled state come from platform_setting (job.<name>.cron/.enabled),
so ops toggle without a deploy. Best-effort: a job-store connection failure logs
and leaves the API running (the scheduler is auxiliary, not on the request path).
"""

from __future__ import annotations

import logging

from app.config import settings
from app.services.jobs import monitor_notices, pull_regulators, refresh_benchmarks
from app.services.jobs.framework import JOB_DEFAULTS

log = logging.getLogger(__name__)

# Top-level references so the SQLAlchemy job store can serialize them by import path.
JOB_FUNCS = {
    "monitor_notices": monitor_notices.run,
    "pull_regulators": pull_regulators.run,
    "refresh_benchmarks": refresh_benchmarks.run,
}

_scheduler = None


def _jobstore_url() -> str | None:
    """Sync SQLAlchemy URL for the pooler (psycopg driver)."""
    raw = settings.database_pooler_url or settings.database_url
    if not raw:
        return None
    # APScheduler/SQLAlchemy want the psycopg3 driver prefix.
    return raw.replace("postgresql://", "postgresql+psycopg://", 1)


async def _run(job_name: str) -> None:
    """Scheduled entry — always triggered_by='schedule'."""
    await JOB_FUNCS[job_name]("schedule")


def start() -> None:
    global _scheduler
    if not settings.scheduler_enabled:
        log.info("scheduler disabled (SCHEDULER_ENABLED=false) — not starting")
        return
    try:
        from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from apscheduler.triggers.cron import CronTrigger

        url = _jobstore_url()
        jobstores = {"default": SQLAlchemyJobStore(url=url)} if url else {}
        _scheduler = AsyncIOScheduler(jobstores=jobstores, timezone="UTC")

        # Startup uses SLA defaults; the /admin/jobs/{name}/toggle endpoint applies
        # platform_setting cron/enabled overrides live (reschedule()).
        for name in JOB_DEFAULTS:
            if JOB_DEFAULTS[name]["enabled"]:
                _scheduler.add_job(_run, CronTrigger.from_crontab(JOB_DEFAULTS[name]["cron"], timezone="UTC"),
                                   args=[name], id=name, replace_existing=True)
        _scheduler.start()
        log.info("scheduler started with jobs: %s", list(JOB_FUNCS))
    except Exception as e:  # noqa: BLE001 — auxiliary; never take down the API
        log.exception("scheduler failed to start (API continues): %s", e)


def reschedule(job_name: str, enabled: bool, cron: str) -> None:
    """Apply an enabled/cron change to the live scheduler (called by the toggle endpoint)."""
    if _scheduler is None:
        return
    try:
        from apscheduler.triggers.cron import CronTrigger
        if not enabled:
            if _scheduler.get_job(job_name):
                _scheduler.remove_job(job_name)
        else:
            _scheduler.add_job(_run, CronTrigger.from_crontab(cron, timezone="UTC"),
                               args=[job_name], id=job_name, replace_existing=True)
    except Exception as e:  # noqa: BLE001
        log.warning("reschedule %s failed: %s", job_name, e)


def shutdown() -> None:
    global _scheduler
    if _scheduler is not None:
        try:
            _scheduler.shutdown(wait=False)
        except Exception:  # noqa: BLE001
            pass
        _scheduler = None
