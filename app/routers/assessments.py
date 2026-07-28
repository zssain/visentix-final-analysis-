"""Assessment endpoints — intake, decompose, classify, and score privacy notices."""

import hashlib
import urllib.parse
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from app.auth import AuthenticatedUser, require_role
from app.db import supabase_rest_get, supabase_rest_post
from app.logging import get_logger
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
    user: AuthenticatedUser = require_role("customer", "sme", "admin"),
):
    """Guardrailed illustrative rewrite; falls back to an approved-exemplar
    comparison on any guardrail/verification failure. Org-scoped (403 cross-org)."""
    await _assert_owns(assessment_id, user)
    from app.services.rewrite import generate_rewrite
    try:
        return await generate_rewrite(assessment_id, clause_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


# ── Create assessment ────────────────────────────────────────

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_assessment(
    user: AuthenticatedUser = require_role("customer", "admin"),
    url: Optional[str] = Form(None),
    text: Optional[str] = Form(None),
    organization_id: Optional[str] = Form(None),
    organization_name: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
):
    """Create a new assessment from URL, PDF upload, or raw text.

    Full pipeline: extract -> decompose -> classify -> persist -> score.
    Returns 201 with assessment details including scores when available.
    """
    return await run_assessment_intake(
        user=user, url=url, text=text, organization_id=organization_id,
        organization_name=organization_name, file=file,
    )


async def run_assessment_intake(
    *,
    user: AuthenticatedUser,
    url: Optional[str] = None,
    text: Optional[str] = None,
    organization_id: Optional[str] = None,
    organization_name: Optional[str] = None,
    file: Optional[UploadFile] = None,
):
    """The single intake+score core (extract → decompose → classify → persist →
    score). Called by the customer `/assessments/` route AND the F20 partner
    workspace-assessment route — one path, no fork. Callers whose role is not
    `customer` supply `organization_id` explicitly (partner → the workspace's
    client org)."""

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

            extracted_text, content_hash = await extract_from_url(fetch_url)
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

    # ── 3. DECOMPOSE ─────────────────────────────────────────
    notice = decompose(extracted_text)

    # ── 4. LLM CLASSIFY (bounded concurrency) ────────────────
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
    scoring_summary: dict | None = None
    scoring_error: str | None = None
    try:
        from app.services.live_scoring import score_and_persist
        result = await score_and_persist(org_id, notice_id, notice)
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
