"""Visentix MVP — FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.logging import get_logger, setup_logging
from app.routers import admin, assessments, auth, bulk, explain, feed, findings, formulas, health, monitoring, partner, reports, review
from app.routers import eval as eval_router
from app.routers import notifications

setup_logging(level="DEBUG" if not settings.is_production else "INFO")
log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
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

log.info("Visentix MVP started (env=%s)", settings.app_env)
