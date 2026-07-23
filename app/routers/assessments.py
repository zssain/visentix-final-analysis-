"""Assessment endpoints — intake, decompose, classify, and score privacy notices."""

import asyncio
import json
import urllib.parse
from datetime import date
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from app.auth import AuthenticatedUser, require_role
from app.db import supabase_rest_get, supabase_rest_post
from app.config import settings
from app.logging import get_logger
from app.services.intake.decompose import (
    DecomposedNotice,
    decompose,
)
from app.services.intake.discover import discover_policy_url, is_direct_policy_url
from app.services.intake.extract import (
    ALLOWED_MIME_TYPES,
    ExtractionError,
    extract_from_pdf,
    extract_from_text,
    extract_from_url,
    looks_like_privacy_policy,
)
from app.services.intake.ssrf import SSRFError

log = get_logger(__name__)

router = APIRouter(prefix="/assessments", tags=["assessments"])

# Valid category values the LLM may return (the 8 legacy domain slugs + other)
from app.services.intake.classify_v2 import (  # noqa: E402
    CLASSIFIER_VERSION,
    KEYWORD_FALLBACK_VERSION,
    TAXONOMY_V2 as _LLM_TAXONOMY,   # single source of truth (shared with the reclassifier)
)


# ── List assessments ─────────────────────────────────────────

@router.get("/")
async def list_assessments(
    user: AuthenticatedUser = require_role("customer", "sme", "admin"),
):
    """List assessments visible to the current user."""
    r = await supabase_rest_get(
        "privacy_notice",
        select="notice_id,organization_id,notice_type,effective_date,content_hash,"
               "organization(name,domain,industry,size,geography)",
        limit=100,
    )
    return r.json()


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

    # ── 1. EXTRACT ────────────────────────────────────────────
    extracted_text: str | None = None
    content_hash: str | None = None
    source_url: str | None = None
    content_warning: str | None = None

    try:
        if url:
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
            log.info("Assessment intake: PDF upload (%s)", file.filename)
            ct = file.content_type or ""
            if ct not in ALLOWED_MIME_TYPES:
                raise HTTPException(
                    status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                    detail=f"Unsupported file type: {ct}. Allowed: {ALLOWED_MIME_TYPES}",
                )
            pdf_bytes = await file.read()
            extracted_text, content_hash = extract_from_pdf(pdf_bytes, file.filename or "")

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
    llm_classified, keyword_fallback = await _classify_clauses(notice)

    log.info(
        "Classification: llm=%d keyword_fallback=%d total=%d (text not logged)",
        llm_classified, keyword_fallback, len(notice.clauses),
    )

    # ── 5. PERSIST (batched) ─────────────────────────────────
    notice_id = str(uuid4())

    # Mean NLP confidence across clauses → extraction_confidence
    mean_conf = (
        sum(c.nlp_confidence for c in notice.clauses) / len(notice.clauses)
        if notice.clauses else 0.0
    )

    # 5a. privacy_notice — single row
    notice_payload = {
        "notice_id": notice_id,
        "organization_id": org_id,
        "notice_type": "live_assessment",
        "url": source_url or "",
        "effective_date": str(date.today()),
        "retrieval_date": str(date.today()),
        "content_hash": content_hash,
        "version_id": 0,
        "jurisdiction_scope": ["US"],
        "storage_path": "",
        "extraction_confidence": round(mean_conf, 4),
        "ai_disclosure_presence": any(
            c.category == "ai_automated_decisions" for c in notice.clauses
        ),
        "tracking_disclosure_presence": any(
            c.category == "tracking_cookies" for c in notice.clauses
        ),
        "consumer_rights_presence": any(
            c.category == "consumer_rights" for c in notice.clauses
        ),
        "retention_disclosure_presence": any(
            c.category == "retention" for c in notice.clauses
        ),
        "cross_border_indicator": any(
            c.category == "cross_border" for c in notice.clauses
        ),
        "sensitive_data_indicator": any(
            c.category == "sensitive_data" for c in notice.clauses
        ),
    }
    r = await supabase_rest_post("privacy_notice", notice_payload)
    if r.status_code >= 400:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to store notice.",
        )

    # 5b. notice_section — ONE batch POST
    section_rows = [
        {
            "section_id": s.section_id,
            "notice_id": notice_id,
            "title": s.title,
            "section_type": s.section_type,
            "sequence": s.sequence,
            "extracted_text": s.text[:10000],
        }
        for s in notice.sections
    ]
    if section_rows:
        r = await supabase_rest_post("notice_section", section_rows)
        if r.status_code >= 400:
            log.error("notice_section insert failed: %d %s", r.status_code, r.text[:300])

    # 5c. disclosure_clause — ONE batch POST (includes v2 taxonomy fields)
    clause_rows = [
        {
            "clause_id": c.clause_id,
            "section_id": c.section_id,
            "raw_text": c.raw_text[:5000],
            "normalized_text": c.normalized_text[:5000],
            "category": c.category,
            "ambiguity_score": c.ambiguity_score,
            "readability_score": c.readability_score,
            "nlp_confidence": c.nlp_confidence,
            "domain_id": c.domain_id or None,
            "clause_type": c.clause_type or None,
            "transparency_score": c.transparency_score,
            # v2 classification written at ingest (never NULL) — mirror of the reclassifier
            "category_v2": c.category_v2,
            "nlp_confidence_v2": c.nlp_confidence_v2,
            "classifier_version": c.classifier_version,
        }
        for c in notice.clauses
    ]
    if clause_rows:
        r = await supabase_rest_post("disclosure_clause", clause_rows)
        if r.status_code >= 400:
            log.error(
                "disclosure_clause insert failed: %d %s",
                r.status_code, r.text[:300],
            )

    log.info(
        "Assessment persisted: notice=%s sections=%d clauses=%d",
        notice_id[:12], len(notice.sections), len(notice.clauses),
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
        "clauses": len(notice.clauses),
        "content_hash": content_hash,
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

    return response


# ── LLM classification helper ────────────────────────────────

async def _classify_clauses(notice: DecomposedNotice) -> tuple[int, int]:
    """Classify clauses via LLM with bounded concurrency.

    Returns (llm_classified_count, keyword_fallback_count).
    On any LLM-level failure, all clauses keep their keyword labels.
    """
    eligible = [c for c in notice.clauses if len(c.raw_text) >= 20]
    if not eligible:
        return 0, 0

    try:
        from app.services.llm import get_llm_client
        llm = get_llm_client()
    except Exception:
        return 0, len(eligible)

    sem = asyncio.Semaphore(4)
    llm_count = 0
    fallback_count = 0

    async def _classify_one(clause):
        nonlocal llm_count, fallback_count
        async with sem:
            try:
                result = await llm.classify(clause.raw_text, _LLM_TAXONOMY)
                cat = result.get("category", "")
                if cat in _LLM_TAXONOMY:
                    conf = min(result.get("confidence", 0.7), 0.95)
                    clause.category = cat
                    clause.nlp_confidence = conf
                    # write the v2 columns at ingest (mirror of the reclassifier) so a
                    # new clause is NEVER left with a NULL category_v2.
                    clause.category_v2 = cat
                    clause.nlp_confidence_v2 = conf
                    clause.classifier_version = CLASSIFIER_VERSION
                    llm_count += 1
                else:
                    fallback_count += 1
            except Exception:
                fallback_count += 1
        # LLM unavailable / off-taxonomy → keep the deterministic keyword label as v2
        # (still non-NULL, honestly attributed) so category_v2 is never NULL.
        if clause.category_v2 is None:
            clause.category_v2 = clause.category
            clause.nlp_confidence_v2 = clause.nlp_confidence
            clause.classifier_version = KEYWORD_FALLBACK_VERSION

    await asyncio.gather(*[_classify_one(c) for c in eligible])
    return llm_count, fallback_count


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
