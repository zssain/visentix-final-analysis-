"""F19 — Bulk Screening endpoints.

Product surface on the verified reassessment kernel (services/bulk.py). Roles:
admin | analyst. Tenant-scoped throughout: a job belongs to the caller's
organization and is invisible cross-tenant (F10). Results are draft-grade; the
gate is never touched here — score_and_persist already leaves each assessment
an SME draft.
"""

import csv
import io

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, status
from fastapi.responses import PlainTextResponse

from app.auth import AuthenticatedUser, require_role
from app.logging import get_logger
from app.services import bulk
from app.services.ratelimit import check_rate_limit, client_key

log = get_logger(__name__)

router = APIRouter(prefix="/bulk", tags=["bulk"])

# SEC-005: a bulk job fans out to ≤200 assessments (extract→classify→score each),
# so it is by far the heaviest submit. Throttle job creation hard — ~3/min per
# user is generous given the one-running-job-per-tenant guard below.
_BULK_JOBS_LIMIT = 3
_BULK_JOBS_WINDOW_S = 60


def _require_tenant(user: AuthenticatedUser) -> str:
    if not user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No organization on your account — a tenant is required for bulk screening.",
        )
    return user.organization_id


async def _parse_rows(request: Request) -> tuple[str, list[dict]]:
    """Return (label, rows) from multipart CSV (org_name,notice_url) or JSON."""
    ctype = request.headers.get("content-type", "")
    if "multipart/form-data" in ctype:
        form = await request.form()
        label = str(form.get("label") or "")
        upload = form.get("file")
        if upload is None or not hasattr(upload, "read"):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "CSV file is required.")
        raw = await upload.read()
        text = raw.decode("utf-8", errors="replace")
        reader = csv.DictReader(io.StringIO(text))
        if not reader.fieldnames or "org_name" not in reader.fieldnames or "notice_url" not in reader.fieldnames:
            raise HTTPException(status.HTTP_400_BAD_REQUEST,
                                "CSV must have headers: org_name,notice_url")
        rows = [{"org_name": rec.get("org_name", ""), "notice_url": rec.get("notice_url", "")}
                for rec in reader]
        return label, rows
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Body must be CSV (multipart) or JSON.")
    label = str(body.get("label") or "")
    rows = [{"org_name": r.get("org_name", ""), "notice_url": r.get("notice_url", "")}
            for r in (body.get("rows") or []) if isinstance(r, dict)]
    return label, rows


@router.post("/jobs", status_code=status.HTTP_202_ACCEPTED)
async def create_bulk_job(
    request: Request,
    background: BackgroundTasks,
    user: AuthenticatedUser = require_role("admin", "analyst"),
):
    """Submit a screening batch. → 202 {bulk_job_id}. Runs sequentially in-process.

    ≤200 rows (201+ → 400). One running job per tenant (else 409). Rows with a
    malformed URL are accepted and fail alone during processing (→ 'partial').
    """
    check_rate_limit(client_key(request, user), limit=_BULK_JOBS_LIMIT, window_s=_BULK_JOBS_WINDOW_S)
    owner_org_id = _require_tenant(user)
    label, rows = await _parse_rows(request)

    if not rows:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No rows provided.")
    if len(rows) > bulk.MAX_ROWS:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Too many rows: {len(rows)} (max {bulk.MAX_ROWS}).",
        )

    # One-running-job-per-tenant guard (AC-11) — the sequential BackgroundTasks
    # model must not silently queue a second 200-row job behind the first.
    if await bulk.has_active_job(owner_org_id):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "A screening job is already running for your organization — "
            "wait for it to finish before starting another.",
        )

    job_id = await bulk.create_job(owner_org_id, user.user_id, label, rows)
    background.add_task(bulk.run_bulk_job, job_id)
    return {"bulk_job_id": job_id}


@router.get("/jobs")
async def list_bulk_jobs(user: AuthenticatedUser = require_role("admin", "analyst")):
    owner_org_id = _require_tenant(user)
    return await bulk.list_jobs(owner_org_id)


@router.get("/jobs/{job_id}")
async def get_bulk_job(job_id: str, user: AuthenticatedUser = require_role("admin", "analyst")):
    owner_org_id = _require_tenant(user)
    job = await bulk.get_job(job_id, owner_org_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found.")
    return job


@router.get("/jobs/{job_id}/results")
async def get_bulk_results(job_id: str, user: AuthenticatedUser = require_role("admin", "analyst")):
    owner_org_id = _require_tenant(user)
    results = await bulk.get_results(job_id, owner_org_id)
    if results is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found.")
    return results


@router.get("/jobs/{job_id}/export.csv", response_class=PlainTextResponse)
async def export_bulk_csv(job_id: str, user: AuthenticatedUser = require_role("admin", "analyst")):
    owner_org_id = _require_tenant(user)
    body = await bulk.export_csv(job_id, owner_org_id)
    if body is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found.")
    return PlainTextResponse(
        content=body,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="bulk_screening_{job_id[:8]}.csv"'},
    )
