"""Visentix MVP — FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.logging import get_logger, setup_logging
from app.routers import admin, assessments, auth, bulk, explain, feed, findings, formulas, health, monitoring, partner, quarterly, reports, review
from app.routers import config_routes
from app.routers import eval as eval_router
from app.routers import notifications

setup_logging(level="DEBUG" if not settings.is_production else "INFO")
log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # BACK-001 startup reaper: reclaim any job_run left in `running` by a worker
    # that was SIGKILL'd/OOM'd (its `finally` never ran). Without this a single
    # hard crash disables monitor_notices/pull_regulators/refresh_benchmarks
    # forever. Best-effort: a DB hiccup here must not block app startup.
    if settings.scheduler_enabled:
        try:
            from app.services.jobs.framework import reap_stale_runs
            reaped = await reap_stale_runs()
            if reaped:
                log.warning("startup reaper: reclaimed %d orphaned job_run(s)", reaped)
        except Exception:  # noqa: BLE001 — never let the reaper block startup
            log.exception("startup reaper failed (non-fatal)")

    # F07 scheduler — no-op unless SCHEDULER_ENABLED=true, so tests never start it.
    from app.services import scheduler
    scheduler.start()
    yield
    scheduler.shutdown()


app = FastAPI(
    title="Visentix MVP",
    version="0.2.0",
    docs_url="/docs" if not settings.is_production else None,
    redoc_url=None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(assessments.router)
app.include_router(findings.router)
app.include_router(reports.router)
app.include_router(admin.router)
app.include_router(review.router)
app.include_router(auth.router)
app.include_router(explain.router)
app.include_router(feed.router)
app.include_router(monitoring.router)
app.include_router(formulas.router)
app.include_router(eval_router.router)
app.include_router(notifications.router)
app.include_router(bulk.router)
app.include_router(partner.router)
app.include_router(quarterly.public_router)
app.include_router(quarterly.admin_router)
app.include_router(config_routes.router)

log.info("Visentix MVP started (env=%s)", settings.app_env)
