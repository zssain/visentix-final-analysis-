"""Assessment endpoints — intake, decompose, classify, and score privacy notices."""

import asyncio
import hashlib
import urllib.parse
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile, status

from app.services.intake import jobs as intake_jobs

from app.auth import AuthenticatedUser, require_role
from app.db import supabase_rest_get, supabase_rest_patch, supabase_rest_post
from app.logging import get_logger
from app.services.ratelimit import check_rate_limit, client_key

# SEC-005: intake is the most expensive path (extract → decompose → LLM classify →
# score). Throttle creates per-authenticated-user. ~10/min balances a legit user
# resubmitting/queuing a few notices against a runaway loop or scripted abuse.
_CREATE_LIMIT = 10
_CREATE_WINDOW_S = 60
from app.services import intake_options as _iopt
from app.services.intake.decompose import decompose
from app.services.intake.discover import discover_policy_url, is_direct_policy_url
from app.services.intake.extract import (
    ExtractionError,
    extract_from_text,
    extract_from_upload,
    extract_from_url,
    looks_like_privacy_policy,
)
from app.services.intake.persist import classify_clauses, persist_notice
from app.services.intake.ssrf import SSRFError

log = get_logger(__name__)

router = APIRouter(prefix="/assessments", tags=["assessments"])


# ── List assessments ─────────────────────────────────────────

@router.get("/")
async def list_assessments(
    user: AuthenticatedUser = require_role("customer", "sme", "admin"),
):
    """List assessments visible to the current user.

    F10 org isolation: a `customer` sees only its own organization's notices;
    `sme`/`admin` see all. A customer with no organization sees nothing (never
    the whole corpus).
    """
    select = ("notice_id,organization_id,notice_type,effective_date,content_hash,"
              "organization(name,domain,industry,size,geography)")
    filters = ""
    if user.role == "customer":
        if not user.organization_id:
            return []
        filters = f"organization_id=eq.{user.organization_id}"
    r = await supabase_rest_get("privacy_notice", select=select, filters=filters, limit=100)
    return r.json()


# ── F05 addendum: recommendation evidence stack (frozen at approval) ──

@router.get("/{assessment_id}/findings/{finding_id}/evidence")
async def finding_evidence(
    assessment_id: str,
    finding_id: str,
    user: AuthenticatedUser = require_role("customer", "sme", "admin"),
):
    """The frozen evidence stack for a finding (served from the store, never
    re-assembled at render). Org-scoped: a customer may only read its own."""
    if user.role == "customer":
        r = await supabase_rest_get("privacy_notice", select="organization_id",
                                    filters=f"notice_id=eq.{assessment_id}", limit=1)
        rows = r.json() if r.status_code == 200 else []
        owner = rows[0]["organization_id"] if rows else None
        if not owner or owner != user.organization_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your assessment.")
    from app.services.evidence import get_evidence
    ev = await get_evidence(assessment_id, finding_id)
    if ev is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="No frozen evidence for this finding (assembled at approval).")
    return ev


async def _assert_owns(assessment_id: str, user: AuthenticatedUser) -> None:
    """Customer may only touch its own assessment (403 otherwise)."""
    if user.role != "customer":
        return
    r = await supabase_rest_get("privacy_notice", select="organization_id",
                                filters=f"notice_id=eq.{assessment_id}", limit=1)
    rows = r.json() if r.status_code == 200 else []
    owner = rows[0]["organization_id"] if rows else None
    if not owner or owner != user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your assessment.")


# ── Clause list (for the rewrite picker) ─────────────────────

@router.get("/{assessment_id}/clauses")
async def list_clauses(
    assessment_id: str,
    user: AuthenticatedUser = require_role("customer", "sme", "admin"),
):
    """The assessment's substantive clauses grouped for the rewrite picker
    (findings-flagged domains first). Org-scoped."""
    await _assert_owns(assessment_id, user)
    sr = await supabase_rest_get("notice_section", select="section_id",
                                 filters=f"notice_id=eq.{assessment_id}", limit=1000)
    section_ids = [s["section_id"] for s in (sr.json() if sr.status_code == 200 else []) if s.get("section_id")]
    clauses: list[dict] = []
    for i in range(0, len(section_ids), 40):
        chunk = ",".join(f'"{s}"' for s in section_ids[i:i + 40])
        cr = await supabase_rest_get(
            "disclosure_clause", select="clause_id,raw_text,category,is_noise",
            filters=f"section_id=in.({chunk})", limit=2000)
        for c in (cr.json() if cr.status_code == 200 else []):
            if c.get("is_noise"):
                continue
            clauses.append({"clause_id": c["clause_id"], "raw_text": c.get("raw_text") or "",
                            "domain": c.get("category") or "other"})
    # domains that have a finding surface first
    fr = await supabase_rest_get("risk_finding", select="domain",
                                 filters=f"notice_id=eq.{assessment_id}", limit=200)
    flagged = {f.get("domain") for f in (fr.json() if fr.status_code == 200 else [])}
    clauses.sort(key=lambda c: (c["domain"] not in flagged, c["domain"]))
    return {"assessment_id": assessment_id, "flagged_domains": sorted(d for d in flagged if d), "clauses": clauses}


# ── F18: illustrative clause rewrite (guardrailed + verified) ──

@router.post("/{assessment_id}/clauses/{clause_id}/rewrite")
async def rewrite_clause(
    assessment_id: str,
    clause_id: str,
    user: AuthenticatedUser = require_role("sme", "admin"),
):
    """Guardrailed illustrative rewrite; falls back to an approved-exemplar
    comparison on any guardrail/verification failure. v1: gated to sme|admin
    (F18 is the v4 flagship — releases with v4 entitlements, not in the pilot)."""
    await _assert_owns(assessment_id, user)
    from app.services.rewrite import generate_rewrite
    try:
        return await generate_rewrite(assessment_id, clause_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


# ── Create assessment ────────────────────────────────────────

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_assessment(
    request: Request,
    user: AuthenticatedUser = require_role("customer", "admin"),
    url: Optional[str] = Form(None),
    text: Optional[str] = Form(None),
    organization_id: Optional[str] = Form(None),
    organization_name: Optional[str] = Form(None),
    industry: Optional[str] = Form(None),
    jurisdictions: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
):
    """Create a new assessment from URL, PDF upload, or raw text.

    Full pipeline: extract -> decompose -> classify -> persist -> score.
    ARCH-001A: optional `industry` + `jurisdictions` (comma-separated state codes)
    are threaded into the org profile and consumed by scoring.
    Returns 201 with assessment details including scores when available.
    """
    check_rate_limit(client_key(request, user), limit=_CREATE_LIMIT, window_s=_CREATE_WINDOW_S)
    return await run_assessment_intake(
        user=user, url=url, text=text, organization_id=organization_id,
        organization_name=organization_name, industry=industry,
        jurisdictions=jurisdictions, file=file,
    )


# ── QA-011: asynchronous intake (202 + server-state progress) ────

class _UploadShim:
    """Buffered stand-in for UploadFile in the background task — the request's
    UploadFile is closed once the 202 response is sent, so we read bytes upfront."""

    def __init__(self, data: bytes, filename: str | None):
        self._data = data
        self.filename = filename

    async def read(self) -> bytes:
        return self._data


async def _run_intake_job(
    job_id: str, *, user, url, text, organization_id, organization_name,
    industry=None, jurisdictions=None, file_bytes=None, file_name=None,
) -> None:
    """Background runner: drive the intake core, recording server-side progress
    and the final outcome on the assessment_job row. Never raises."""
    try:
        async def on_stage(s: str) -> None:
            await intake_jobs.set_stage(job_id, s)

        upload = _UploadShim(file_bytes, file_name) if file_bytes is not None else None
        result = await run_assessment_intake(
            user=user, url=url, text=text, organization_id=organization_id,
            organization_name=organization_name, industry=industry,
            jurisdictions=jurisdictions, file=upload, on_stage=on_stage,
        )
        await intake_jobs.complete_job(
            job_id, assessment_id=result.get("assessment_id"), result=result)
    except HTTPException as e:
        await intake_jobs.fail_job(job_id, f"{e.status_code}: {e.detail}")
    except Exception as e:  # noqa: BLE001 — record honestly; never crash the loop
        log.exception("async intake job %s failed", job_id[:12])
        await intake_jobs.fail_job(job_id, f"{type(e).__name__}: {e}")


@router.post("/async", status_code=status.HTTP_202_ACCEPTED)
async def create_assessment_async(
    request: Request,
    user: AuthenticatedUser = require_role("customer", "admin"),
    url: Optional[str] = Form(None),
    text: Optional[str] = Form(None),
    organization_id: Optional[str] = Form(None),
    organization_name: Optional[str] = Form(None),
    industry: Optional[str] = Form(None),
    jurisdictions: Optional[str] = Form(None),
    idempotency_key: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
):
    """QA-011: enqueue an assessment and return 202 + a job handle immediately,
    instead of blocking the request through extract→…→score (which exceeds
    browser/proxy timeouts for large notices — the "processing flow
    nonfunctional" symptom). Progress lives in SERVER state (`assessment_job`);
    poll `GET /assessments/{id}/status`. A repeat submit carrying the same
    `idempotency_key` returns the SAME job — no duplicate assessment.
    """
    if idempotency_key:
        existing = await intake_jobs.find_by_idempotency_key(idempotency_key)
        if existing:
            # An idempotent replay does no new work → don't spend the caller's budget.
            return {"assessment_id": existing["job_id"], "status": existing["status"],
                    "stage": existing["stage"], "idempotent_replay": True}

    # SEC-005: throttle real new enqueues (shares the create budget with POST /).
    check_rate_limit(client_key(request, user), limit=_CREATE_LIMIT, window_s=_CREATE_WINDOW_S)

    if not (url or text or file):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Provide one of: url, file (PDF), or text.")

    # ARCH-001A: validate filters up front so a bad value fails at submit (422),
    # not silently inside the background job.
    _validate_filters(industry, _parse_jurisdictions(jurisdictions))

    org_for_job = user.organization_id if user.role == "customer" else organization_id
    job = await intake_jobs.create_job(
        organization_id=org_for_job, created_by=user.user_id,
        idempotency_key=idempotency_key)
    job_id = job["job_id"]

    # Buffer the upload now — the UploadFile is closed once we return the 202.
    file_bytes = await file.read() if file else None
    file_name = file.filename if file else None

    asyncio.create_task(_run_intake_job(
        job_id, user=user, url=url, text=text, organization_id=organization_id,
        organization_name=organization_name, industry=industry, jurisdictions=jurisdictions,
        file_bytes=file_bytes, file_name=file_name))

    return {"assessment_id": job_id, "status": "queued", "stage": "queued"}


@router.get("/{assessment_id}/status")
async def assessment_status(
    assessment_id: str,
    user: AuthenticatedUser = require_role("customer", "sme", "admin"),
):
    """QA-011: poll intake progress. `assessment_id` is the job handle returned by
    /async; the real notice id appears in the `assessment_id` field once
    persistence completes (used for the onward redirect to the report)."""
    job = await intake_jobs.get_job(assessment_id)
    if not job:
        raise HTTPException(status_code=404, detail="No such assessment job")
    # Org ownership (mirrors the rest of the tenant boundary): a customer may only
    # poll a job belonging to its own organization.
    if user.role == "customer" and (
        not user.organization_id or job.get("organization_id") != user.organization_id
    ):
        raise HTTPException(status_code=403, detail="Not permitted")
    return {
        "job_id": job["job_id"],
        "status": job["status"],
        "stage": job["stage"],
        "assessment_id": job.get("assessment_id"),
        "error": job.get("error"),
        "result": job.get("result"),
        "created_at": job.get("created_at"),
        "updated_at": job.get("updated_at"),
    }


# ── ARCH-001A: intake filters (industry + state privacy laws) ────

def _parse_csv(raw: Optional[str]) -> list[str]:
    """Accept a comma-separated (or single) field → clean, order-preserving list."""
    if not raw:
        return []
    return [v.strip() for v in raw.split(",") if v.strip()]


# Back-compat alias — jurisdictions were the first multi-value field (ARCH-001A).
_parse_jurisdictions = _parse_csv


def _parse_industries(raw: Optional[str]) -> list[str]:
    """Industry may now be multi-select (checkbox dropdown). The list is
    order-preserving; the FIRST entry is the primary benchmark cohort (scoring
    keys the cohort on a single industry_id)."""
    return _parse_csv(raw)


def _validate_filters(industry: Optional[str], jurisdictions: list[str]) -> None:
    """Reject unknown filter values rather than passing junk downstream (ARCH-001A).

    `industry` accepts a single value or a comma-separated multi-select; every
    entry must be a known industry (or the honest `unknown` sentinel).
    """
    for ind in _parse_industries(industry):
        if not _iopt.is_valid_industry(ind):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Unknown industry: {ind!r}. Choose one of the listed industries or 'unknown'.",
            )
    for j in jurisdictions:
        if not _iopt.is_valid_jurisdiction(j):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Unknown jurisdiction: {j!r}.",
            )


async def _apply_intake_filters(
    org_id: str, industry: Optional[str], jurisdictions: list[str]
) -> bool:
    """Write user-declared industry + jurisdictions onto the org row, with honest
    provenance (ARCH-001A). Blank fields are left untouched (never clobbered).
    Returns True if a scoring input changed → the caller forces a re-profile so
    the change actually reaches the score (Hard Rule 6: new versioned profile).
    """
    from app.services.profiling.live_profile import compute_ic

    patch: dict = {}
    # Industry may be multi-select; the primary (first) entry drives the single
    # benchmark cohort. Additional selections are captured on the request/echo
    # but scoring keys the cohort on one industry_id (Hard Rule 6).
    industries = _parse_industries(industry)
    primary = industries[0] if industries else None
    if primary:
        key = primary.strip().lower().replace(" ", "_")
        if key == _iopt.UNKNOWN_INDUSTRY:
            # Explicit "not sure / not listed" — honest unknown, never a fake real industry.
            patch["industry"] = "unknown"
            patch["industry_source"] = "unknown"
        else:
            industry_id, sub_industry, _label, _conf = compute_ic(key)
            patch["industry"] = key
            patch["industry_id"] = industry_id
            patch["sub_industry"] = sub_industry
            patch["industry_source"] = "user_provided"
    if jurisdictions:
        patch["jurisdiction_presence"] = jurisdictions

    if not patch:
        return False
    await supabase_rest_patch("organization", f"organization_id=eq.{org_id}", patch)
    return True


async def run_assessment_intake(
    *,
    user: AuthenticatedUser,
    url: Optional[str] = None,
    text: Optional[str] = None,
    organization_id: Optional[str] = None,
    organization_name: Optional[str] = None,
    industry: Optional[str] = None,
    jurisdictions: Optional[str] = None,
    file: Optional[UploadFile] = None,
    on_stage=None,
):
    """The single intake+score core (extract → decompose → classify → persist →
    score). Called by the customer `/assessments/` route AND the F20 partner
    workspace-assessment route — one path, no fork. Callers whose role is not
    `customer` supply `organization_id` explicitly (partner → the workspace's
    client org).

    QA-011: `on_stage(stage: str)` is an optional async callback invoked as the
    pipeline advances, so the async intake job can record SERVER-side progress.
    Default None → the synchronous callers behave exactly as before.
    """

    async def _stage(s: str) -> None:
        if on_stage is not None:
            await on_stage(s)

    # ── 0. VALIDATE INTAKE FILTERS (ARCH-001A) — fail fast, before any work ──
    jurisdictions_list = _parse_jurisdictions(jurisdictions)
    _validate_filters(industry, jurisdictions_list)

    # ── 1. EXTRACT ────────────────────────────────────────────
    extracted_text: str | None = None
    content_hash: str | None = None
    source_url: str | None = None
    content_warning: str | None = None
    # Intake provenance — recorded honestly on the notice. 'upload' is NEVER a
    # verified source (that badge means a URL passed SSRF validation); an
    # uploaded document only carries its own filename/mime/original-file hash.
    intake_method = "text"
    upload_filename: str | None = None
    upload_mime: str | None = None
    upload_file_hash: str | None = None

    try:
        if url:
            intake_method = "url"
            log.info("Assessment intake: URL (text not logged)")
            await _stage("fetching")

            # Discovery: if URL isn't already a policy link, try to find the real one
            fetch_url = url
            if not is_direct_policy_url(url):
                discovered = await discover_policy_url(url)
                if discovered:
                    log.info("Discovered policy URL (original not a policy link)")
                    fetch_url = discovered
                else:
                    # Fall back to the given URL + warn
                    content_warning = (
                        "Could not discover a dedicated privacy policy page. "
                        "Extracting from the submitted URL directly — scores may "
                        "carry lower confidence."
                    )

            try:
                extracted_text, content_hash = await extract_from_url(fetch_url)
            except Exception as extract_err:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Could not fetch the URL: {type(extract_err).__name__}. "
                           f"Try submitting a direct privacy policy URL (e.g. /privacy or /privacy-policy).",
                )
            source_url = fetch_url  # real provenance = the page actually assessed

            # Advisory privacy-signal check on the extracted content
            if not content_warning and not looks_like_privacy_policy(extracted_text):
                content_warning = (
                    "Page failed the privacy-signal heuristic — it may not be a "
                    "privacy notice. Scores may carry lower confidence."
                )

        elif file:
            # Uploaded document (PDF / DOCX / TXT). Type is validated by MAGIC
            # BYTES inside extract_from_upload — never the client Content-Type,
            # which is trivially spoofed. Same downstream pipeline as paste-text.
            raw = await file.read()
            log.info(
                "Assessment intake: upload (%s, %d bytes)", file.filename, len(raw)
            )
            extracted_text, content_hash, _kind, upload_mime = extract_from_upload(
                raw, file.filename or ""
            )
            intake_method = "upload"
            # Strip any path components a browser may include; bound the length.
            upload_filename = (file.filename or "").rsplit("/", 1)[-1][:255] or "document"
            # Hash of the ORIGINAL bytes (distinct from content_hash of the text)
            # — lets identical uploaded files be recognized later.
            upload_file_hash = hashlib.sha256(raw).hexdigest()

        elif text:
            log.info("Assessment intake: raw text (%d chars)", len(text))
            extracted_text, content_hash = extract_from_text(text)

        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Provide one of: url, file (PDF), or text.",
            )

    except SSRFError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except ExtractionError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    await _stage("extracting")

    # ── 2. RESOLVE / CREATE ORG ──────────────────────────────
    # Tenancy (F10): a customer's assessment ALWAYS lands under their own
    # organization — a client-supplied organization_id/name can never redirect a
    # customer's notice (URL, paste, or upload) into another tenant. Admins may
    # target a specific org / derive one from the assessed URL.
    if user.role == "customer" and user.organization_id:
        org_id = user.organization_id
    else:
        org_id = organization_id
        if not org_id and organization_name:
            org_id = await _find_or_create_org(organization_name)
        if not org_id and source_url:
            # Derive org name from the URL domain
            from urllib.parse import urlparse
            domain = urlparse(source_url).netloc.replace("www.", "")
            org_name_derived = domain.split(".")[0].title()
            org_id = await _find_or_create_org(org_name_derived)
        if not org_id:
            org_id = await _find_or_create_org("Anonymous Assessment")

    # ── 2b. APPLY INTAKE FILTERS (ARCH-001A) ─────────────────
    # Write the user-declared industry + jurisdictions onto the org BEFORE scoring
    # so compute_ic / compute_rss / build_population consume the real values. A
    # changed scoring input forces a fresh (versioned) profile below.
    profile_inputs_changed = await _apply_intake_filters(org_id, industry, jurisdictions_list)

    # ── 3. DECOMPOSE ─────────────────────────────────────────
    await _stage("segmenting")
    notice = decompose(extracted_text)

    # ── 4. LLM CLASSIFY (bounded concurrency) ────────────────
    await _stage("classifying")
    llm_classified, keyword_fallback = await classify_clauses(notice)

    log.info(
        "Classification: llm=%d keyword_fallback=%d total=%d (text not logged)",
        llm_classified, keyword_fallback, len(notice.clauses),
    )

    # ── 5. PERSIST (batched — shared single intake path) ─────
    # Same code the F19 bulk runner uses (services/intake/persist.py) — one
    # intake path, no fork. Returns the generated notice_id.
    notice_id = await persist_notice(
        org_id, notice,
        source_url=source_url,
        content_hash=content_hash,
        intake_method=intake_method,
        upload_filename=upload_filename,
        upload_mime=upload_mime,
        upload_file_hash=upload_file_hash,
    )

    # ── 6. SCORE (live scoring — Prompt 6 adds the module) ───
    await _stage("scoring")
    scoring_summary: dict | None = None
    scoring_error: str | None = None
    try:
        from app.services.live_scoring import score_and_persist
        result = await score_and_persist(
            org_id, notice_id, notice, refresh_profile=profile_inputs_changed)
        scoring_summary = result.get("summary")
    except ImportError:
        # live_scoring module not yet created (Prompt 6)
        pass
    except Exception as e:
        log.exception(
            "Scoring failed for notice=%s org=%s (clause_count=%d)",
            notice_id[:12], org_id[:12], len(notice.clauses),
        )
        scoring_error = f"{type(e).__name__}: {e}"

    # ── 7. RESPONSE (201 CREATED) ────────────────────────────
    response: dict = {
        "assessment_id": notice_id,
        "organization_id": org_id,
        "status": "scored" if scoring_summary else "decomposed",
        "sections": len(notice.sections),
        "clauses": len(notice.clauses),  # total extracted units (incl. flagged noise)
        # decompose-v2: substantive vs noise split for an honest headline count.
        "clauses_substantive": sum(1 for c in notice.clauses if not c.is_noise),
        "clauses_noise": sum(1 for c in notice.clauses if c.is_noise),
        "content_hash": content_hash,
        # M-02: the source was fetched from a URL that passed SSRF validation
        # (a failed check raises above, so reaching here with a source_url means
        # it was validated). File/text intake has no fetched source → not set.
        "ssrf_protected": bool(source_url),
        "source_url": source_url or None,
        # Intake provenance — drives the honest source badge in the UI. An
        # 'upload' is a customer-register "uploaded document", NOT verified-source.
        "intake_method": intake_method,
        "classification": {
            "llm": llm_classified,
            "keyword_fallback": keyword_fallback,
        },
    }
    if scoring_summary:
        response["scores"] = scoring_summary
    if scoring_error:
        response["scoring_error"] = scoring_error
    if content_warning:
        response["content_warning"] = content_warning
    if upload_filename:
        response["upload_filename"] = upload_filename
    # ARCH-001A: echo the captured filters (honest provenance for the UI/report).
    industries_list = [i.strip().lower().replace(" ", "_") for i in _parse_industries(industry)]
    if industries_list:
        # `industry` = the primary (cohort) selection; `industries` = full picks.
        response["industry"] = industries_list[0]
        response["industries"] = industries_list
        response["industry_source"] = (
            "unknown" if response["industry"] == _iopt.UNKNOWN_INDUSTRY else "user_provided")
    if jurisdictions_list:
        response["jurisdictions"] = jurisdictions_list

    return response


# ── Org resolution (injection-safe) ──────────────────────────

async def _find_or_create_org(name: str) -> str:
    """Find an existing org by name/slug or create a new one."""
    slug = name.lower().replace(" ", "-")

    # Try by name (exact)
    safe_name = urllib.parse.quote(name, safe="")
    r = await supabase_rest_get(
        "organization",
        select="organization_id",
        filters=f"name=eq.{safe_name}",
        limit=1,
    )
    rows = r.json() if r.status_code == 200 else []
    if rows:
        return rows[0]["organization_id"]

    # Try by slug (case-insensitive match)
    safe_slug = urllib.parse.quote(slug, safe="")
    r2 = await supabase_rest_get(
        "organization",
        select="organization_id",
        filters=f"slug=eq.{safe_slug}",
        limit=1,
    )
    rows2 = r2.json() if r2.status_code == 200 else []
    if rows2:
        return rows2[0]["organization_id"]

    # Create new
    org_id = str(uuid4())
    r3 = await supabase_rest_post("organization", {
        "organization_id": org_id,
        "name": name,
        "slug": slug,
        "industry": "unknown",
        "size": "unknown",
        "geography": "US",
        "entity_type": "target",
        "tenant_id": "proto",
    })
    # Handle race condition / slug conflict — re-lookup
    if r3.status_code >= 400:
        r4 = await supabase_rest_get(
            "organization",
            select="organization_id",
            filters=f"slug=eq.{safe_slug}",
            limit=1,
        )
        rows4 = r4.json() if r4.status_code == 200 else []
        if rows4:
            return rows4[0]["organization_id"]
    return org_id
