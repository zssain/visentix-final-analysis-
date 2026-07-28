"""Shared intake persistence — the single classify + persist path.

Factored verbatim out of `routers/assessments.create_assessment` so that both
the single-assessment endpoint and the F19 bulk-screening runner drive ONE
intake path (no forked intake, no forked classifier). `create_assessment`
behavior is unchanged: it calls these helpers with the values it already
computed and gets back the same `notice_id` it used to generate inline.

Scoring is NOT done here — callers invoke the existing scoring path
(`live_scoring.score_and_persist`, or the `reassessment` kernel that wraps it).
"""

import asyncio
from datetime import date
from uuid import uuid4

from fastapi import HTTPException, status

from app.db import supabase_rest_post
from app.logging import get_logger
from app.services.intake.classify_v2 import (
    CLASSIFIER_VERSION,
    KEYWORD_FALLBACK_VERSION,
    TAXONOMY_V2 as _LLM_TAXONOMY,  # single source of truth (shared with the reclassifier)
)
from app.services.intake.decompose import DECOMPOSE_VERSION, DecomposedNotice

log = get_logger(__name__)


# ── LLM classification (bounded concurrency) ─────────────────

async def classify_clauses(notice: DecomposedNotice) -> tuple[int, int]:
    """Classify clauses via LLM with bounded concurrency.

    Returns (llm_classified_count, keyword_fallback_count).
    On any LLM-level failure, all clauses keep their keyword labels.
    """
    # Noise clauses are excluded from classification counts (they keep their
    # deterministic keyword label for lineage but are never LLM-classified/counted).
    eligible = [c for c in notice.clauses if len(c.raw_text) >= 20 and not c.is_noise]
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


# ── Notice persistence (privacy_notice + sections + clauses) ──

async def persist_notice(
    org_id: str,
    notice: DecomposedNotice,
    *,
    source_url: str | None,
    content_hash: str | None,
    intake_method: str,
    upload_filename: str | None = None,
    upload_mime: str | None = None,
    upload_file_hash: str | None = None,
) -> str:
    """Persist a decomposed notice (privacy_notice + sections + clauses).

    Returns the generated notice_id. Raises HTTPException(502) if the notice
    row cannot be stored (preserves the single-assessment 502 behavior).
    """
    notice_id = str(uuid4())

    # Mean NLP confidence across clauses → extraction_confidence
    mean_conf = (
        sum(c.nlp_confidence for c in notice.clauses) / len(notice.clauses)
        if notice.clauses else 0.0
    )

    # privacy_notice — single row
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
        # Intake provenance (migration 0033). Upload columns are NULL for
        # url/text intake; set only for uploaded documents.
        "intake_method": intake_method,
        "upload_filename": upload_filename,
        "upload_mime": upload_mime,
        "upload_file_hash": upload_file_hash,
        # decompose-v2 noise filter version tag — marks this assessment as
        # noise-filtered so older assessments (NULL) stay untouched (Rule 4).
        "decompose_version": DECOMPOSE_VERSION,
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

    # notice_section — ONE batch POST
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

    # disclosure_clause — ONE batch POST (includes v2 taxonomy fields)
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
            # decompose-v2 noise filter — kept for lineage, excluded from counts.
            "is_noise": c.is_noise,
            "noise_reason": c.noise_reason,
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
    return notice_id
