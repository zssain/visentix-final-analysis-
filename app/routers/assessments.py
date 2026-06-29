"""Assessment endpoints — intake, decompose, and classify privacy notices."""

import hashlib
import json
from datetime import date
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from app.auth import AuthenticatedUser, require_role
from app.db import get_service_headers, supabase_rest_get, supabase_rest_post
from app.config import settings
from app.logging import get_logger
from app.services.intake.decompose import decompose
from app.services.intake.extract import (
    ALLOWED_MIME_TYPES,
    ExtractionError,
    extract_from_pdf,
    extract_from_text,
    extract_from_url,
)
from app.services.intake.ssrf import SSRFError

log = get_logger(__name__)

router = APIRouter(prefix="/assessments", tags=["assessments"])


@router.get("/")
async def list_assessments(
    user: AuthenticatedUser = require_role("customer", "sme", "admin"),
):
    """List assessments visible to the current user."""
    r = await supabase_rest_get(
        "privacy_notice",
        select="notice_id,organization_id,notice_type,effective_date,content_hash",
        limit=100,
    )
    return r.json()


@router.post("/", status_code=status.HTTP_202_ACCEPTED)
async def create_assessment(
    user: AuthenticatedUser = require_role("customer", "admin"),
    url: Optional[str] = Form(None),
    text: Optional[str] = Form(None),
    organization_id: Optional[str] = Form(None),
    organization_name: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
):
    """Create a new assessment from URL, PDF upload, or raw text.

    Returns an assessment_id and status for polling.
    """
    # Determine input type
    extracted_text = None
    content_hash = None
    source_url = None

    try:
        if url:
            log.info("Assessment intake: URL (text not logged)")
            extracted_text, content_hash = await extract_from_url(url)
            source_url = url

        elif file:
            log.info("Assessment intake: PDF upload (%s)", file.filename)
            content_type = file.content_type or ""
            if content_type not in ALLOWED_MIME_TYPES:
                raise HTTPException(
                    status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                    detail=f"Unsupported file type: {content_type}. Allowed: {ALLOWED_MIME_TYPES}",
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

    # Resolve or create organization
    org_id = organization_id
    if not org_id and organization_name:
        org_id = await _find_or_create_org(organization_name)
    if not org_id:
        org_id = str(uuid4())  # anonymous assessment

    # Decompose: keyword classification as structural parse
    notice = decompose(extracted_text)

    # LLM classification: classify ALL clauses via Qwen, keyword as fallback
    llm_classified = 0
    keyword_fallback = 0
    taxonomy = [
        "data_sharing", "tracking_cookies", "consumer_rights", "cross_border",
        "sensitive_data", "retention", "children_teens", "ai_automated_decisions", "other",
    ]
    try:
        from app.services.llm import get_llm_client
        llm = get_llm_client()

        for clause in notice.clauses:
            if len(clause.raw_text) < 20:
                continue  # too short for meaningful classification
            try:
                result = await llm.classify(clause.raw_text, taxonomy)
                cat = result.get("category", "")
                if cat in taxonomy:
                    clause.category = cat
                    clause.nlp_confidence = min(result.get("confidence", 0.7), 0.95)
                    llm_classified += 1
                else:
                    keyword_fallback += 1  # keep keyword classification
            except Exception:
                keyword_fallback += 1  # per-clause fallback, no crash
    except Exception:
        keyword_fallback = len(notice.clauses)
        # LLM entirely unavailable — all clauses keep keyword classification

    log.info(
        "Classification: llm=%d keyword_fallback=%d total=%d (text not logged)",
        llm_classified, keyword_fallback, len(notice.clauses),
    )

    notice_id = str(uuid4())

    # Store privacy_notice
    notice_payload = {
        "notice_id": notice_id,
        "organization_id": org_id,
        "notice_type": "live_assessment",
        "url": source_url or "",
        "effective_date": str(date.today()),
        "retrieval_date": str(date.today()),
        "content_hash": content_hash,
        "version_id": 0,
        "jurisdiction_scope": json.dumps(["US"]),
        "storage_path": "",
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
    await supabase_rest_post("privacy_notice", notice_payload)

    # Store sections
    for section in notice.sections:
        await supabase_rest_post("notice_section", {
            "section_id": section.section_id,
            "notice_id": notice_id,
            "title": section.title,
            "section_type": section.section_type,
            "sequence": section.sequence,
            "extracted_text": section.text[:10000],  # cap
        })

    # Store clauses
    for clause in notice.clauses:
        await supabase_rest_post("disclosure_clause", {
            "clause_id": clause.clause_id,
            "section_id": clause.section_id,
            "raw_text": clause.raw_text[:5000],
            "normalized_text": clause.normalized_text[:5000],
            "category": clause.category,
            "ambiguity_score": clause.ambiguity_score,
            "readability_score": clause.readability_score,
            "nlp_confidence": clause.nlp_confidence,
        })

    log.info(
        "Assessment created: notice=%s sections=%d clauses=%d",
        notice_id[:12], len(notice.sections), len(notice.clauses),
    )

    return {
        "assessment_id": notice_id,
        "organization_id": org_id,
        "status": "decomposed",
        "sections": len(notice.sections),
        "clauses": len(notice.clauses),
        "content_hash": content_hash,
    }


async def _find_or_create_org(name: str) -> str:
    """Find an existing org by name or create a new one."""
    r = await supabase_rest_get(
        "organization",
        select="organization_id",
        filters=f"name=eq.{name}",
        limit=1,
    )
    rows = r.json()
    if rows:
        return rows[0]["organization_id"]

    org_id = str(uuid4())
    await supabase_rest_post("organization", {
        "organization_id": org_id,
        "name": name,
        "slug": name.lower().replace(" ", "-"),
        "industry": "unknown",
        "size": "unknown",
        "geography": "US",
        "entity_type": "target",
        "tenant_id": "proto",
    })
    return org_id
