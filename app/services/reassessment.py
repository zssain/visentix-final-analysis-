"""Admin-triggered re-assessment batch (F09 — M-14).

Replaces the `/admin/trigger-assessment` stub with a real call into the
scoring pipeline. Given an org (or an explicit set of notice ids), it
reconstructs each notice's `DecomposedNotice` from its already-stored sections
and clauses and runs the same `score_and_persist` entrypoint the live intake
flow uses — writing new `derived_data_item` + `report_snapshot` rows. No new
scoring code, no fabricated inputs.

Every batch is recorded as an `ingestion_run` row (the run identifier returned
to the caller) so the trigger leaves an audit trail (schema.md §4 lineage).
"""

from __future__ import annotations

import logging
from uuid import uuid4

import httpx

from app.config import settings
from app.db import get_service_headers, supabase_rest_get
from app.services.intake.decompose import (
    DecomposedClause,
    DecomposedNotice,
    DecomposedSection,
)
from app.services.live_scoring import score_and_persist

log = logging.getLogger(__name__)

SB = settings.supabase_url


async def _reconstruct_notice(notice_id: str) -> DecomposedNotice:
    """Rebuild a DecomposedNotice from stored notice_section + disclosure_clause."""
    r = await supabase_rest_get(
        "notice_section",
        select="section_id,title,section_type,sequence,extracted_text",
        filters=f"notice_id=eq.{notice_id}&order=sequence.asc",
        limit=1000,
    )
    section_rows = r.json() if r.status_code == 200 else []
    sections = [
        DecomposedSection(
            section_id=s["section_id"],
            title=s.get("title") or "",
            section_type=s.get("section_type") or "general",
            sequence=s.get("sequence") or 0,
            text=s.get("extracted_text") or "",
        )
        for s in section_rows if isinstance(s, dict) and s.get("section_id")
    ]

    section_ids = [s.section_id for s in sections]
    clauses: list[DecomposedClause] = []
    # Chunk the section-id IN() filter to stay well under URL limits.
    for i in range(0, len(section_ids), 40):
        chunk = section_ids[i:i + 40]
        in_list = ",".join(f'"{sid}"' for sid in chunk)
        r = await supabase_rest_get(
            "disclosure_clause",
            select=(
                "clause_id,section_id,raw_text,normalized_text,category,"
                "ambiguity_score,readability_score,nlp_confidence,domain_id,"
                "clause_type,transparency_score,classifier_version,is_noise,noise_reason"
            ),
            filters=f"section_id=in.({in_list})",
            limit=2000,
        )
        for c in (r.json() if r.status_code == 200 else []):
            if not isinstance(c, dict):
                continue
            clauses.append(DecomposedClause(
                clause_id=c["clause_id"],
                section_id=c.get("section_id") or "",
                raw_text=c.get("raw_text") or "",
                normalized_text=c.get("normalized_text") or "",
                category=c.get("category") or "other",
                ambiguity_score=c.get("ambiguity_score") or 0.0,
                readability_score=c.get("readability_score") or 0.0,
                nlp_confidence=c.get("nlp_confidence") or 0.0,
                domain_id=c.get("domain_id") or "",
                clause_type=c.get("clause_type") or "",
                transparency_score=c.get("transparency_score") or 0.0,
                classifier_version=c.get("classifier_version"),
                # Carry the stored noise flag so re-scoring excludes noise the
                # same way intake does (older rows default is_noise=false).
                is_noise=bool(c.get("is_noise")),
                noise_reason=c.get("noise_reason"),
            ))

    return DecomposedNotice(sections=sections, clauses=clauses)


async def _resolve_target_notices(
    org_id: str | None, notice_ids: list[str] | None,
) -> list[dict]:
    """Return [{notice_id, organization_id}] for the batch."""
    if notice_ids:
        in_list = ",".join(f'"{nid}"' for nid in notice_ids)
        r = await supabase_rest_get(
            "privacy_notice", select="notice_id,organization_id",
            filters=f"notice_id=in.({in_list})", limit=1000,
        )
        return r.json() if r.status_code == 200 else []
    if org_id:
        r = await supabase_rest_get(
            "privacy_notice", select="notice_id,organization_id",
            filters=f"organization_id=eq.{org_id}&order=retrieval_date.desc",
            limit=1000,
        )
        return r.json() if r.status_code == 200 else []
    return []


async def _record_run(run_id: str, fields: dict) -> None:
    headers = {**get_service_headers(), "Content-Type": "application/json",
               "Prefer": "return=minimal"}
    async with httpx.AsyncClient(timeout=15) as client:
        await client.patch(
            f"{SB}/rest/v1/ingestion_run?run_id=eq.{run_id}",
            headers=headers, json=fields,
        )


async def trigger_reassessment(
    *,
    org_id: str | None = None,
    notice_ids: list[str] | None = None,
    triggered_by: str = "",
) -> dict:
    """Run the scoring pipeline over an org's notices (or an explicit set).

    Returns the run identifier and a per-notice result list. Raises ValueError
    when neither org_id nor notice_ids is supplied, or no notices resolve.
    """
    if not org_id and not notice_ids:
        raise ValueError("Provide org_id or notice_ids.")

    targets = await _resolve_target_notices(org_id, notice_ids)
    if not targets:
        raise ValueError("No notices found for the requested scope.")

    run_id = str(uuid4())
    # Open the run row up front so a crash mid-batch still leaves a trace.
    headers = {**get_service_headers(), "Content-Type": "application/json",
               "Prefer": "return=minimal"}
    async with httpx.AsyncClient(timeout=15) as client:
        await client.post(
            f"{SB}/rest/v1/ingestion_run",
            headers=headers,
            json={
                "run_id": run_id,
                "source_name": "admin_trigger_assessment",
                "run_type": "reassessment",
                "status": "running",
                "records_seen": len(targets),
                "notes": f"triggered_by={triggered_by}",
            },
        )

    results: list[dict] = []
    scored = 0
    for t in targets:
        nid = t.get("notice_id")
        oid = t.get("organization_id")
        if not nid or not oid:
            continue
        try:
            notice = await _reconstruct_notice(nid)
            if not notice.clauses:
                results.append({"notice_id": nid, "status": "skipped_no_clauses"})
                continue
            out = await score_and_persist(oid, nid, notice)
            snap = (out.get("summary") or {}).get("snapshot_id", "")
            results.append({"notice_id": nid, "status": "scored", "snapshot_id": snap})
            scored += 1
        except Exception as exc:  # noqa: BLE001 — honest per-notice failure record
            log.warning("reassessment failed for notice %s: %s", nid, exc)
            results.append({"notice_id": nid, "status": "failed", "error": str(exc)[:200]})

    failed = sum(1 for r in results if r["status"] == "failed")
    outcome = "ok" if failed == 0 else ("partial" if scored else "failed")
    await _record_run(run_id, {
        "status": outcome,
        "outcome": outcome,
        "records_new": scored,
        "records_skipped": len(results) - scored,
        "finished_at": "now()",
    })

    return {
        "run_id": run_id,
        "run_type": "reassessment",
        "requested": len(targets),
        "scored": scored,
        "failed": failed,
        "outcome": outcome,
        "notices": results,
    }
