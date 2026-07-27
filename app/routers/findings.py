"""Findings + Codex endpoints — real data from DB."""

import json

import httpx
from fastapi import APIRouter

from app.auth import AuthenticatedUser, require_role
from app.config import settings
from app.db import get_service_headers

router = APIRouter(prefix="/findings", tags=["findings"])

SB = settings.supabase_url


def _sb_get(path: str) -> list[dict]:
    r = httpx.get(f"{SB}/rest/v1/{path}", headers=get_service_headers(), timeout=15)
    return r.json() if r.status_code == 200 else []


@router.get("/")
async def list_findings(
    user: AuthenticatedUser = require_role("customer", "sme", "admin"),
):
    """List all risk findings from the DB."""
    rows = _sb_get(
        "risk_finding?select=finding_id,finding_type_code,severity,score,domain,"
        "organization_id,confidence_score,notice_id"
        "&order=score.desc&limit=200"
    )
    return rows


@router.get("/codex")
async def codex(
    user: AuthenticatedUser = require_role("customer", "sme", "admin"),
):
    """Return the finding-type catalog from the DB — replaces MOCK M-11."""
    finding_types = _sb_get(
        "finding_type?select=code,title,default_severity,domain,regulator_relevance,sme_authored"
        "&order=code.asc&limit=100"
    )

    # Load recommendations per finding code
    recs = _sb_get(
        "recommendation_library?select=finding_type_code,title,body_template,severity_bucket"
        "&order=finding_type_code.asc&limit=200"
    )
    rec_map: dict[str, list[dict]] = {}
    for r in recs:
        rec_map.setdefault(r["finding_type_code"], []).append(r)

    # Load legal references per finding code
    legal_refs = _sb_get(
        "finding_legal_reference?select=finding_type_code,is_primary,rationale,"
        "legal_reference(reference_id,jurisdiction,framework,citation,title,summary,official_url)"
        "&limit=200"
    )
    legal_map: dict[str, list[dict]] = {}
    for lr in legal_refs:
        ref = lr.get("legal_reference") or {}
        legal_map.setdefault(lr["finding_type_code"], []).append({
            **ref,
            "is_primary": lr.get("is_primary", False),
            "rationale": lr.get("rationale", ""),
        })

    # Build enriched codex entries
    entries = []
    for ft in finding_types:
        code = ft["code"]
        relevance = ft.get("regulator_relevance") or {}
        if isinstance(relevance, str):
            try:
                relevance = json.loads(relevance)
            except Exception:
                relevance = {}

        entries.append({
            "code": code,
            "title": ft.get("title", "").replace("STUB — ", ""),
            "domain": ft.get("domain", ""),
            "default_severity": ft.get("default_severity", "medium"),
            "sme_authored": ft.get("sme_authored", False),
            "regulator_relevance": relevance,
            "recommendations": rec_map.get(code, []),
            "legal_references": legal_map.get(code, []),
        })

    return {"entries": entries, "count": len(entries)}


@router.get("/dashboard-stats")
async def dashboard_stats(
    user: AuthenticatedUser = require_role("customer", "sme", "admin"),
):
    """Real dashboard statistics — replaces all MOCK_ constants.

    F10 org isolation: a `customer` sees only its own organization's stats;
    `sme`/`admin` see the platform-wide view. A customer with no organization
    gets empty stats — never another org's globally-latest scores.
    """
    if user.role == "customer" and not user.organization_id:
        return {
            "overall_score": None, "overall_confidence": 0, "domain_scores": [],
            "finding_count": 0, "high_findings": 0, "medium_findings": 0,
            "assessment_count": 0, "snapshot": {"id": None, "date": None,
            "benchmark_population_version": None},
            "training_stats": {"confirmed": 0, "edited": 0, "dismissed": 0},
        }
    # Customer → scope every query to their org; sme/admin → platform-wide.
    org_clause = (f"&organization_id=eq.{user.organization_id}"
                  if user.role == "customer" else "")

    # Overall score from latest derived_data_item
    overall_rows = _sb_get(
        "derived_data_item?select=score,confidence_score,generated_at"
        "&object_type=eq.overall_intelligence"
        f"{org_clause}"
        "&order=generated_at.desc&limit=1"
    )
    overall_score = overall_rows[0]["score"] if overall_rows else None
    overall_confidence = overall_rows[0].get("confidence_score", 0) if overall_rows else 0

    # Domain scores from latest derived items
    domain_types = [
        ("regulatory_exposure", "Regulatory Exposure"),
        ("disclosure_maturity", "Disclosure Maturity"),
        ("transparency", "Transparency"),
        ("ai_transparency", "AI Transparency"),
        ("compound_risk", "Compound Risk"),
        ("benchmark_percentile", "Benchmark Percentile"),
        ("benchmark_deviation", "Benchmark Deviation"),
        ("enforcement_correlation", "Enforcement Correlation"),
    ]
    domain_scores = []
    for otype, label in domain_types:
        rows = _sb_get(
            f"derived_data_item?select=score,confidence_score"
            f"&object_type=eq.{otype}"
            f"{org_clause}"
            f"&order=generated_at.desc&limit=1"
        )
        domain_scores.append({
            "domain": label,
            "object_type": otype,
            "score": rows[0]["score"] if rows else 0,
            "confidence": rows[0].get("confidence_score", 0) if rows else 0,
        })

    # Finding counts
    findings = _sb_get(
        "risk_finding?select=finding_type_code,severity"
        f"{org_clause}"
        "&order=score.desc&limit=500"
    )
    high_count = sum(1 for f in findings if f.get("severity") == "high")
    medium_count = sum(1 for f in findings if f.get("severity") == "medium")

    # Latest snapshot
    snaps = _sb_get(
        "report_snapshot?select=snapshot_id,created_at,benchmark_population_version"
        f"{org_clause}"
        "&order=created_at.desc&limit=1"
    )
    snapshot = snaps[0] if snaps else None

    # Assessment count
    notices = _sb_get(f"privacy_notice?select=notice_id{org_clause}&limit=500")

    # Training stats
    try:
        from app.services.training import get_training_stats
        training = get_training_stats()
    except Exception:
        training = {"confirmed": 0, "edited": 0, "dismissed": 0}

    return {
        "overall_score": overall_score,
        "overall_confidence": overall_confidence,
        "domain_scores": domain_scores,
        "finding_count": len(findings),
        "high_findings": high_count,
        "medium_findings": medium_count,
        "assessment_count": len(notices),
        "snapshot": {
            "id": snapshot["snapshot_id"] if snapshot else None,
            "date": (snapshot["created_at"] or "")[:10] if snapshot else None,
            "benchmark_population_version": snapshot.get("benchmark_population_version") if snapshot else None,
        },
        "training_stats": training,
    }
