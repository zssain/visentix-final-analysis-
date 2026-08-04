"""Explainability API — VICBNF-005/007.

Uniform explain envelope for every score, finding, clause, domain, cohort,
recommendation, and report section. Decodes all short codes via glossary.
Same auth + customer_can_view gate as reports.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import httpx
from fastapi import APIRouter, HTTPException, Query, status

from app.auth import AuthenticatedUser, require_role
from app.config import settings
from app.db import get_service_headers
from app.services.review import customer_can_view

router = APIRouter(prefix="/reports", tags=["explain"])

log = logging.getLogger(__name__)

SB = settings.supabase_url
_GLOSSARY_PATH = Path(__file__).resolve().parents[2] / "config" / "glossary.json"
with open(_GLOSSARY_PATH) as _f:
    GLOSSARY = json.load(_f)

# Quick lookup helpers
_FORMULA_GLOSSARY = GLOSSARY.get("formulas", {})
_FINDING_GLOSSARY = GLOSSARY.get("finding_codes", {})
_DOMAIN_GLOSSARY = GLOSSARY.get("domain_ids", {})
_VCI_BANDS = GLOSSARY.get("vci_bands", {})
_MATURITY_BANDS = GLOSSARY.get("maturity_bands", {})
_ORG_DIM_GLOSSARY = GLOSSARY.get("org_dimensions", {})


def _sb_get(path: str) -> list[dict]:
    r = httpx.get(f"{SB}/rest/v1/{path}", headers=get_service_headers(), timeout=15)
    return r.json() if r.status_code == 200 else []


def _decode_title(element_type: str, key: str) -> str:
    """Decode a short code to a human title. Never return a bare code."""
    fkey = key.upper().replace("F0", "F-0").replace("F1", "F-1") if key.startswith("f0") else key
    if element_type == "score":
        entry = _FORMULA_GLOSSARY.get(fkey, _FORMULA_GLOSSARY.get(key, {}))
        if entry:
            return entry.get("plain", key)
    elif element_type == "finding":
        entry = _FINDING_GLOSSARY.get(key, {})
        if entry:
            return entry.get("plain", key)
    elif element_type == "domain":
        entry = _DOMAIN_GLOSSARY.get(key, {})
        if entry:
            return entry.get("plain", key)
    return key


def _vci_note(score: float) -> str:
    if score >= 90: return _VCI_BANDS.get("Very High", {}).get("plain", "")
    if score >= 75: return _VCI_BANDS.get("High", {}).get("plain", "")
    if score >= 60: return _VCI_BANDS.get("Moderate", {}).get("plain", "")
    if score >= 40: return _VCI_BANDS.get("Low", {}).get("plain", "")
    return _VCI_BANDS.get("Very Low", {}).get("plain", "")


# ── Endpoints ────────────────────────────────────────────────

@router.get("/{assessment_id}/explain")
async def get_explain(
    assessment_id: str,
    type: str = Query(..., description="score|finding|clause|domain|cohort|recommendation|report_section"),
    key: str = Query(..., description="Element key, e.g. f002, SH-002, CR, etc."),
    user: AuthenticatedUser = require_role("customer", "sme", "admin"),
):
    """Return a uniform explain envelope for any report element."""
    if user.role == "customer":
        can_view, _ = customer_can_view(assessment_id)
        if not can_view:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Report pending expert review.")

    # Resolve notice + org
    notices = _sb_get(f"privacy_notice?select=notice_id,organization_id&notice_id=eq.{assessment_id}&limit=1")
    if not notices:
        notices = _sb_get(f"privacy_notice?select=notice_id,organization_id&organization_id=eq.{assessment_id}&order=retrieval_date.desc&limit=1")
    if not notices:
        raise HTTPException(status_code=404, detail="Assessment not found")

    notice = notices[0]
    notice_id = notice["notice_id"]
    org_id = notice["organization_id"]

    # F10: a customer may only explain its own organization's assessment.
    if user.role == "customer" and org_id != user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Not permitted to view this assessment.")

    envelope = _build_envelope(type, key, notice_id, org_id)
    return envelope


@router.get("/{assessment_id}/explain/all")
async def get_explain_all(
    assessment_id: str,
    user: AuthenticatedUser = require_role("customer", "sme", "admin"),
):
    """Return all explain envelopes keyed by 'type:key' for prefetch."""
    if user.role == "customer":
        can_view, _ = customer_can_view(assessment_id)
        if not can_view:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Report pending expert review.")

    notices = _sb_get(f"privacy_notice?select=notice_id,organization_id&notice_id=eq.{assessment_id}&limit=1")
    if not notices:
        notices = _sb_get(f"privacy_notice?select=notice_id,organization_id&organization_id=eq.{assessment_id}&order=retrieval_date.desc&limit=1")
    if not notices:
        raise HTTPException(status_code=404, detail="Assessment not found")

    notice = notices[0]
    notice_id = notice["notice_id"]
    org_id = notice["organization_id"]

    # F10: a customer may only prefetch its own organization's explains.
    if user.role == "customer" and org_id != user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Not permitted to view this assessment.")

    result = {}

    # All scores
    for fkey in ["f002", "f003", "f005", "f006", "f007", "f008", "f010", "f011"]:
        result[f"score:{fkey}"] = _build_envelope("score", fkey, notice_id, org_id)

    # All findings
    findings = _sb_get(f"risk_finding?select=finding_type_code&notice_id=eq.{notice_id}&limit=20")
    if not findings:
        findings = _sb_get(f"risk_finding?select=finding_type_code&organization_id=eq.{org_id}&limit=20")
    seen = set()
    for f in findings:
        code = f.get("finding_type_code", "")
        if code and code not in seen:
            result[f"finding:{code}"] = _build_envelope("finding", code, notice_id, org_id)
            seen.add(code)

    # All domains
    for did in ["CR", "DC", "SH", "RT", "AI", "SEC", "TRK", "XB"]:
        result[f"domain:{did}"] = _build_envelope("domain", did, notice_id, org_id)

    # Cohort
    result["cohort:population"] = _build_envelope("cohort", "population", notice_id, org_id)

    return result


# ── Envelope builder ─────────────────────────────────────────

def _build_envelope(element_type: str, key: str, notice_id: str, org_id: str) -> dict:
    """Build the uniform explain envelope for any element type."""

    title = _decode_title(element_type, key)

    # Load snapshot for cohort/versioning
    snapshots = _sb_get(
        f"report_snapshot?select=snapshot_id,payload,created_at,benchmark_population_version,"
        f"scoring_model_version,source_corpus_version"
        f"&notice_id=eq.{notice_id}&order=created_at.desc&limit=1"
    )
    if not snapshots:
        snapshots = _sb_get(
            f"report_snapshot?select=snapshot_id,payload,created_at,benchmark_population_version,"
            f"scoring_model_version,source_corpus_version"
            f"&organization_id=eq.{org_id}&order=created_at.desc&limit=1"
        )

    snap = snapshots[0] if snapshots else {}
    snap_payload = snap.get("payload", {})
    if isinstance(snap_payload, str):
        try:
            snap_payload = json.loads(snap_payload)
        except Exception:
            log.warning("Failed to parse report_snapshot payload JSON for org %s; using empty payload", org_id)
            snap_payload = {}

    cohort_size = snap_payload.get("cohort_size", 0)
    cohort_date = (snap.get("created_at") or "")[:10]
    relaxations = snap_payload.get("relaxations", [])
    pop_version = snap.get("benchmark_population_version")

    versioning = {
        "scoring_model_version": snap.get("scoring_model_version") or settings.scoring_model_version,
        "source_corpus_version": snap.get("source_corpus_version") or settings.source_corpus_version,
        "benchmark_population_version": pop_version,
        "formula_version": None,
        "generated_at": snap.get("created_at"),
    }

    # Type-specific data
    plain = ""
    technical: dict = {}
    llm_involvement: dict = {"used": False, "role": "none", "model": None, "confidence": None, "fallback_used": False, "guardrails": ["banned_term_guardrail"]}
    database_provenance: list[dict] = []
    legal_basis: list[dict] = []
    lineage: dict = {}
    confidence_note = ""
    peer_comparison: dict = {}

    if element_type == "score":
        plain, technical, lineage, confidence_note, database_provenance = _explain_score(key, notice_id, org_id, versioning)
        peer_comparison = _build_peer_comparison(cohort_size, cohort_date, pop_version, relaxations)
        # Scores are 100% deterministic — no LLM
        llm_involvement["role"] = "Scores are computed by the deterministic formula engine. No LLM is involved."

    elif element_type == "finding":
        plain, technical, lineage, legal_basis, database_provenance = _explain_finding(key, notice_id, org_id)
        # Findings are deterministic catalog selection
        llm_involvement["role"] = "Findings are selected deterministically from the fixed finding-type catalog based on clause maturity and ambiguity thresholds. No LLM is involved."

    elif element_type == "domain":
        plain, technical, legal_basis = _explain_domain(key)
        # Classification may use LLM
        llm_involvement = {
            "used": True,
            "role": "Clause classification within this domain may use LLM (Qwen) for text categorization, with keyword-based fallback.",
            "model": settings.qwen_local_model or settings.hosted_qwen_model or "keyword_fallback",
            "confidence": None,
            "fallback_used": False,
            "guardrails": ["banned_term_guardrail", "keyword_fallback_on_llm_failure"],
        }

    elif element_type == "cohort":
        plain = f"Dynamic benchmark population of {cohort_size} normalized peers."
        technical = {
            "what_ran": "app/services/benchmark/population.py::build_population",
            "computation": "Population constructed using Industry + 6 tier dimensions as key. Normalization Score = weighted tier similarity. Benchmark Weight = normalization score x band confidence factor.",
        }
        peer_comparison = _build_peer_comparison(cohort_size, cohort_date, pop_version, relaxations)

    elif element_type == "clause":
        llm_involvement = {
            "used": True,
            "role": "Clause text is classified into one of 30 clause types using LLM (primary) or keyword matching (fallback).",
            "model": settings.qwen_local_model or "keyword_classifier",
            "confidence": None,
            "fallback_used": None,
            "guardrails": ["banned_term_guardrail"],
        }
        plain = f"Individual clause classification for clause type '{key}'."

    elif element_type == "recommendation":
        llm_involvement = {
            "used": True,
            "role": "Recommendation prose may be rephrased by LLM from a fixed template. All numbers are pre-computed; LLM only smooths tone.",
            "model": settings.qwen_local_model or settings.hosted_qwen_model or "template_only",
            "confidence": None,
            "fallback_used": None,
            "guardrails": ["banned_term_guardrail", "number_verification", "entity_verification"],
        }
        plain = f"Strategic recommendation for finding {key}."

    else:
        plain = f"Report section: {key}"

    # Check scoring status
    if element_type == "score" and not lineage:
        plain = f"Score '{title}' has not yet been computed for this assessment."

    return {
        "element_type": element_type,
        "element_key": key,
        "title": title,
        "plain": plain,
        "technical": technical,
        "llm_involvement": llm_involvement,
        "database_provenance": database_provenance,
        "legal_basis": legal_basis,
        "peer_comparison": peer_comparison,
        "lineage": lineage,
        "confidence_note": confidence_note,
        "human_review_status": None,
        "versioning": versioning,
        "last_updated": snap.get("created_at"),
    }


# ── Type-specific builders ───────────────────────────────────

def _explain_score(key: str, notice_id: str, org_id: str, versioning: dict):
    """Build explain data for a score."""
    from app.routers.reports import SCORE_TYPE_MAP
    inv = {v: k for k, v in SCORE_TYPE_MAP.items()}
    otype = {v: k for k, v in SCORE_TYPE_MAP.items()}.get(key)
    if not otype:
        # Try direct mapping
        otype = key  # e.g. "f002" → look up via SCORE_TYPE_MAP values
        for obj_type, fk in SCORE_TYPE_MAP.items():
            if fk == key:
                otype = obj_type
                break

    derived = _sb_get(
        f"derived_data_item?select=derived_data_item_id,object_type,score,value_label,"
        f"confidence_score,source_lineage,formula_version_id,generated_at"
        f"&notice_id=eq.{notice_id}&object_type=eq.{otype}"
        f"&order=generated_at.desc&limit=1"
    )
    if not derived:
        derived = _sb_get(
            f"derived_data_item?select=derived_data_item_id,object_type,score,value_label,"
            f"confidence_score,source_lineage,formula_version_id,generated_at"
            f"&organization_id=eq.{org_id}&object_type=eq.{otype}"
            f"&order=generated_at.desc&limit=1"
        )

    if not derived:
        return "Not yet computed.", {}, {}, "", []

    row = derived[0]
    lineage = row.get("source_lineage", {})
    if isinstance(lineage, str):
        try:
            lineage = json.loads(lineage)
        except Exception:
            log.warning("Failed to parse derived_data_item source_lineage JSON for org %s (object_type=%s); using empty lineage", org_id, otype)
            lineage = {}

    fv_id = row.get("formula_version_id", "")
    formula_key = fv_id.replace("_v1", "").replace("-", "-") if fv_id else key.upper()
    glossary_entry = _FORMULA_GLOSSARY.get(formula_key, {})

    conf = (row.get("confidence_score") or 0) * 100
    confidence_note = f"VCI {conf:.0f}: {_vci_note(conf)}"

    plain = f"{glossary_entry.get('plain', key)}: {row['score']:.1f}/100."
    technical = {
        "what_ran": glossary_entry.get("defined_in", ""),
        "formula": glossary_entry.get("technical", ""),
        "inputs": lineage,
        "output": row["score"],
    }

    db_prov = [{
        "table": "derived_data_item",
        "row_id": row.get("derived_data_item_id", ""),
        "fields_used": ["score", "value_label", "confidence_score", "source_lineage"],
    }]

    return plain, technical, lineage, confidence_note, db_prov


def _explain_finding(key: str, notice_id: str, org_id: str):
    """Build explain data for a finding."""
    findings = _sb_get(
        f"risk_finding?select=finding_id,finding_type_code,severity,score,domain,confidence_score,snapshot_id"
        f"&notice_id=eq.{notice_id}&finding_type_code=eq.{key}&limit=1"
    )
    if not findings:
        findings = _sb_get(
            f"risk_finding?select=finding_id,finding_type_code,severity,score,domain,confidence_score,snapshot_id"
            f"&organization_id=eq.{org_id}&finding_type_code=eq.{key}&limit=1"
        )

    glossary_entry = _FINDING_GLOSSARY.get(key, {})
    domain = ""
    lineage: dict = {}
    db_prov: list[dict] = []

    if findings:
        f = findings[0]
        domain = f.get("domain", "")
        lineage = {
            "finding_id": f.get("finding_id"),
            "severity": f.get("severity"),
            "score": f.get("score"),
            "domain": domain,
            "snapshot_id": f.get("snapshot_id"),
        }
        db_prov = [{"table": "risk_finding", "row_id": f.get("finding_id", ""), "fields_used": ["severity", "score", "domain"]}]

    plain = f"{glossary_entry.get('plain', key)}: This finding was selected deterministically from the fixed catalog because the {domain.replace('_', ' ')} domain had clauses AND maturity was below threshold or ambiguity exceeded threshold."

    technical = {
        "what_ran": "app/services/scoring/findings.py::select_findings",
        "formula": "A finding triggers when domain clauses exist AND (maturity < 70 OR ambiguity > 0.05). Score = 100 - maturity.",
        "catalog_code": key,
        "domain": domain,
    }

    # Legal basis
    legal_refs = _sb_get(
        f"finding_legal_reference?select=reference_id,is_primary,rationale,"
        f"legal_reference(jurisdiction,framework,citation,title,summary,official_url)"
        f"&finding_type_code=eq.{key}&limit=10"
    )
    legal_basis = []
    for lr in legal_refs:
        ref = lr.get("legal_reference", {})
        if not ref:
            continue
        legal_basis.append({
            "framework": ref.get("framework", ""),
            "citation": ref.get("citation", ""),
            "title": ref.get("title", ""),
            "summary": ref.get("summary", ""),
            "official_url": ref.get("official_url", ""),
            "is_primary": lr.get("is_primary", False),
            "rationale": lr.get("rationale", ""),
        })

    return plain, technical, lineage, legal_basis, db_prov


def _explain_domain(key: str):
    """Build explain data for a domain."""
    entry = _DOMAIN_GLOSSARY.get(key, {})
    plain = entry.get("plain", key)
    technical = {"domain_id": key, "description": entry.get("technical", "")}

    # Legal references for this domain
    legal_refs = _sb_get(
        f"legal_reference?select=reference_id,jurisdiction,framework,citation,title,summary,official_url"
        f"&domain_id=eq.{key}&limit=20"
    )
    legal_basis = [
        {
            "framework": lr.get("framework", ""),
            "citation": lr.get("citation", ""),
            "title": lr.get("title", ""),
            "summary": lr.get("summary", ""),
            "official_url": lr.get("official_url", ""),
            "is_primary": False,
            "rationale": "Domain-level legal framework reference.",
        }
        for lr in legal_refs
    ]

    return plain, technical, legal_basis


def _build_peer_comparison(cohort_size, cohort_date, pop_version, relaxations):
    return {
        "cohort_size": cohort_size,
        "benchmark_population_version": pop_version,
        "cohort_date": cohort_date,
        "relaxations": relaxations,
        "how_percentile_computed": "Weighted percentile rank over normalization-weighted peer population (PercentileRank formula over weighted cohort scores).",
    }
