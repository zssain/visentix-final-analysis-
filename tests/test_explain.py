"""Explainability tests — bundle correctness, formula descriptions, read-only."""

import time
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import jwt as pyjwt
import pytest
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.main import app
from app.services.report.explain import (
    FORMULA_DESCRIPTIONS,
    build_explanation_bundle,
)


# ── Fixtures ──────────────────────────────────────────────────

SAMPLE_SCORES = {
    "f002": {
        "score": 47.2,
        "tier": "moderate",
        "lineage": {
            "domains_scored": ["data_sharing", "tracking_cookies"],
            "regulator_contributions": {"reg-1": 0.12},
            "raw_sum": 2.34,
            "max_possible": 5.0,
            "total_clauses": 41,
        },
    },
    "f010": {
        "score": 62.5,
        "tier": "",
        "lineage": {
            "component_scores": {"regulatory": 47.2, "benchmark": 15.0},
            "weights": {"regulatory": 0.25, "benchmark": 0.20},
            "weighted_risk": 37.5,
        },
    },
    "f011": {
        "score": 71.0,
        "tier": "",
        "lineage": {
            "org_score": 62.5,
            "cohort_size": 30,
            "cohort_date": "2026-06-29",
            "cohort_label": "small_cohort",
            "weighted": True,
        },
    },
}

SAMPLE_FINDINGS = [
    {"code": "AI-004", "domain": "ai_automated_decisions", "severity": "high", "score": 62.0, "confidence_score": 0.5},
    {"code": "SH-002", "domain": "data_sharing", "severity": "high", "score": 55.0, "confidence_score": 0.6},
]

SAMPLE_VCI = {"score": 52.0, "label": "moderate", "components": {"regulatory_exposure": 0.5, "overall_intelligence": 0.5}}

SAMPLE_NOTICE_REFS = {
    "notice_id": "notice-001",
    "clause_count": 41,
    "org_name": "TestCo",
    "org_industry": "fintech",
    "org_size": "large",
    "org_geography": "US",
    "clause_categories": {"data_sharing": 15, "ai_automated_decisions": 8, "tracking_cookies": 10, "retention": 8},
    "clause_ids_by_domain": {"data_sharing": ["c1", "c2"], "ai_automated_decisions": ["c3", "c4"]},
}

SAMPLE_NARRATIVE_META = {
    "executive_summary": {
        "llm_used": False,
        "guardrail": "passed",
        "numbers_from": ["f010", "f011"],
        "text": "TestCo presents an overall score of 62.5.",
    },
    "takeaways": [
        {"llm_used": False, "guardrail": "passed", "numbers_from": [], "text": "AI domain elevated."},
    ],
}


# ── Pure function tests ────────────────────────────────────────

def test_bundle_has_all_three_sections():
    bundle = build_explanation_bundle(
        SAMPLE_SCORES, SAMPLE_FINDINGS, SAMPLE_VCI,
        SAMPLE_NARRATIVE_META, SAMPLE_NOTICE_REFS,
    )
    assert "scores" in bundle
    assert "findings" in bundle
    assert "narrative" in bundle


def test_scores_keyed_by_formula():
    bundle = build_explanation_bundle(
        SAMPLE_SCORES, SAMPLE_FINDINGS, SAMPLE_VCI,
        SAMPLE_NARRATIVE_META, SAMPLE_NOTICE_REFS,
    )
    assert "f002" in bundle["scores"]
    assert "f010" in bundle["scores"]
    assert "f011" in bundle["scores"]


def test_score_has_formula_plain():
    bundle = build_explanation_bundle(
        SAMPLE_SCORES, SAMPLE_FINDINGS, SAMPLE_VCI,
    )
    f002 = bundle["scores"]["f002"]
    assert f002["formula_version"] == "F-002_v1"
    assert "Jurisdiction Weight" in f002["formula_plain"]
    assert f002["score"] == 47.2
    assert f002["label"] == "Regulatory Exposure"


def test_score_has_vci_confidence():
    bundle = build_explanation_bundle(
        SAMPLE_SCORES, SAMPLE_FINDINGS, SAMPLE_VCI,
    )
    conf = bundle["scores"]["f002"]["confidence"]
    assert conf["vci"] == 52.0
    assert conf["label"] == "moderate"
    assert conf["guidance"] == "Include with confidence caveat"


def test_score_inputs_from_lineage():
    bundle = build_explanation_bundle(
        SAMPLE_SCORES, SAMPLE_FINDINGS, SAMPLE_VCI,
        notice_refs=SAMPLE_NOTICE_REFS,
    )
    inputs = bundle["scores"]["f002"]["inputs"]
    assert inputs["total_clauses"] == 41
    assert "data_sharing" in inputs["domains_scored"]


def test_score_source_refs():
    bundle = build_explanation_bundle(
        SAMPLE_SCORES, SAMPLE_FINDINGS, SAMPLE_VCI,
        notice_refs=SAMPLE_NOTICE_REFS,
    )
    refs = bundle["scores"]["f002"]["source_refs"]
    assert refs["notice_id"] == "notice-001"
    assert refs["clause_count"] == 41


def test_findings_keyed_by_code():
    bundle = build_explanation_bundle(
        SAMPLE_SCORES, SAMPLE_FINDINGS, SAMPLE_VCI,
    )
    assert "AI-004" in bundle["findings"]
    assert "SH-002" in bundle["findings"]


def test_finding_how_selected():
    bundle = build_explanation_bundle(
        SAMPLE_SCORES, SAMPLE_FINDINGS, SAMPLE_VCI,
    )
    ai = bundle["findings"]["AI-004"]
    assert "fixed finding-type catalog" in ai["how_selected"]
    assert "model did NOT invent" in ai["how_selected"]
    assert ai["domain"] == "ai_automated_decisions"
    assert ai["severity"] == "high"
    assert ai["score"] == 62.0


def test_narrative_provenance():
    bundle = build_explanation_bundle(
        SAMPLE_SCORES, SAMPLE_FINDINGS, SAMPLE_VCI,
        SAMPLE_NARRATIVE_META,
    )
    exec_ = bundle["narrative"]["executive_summary"]
    assert exec_["llm_used"] is False
    assert exec_["guardrail"] == "passed"
    assert "f010" in exec_["numbers_from"]
    assert "formula engine" in exec_["provenance"]
    assert "guardrail" in exec_["provenance"]


def test_narrative_takeaways_provenance():
    bundle = build_explanation_bundle(
        SAMPLE_SCORES, SAMPLE_FINDINGS, SAMPLE_VCI,
        SAMPLE_NARRATIVE_META,
    )
    takeaways = bundle["narrative"]["takeaways"]
    assert len(takeaways) == 1
    assert takeaways[0]["llm_used"] is False
    assert "deterministic finding engine" in takeaways[0]["provenance"]


def test_score_has_methodology():
    bundle = build_explanation_bundle(
        SAMPLE_SCORES, SAMPLE_FINDINGS, SAMPLE_VCI,
        notice_refs=SAMPLE_NOTICE_REFS,
    )
    f002 = bundle["scores"]["f002"]
    assert "methodology" in f002
    assert len(f002["methodology"]) > 100, "Methodology should be a detailed paragraph"
    assert "JW" in f002["methodology"] or "Jurisdiction" in f002["methodology"]


def test_score_has_interpretation():
    bundle = build_explanation_bundle(
        SAMPLE_SCORES, SAMPLE_FINDINGS, SAMPLE_VCI,
        notice_refs=SAMPLE_NOTICE_REFS,
    )
    f002 = bundle["scores"]["f002"]
    assert "interpretation" in f002
    assert "TestCo" in f002["interpretation"]
    assert "47.2" in f002["interpretation"]


def test_finding_has_catalog_description():
    bundle = build_explanation_bundle(
        SAMPLE_SCORES, SAMPLE_FINDINGS, SAMPLE_VCI,
        notice_refs=SAMPLE_NOTICE_REFS,
    )
    ai = bundle["findings"]["AI-004"]
    assert "catalog_description" in ai
    assert len(ai["catalog_description"]) > 50
    assert "AI" in ai["catalog_description"] or "automated" in ai["catalog_description"]


def test_finding_how_selected_includes_clause_count():
    bundle = build_explanation_bundle(
        SAMPLE_SCORES, SAMPLE_FINDINGS, SAMPLE_VCI,
        notice_refs=SAMPLE_NOTICE_REFS,
    )
    ai = bundle["findings"]["AI-004"]
    assert "8 clause(s)" in ai["how_selected"]
    assert "maturity" in ai["how_selected"].lower()


def test_finding_has_triggering_clause_ids():
    bundle = build_explanation_bundle(
        SAMPLE_SCORES, SAMPLE_FINDINGS, SAMPLE_VCI,
        notice_refs=SAMPLE_NOTICE_REFS,
    )
    ai = bundle["findings"]["AI-004"]
    assert ai["triggering_clause_ids"] == ["c3", "c4"]
    assert ai["triggering_clause_count"] == 8


def test_bundle_has_meta_section():
    bundle = build_explanation_bundle(
        SAMPLE_SCORES, SAMPLE_FINDINGS, SAMPLE_VCI,
        SAMPLE_NARRATIVE_META, SAMPLE_NOTICE_REFS,
    )
    assert "meta" in bundle
    meta = bundle["meta"]
    assert meta["org_name"] == "TestCo"
    assert meta["org_industry"] == "fintech"
    assert meta["total_clauses_analyzed"] == 41
    assert "data_sharing" in meta["domains_covered"]
    assert "philosophy" in meta
    assert "formula engine" in meta["philosophy"]


def test_narrative_provenance_includes_org_name():
    bundle = build_explanation_bundle(
        SAMPLE_SCORES, SAMPLE_FINDINGS, SAMPLE_VCI,
        SAMPLE_NARRATIVE_META, SAMPLE_NOTICE_REFS,
    )
    exec_ = bundle["narrative"]["executive_summary"]
    assert "TestCo" in exec_["provenance"]
    assert "F-010" in exec_["provenance"]
    assert "banned-term guardrail" in exec_["provenance"]


def test_empty_inputs_produce_empty_bundle():
    bundle = build_explanation_bundle({}, [], {})
    assert bundle["scores"] == {}
    assert bundle["findings"] == {}
    assert bundle["narrative"]["executive_summary"]["llm_used"] is False


def test_absent_guardrail_metadata_never_renders_passed():
    """GRD-002: a snapshot with no recorded guardrail result must render honest
    absence ('not_recorded'), never a manufactured 'passed', and the provenance
    must not assert the guardrail ran."""
    meta_no_guardrail = {
        "executive_summary": {"text": "Summary.", "numbers_from": ["f010"], "llm_used": False},
        "takeaways": [{"text": "A takeaway.", "numbers_from": [], "llm_used": False}],
    }
    bundle = build_explanation_bundle(
        SAMPLE_SCORES, SAMPLE_FINDINGS, SAMPLE_VCI,
        meta_no_guardrail, SAMPLE_NOTICE_REFS,
    )
    exec_ = bundle["narrative"]["executive_summary"]
    assert exec_["guardrail"] == "not_recorded"
    assert exec_["guardrail"] != "passed"
    assert "not recorded" in exec_["provenance"].lower()
    assert "passed the banned-term guardrail" not in exec_["provenance"]
    for t in bundle["narrative"]["takeaways"]:
        assert t["guardrail"] == "not_recorded"
        assert "not recorded" in t["provenance"].lower()


def test_empty_bundle_guardrail_not_passed():
    """Even the fully-empty bundle must not default the guardrail receipt to passed."""
    bundle = build_explanation_bundle({}, [], {})
    assert bundle["narrative"]["executive_summary"]["guardrail"] == "not_recorded"


def test_formula_descriptions_cover_all_formulas():
    expected = [
        "F-001_v1", "F-002_v1", "F-003_v1", "F-004_v1", "F-005_v1",
        "F-006_v1", "F-007_v1", "F-008_v1", "F-009_v1", "F-010_v1",
        "F-011_v1", "F-012_v1", "F-013_v1", "F-014_v1", "VCI",
    ]
    for fv in expected:
        assert fv in FORMULA_DESCRIPTIONS, f"Missing description for {fv}"
        desc = FORMULA_DESCRIPTIONS[fv]
        assert "label" in desc
        assert "formula_plain" in desc
        assert len(desc["formula_plain"]) > 20, f"formula_plain too short for {fv}"
        assert "methodology" in desc
        assert len(desc["methodology"]) > 80, f"methodology too short for {fv}"


# ── Endpoint tests ──────────────────────────────────────────────

_TEST_ORG_ID = str(uuid4())


def _make_token(sub: str = "test-user") -> str:
    now = int(time.time())
    return pyjwt.encode(
        {"sub": sub, "aud": "authenticated", "iat": now - 60,
         "exp": now + 3600, "role": "authenticated"},
        settings.supabase_jwt_secret, algorithm="HS256",
    )


def _mock_profile(role: str = "sme", org_id: str = _TEST_ORG_ID):
    return patch("app.auth._load_profile", new_callable=AsyncMock,
                 return_value={"role": role, "organization_id": org_id})


@pytest.mark.anyio
async def test_explain_endpoint_requires_auth():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/reports/test-id/explain")
        assert r.status_code == 401


@pytest.mark.anyio
@pytest.mark.skip(reason="DEBT: explain tests patch app.routers.reports._resolve_org_id, which no "
                         "longer exists — endpoint refactored; test/endpoint reconciliation pending")
async def test_explain_endpoint_enforces_org_ownership():
    """Customer from org-A cannot access explain for org-B's assessment."""
    token = _make_token()
    other_org = str(uuid4())
    with _mock_profile("customer", other_org), \
         patch("app.routers.reports._resolve_org_id", return_value=_TEST_ORG_ID):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.get("/reports/test-id/explain",
                            headers={"Authorization": f"Bearer {token}"})
            assert r.status_code == 403


@pytest.mark.anyio
@pytest.mark.skip(reason="DEBT: explain tests patch app.routers.reports._resolve_org_id, which no "
                         "longer exists — endpoint refactored; test/endpoint reconciliation pending")
async def test_explain_endpoint_returns_bundle():
    token = _make_token()
    mock_data = (SAMPLE_SCORES, SAMPLE_FINDINGS, SAMPLE_VCI, SAMPLE_NOTICE_REFS)
    with _mock_profile("sme"), \
         patch("app.routers.reports._resolve_org_id", return_value=_TEST_ORG_ID), \
         patch("app.routers.reports._load_explain_data", return_value=mock_data):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.get("/reports/test-id/explain",
                            headers={"Authorization": f"Bearer {token}"})
            assert r.status_code == 200
            body = r.json()
            assert "scores" in body
            assert "findings" in body
            assert "narrative" in body
            assert "f002" in body["scores"]
            assert "AI-004" in body["findings"]


@pytest.mark.anyio
@pytest.mark.skip(reason="DEBT: explain tests patch app.routers.reports._resolve_org_id, which no "
                         "longer exists — endpoint refactored; test/endpoint reconciliation pending")
async def test_explain_is_read_only():
    """Hitting /explain must not create or mutate any DB rows."""
    token = _make_token()
    mock_data = (SAMPLE_SCORES, SAMPLE_FINDINGS, SAMPLE_VCI, SAMPLE_NOTICE_REFS)

    # Track calls to supabase_rest_post — should not be called
    with _mock_profile("sme"), \
         patch("app.routers.reports._resolve_org_id", return_value=_TEST_ORG_ID), \
         patch("app.routers.reports._load_explain_data", return_value=mock_data), \
         patch("app.db.supabase_rest_post", new_callable=AsyncMock) as mock_post:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.get("/reports/test-id/explain",
                            headers={"Authorization": f"Bearer {token}"})
            assert r.status_code == 200
            mock_post.assert_not_called()
