"""Cross-module acceptance tests for the F01/F05 QA remediation.

These tests keep external services at the boundary: decomposition, clause selection,
heatmap construction, report assembly, rendering, snapshot routing, and tenancy all
run through their real local implementations.
"""

from dataclasses import asdict
import hashlib
import time
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import jwt
import pytest
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.main import app
from app.routers.reports import _enforce_snapshot_prose
from app.services import guardrail
from app.services.intake.decompose import decompose
from app.services.report.assembly import assemble_report
from app.services.report.clause_data import heatmap_counts, representative_clauses
from app.services.report.renderer import find_unresolved_template_tokens, render_html
from app.services.scoring.heatmap import build_regulator_heatmap, heatmap_to_serializable
from scripts.eval.golden_notices import FIXTURES
from tests.test_live_pipeline import SAMPLE_NOTICE


DOMAINS = {
    "data_sharing", "tracking_cookies", "consumer_rights", "cross_border",
    "sensitive_data", "retention", "children_teens", "ai_automated_decisions",
}
REGULATOR = {
    "regulator_id": "reg-1", "name": "Fixture regulator", "jurisdiction": "US",
    "priority_weights": {domain: 0.5 for domain in DOMAINS},
    "enforcement_frequency_weight": 0.5,
}


def _clause_rows(text: str) -> list[dict]:
    notice = decompose(text)
    return [
        {
            "clause_id": f"clause-{index}", "category": clause.category,
            "normalized_text": clause.normalized_text, "raw_text": clause.raw_text,
            "nlp_confidence": 0.8, "transparency_score": 60,
            "is_noise": clause.is_noise, "section_title": "Golden notice",
        }
        for index, clause in enumerate(notice.clauses)
    ]


def _build(text: str, *, cohort_size: int = 25, scope: dict | None = None,
           exemplars: list[dict] | None = None, extraction_status: str = "matched"):
    rows = _clause_rows(text) if text else []
    counts = heatmap_counts(rows, {})
    org_clauses = representative_clauses(rows, {})
    findings = []
    if org_clauses:
        domain, clause = next(iter(sorted(org_clauses.items())))
        findings = [{
            "code": "FIX-001", "domain": domain, "severity": "medium", "score": 45,
            "confidence": 0.8, "formula_version": "fixture-v1",
            "clause_ids": [clause["clause_id"]],
            "evidence": [{"clause_id": clause["clause_id"], "section_reference": "Golden notice",
                          "excerpt": clause["text"], "source_reference": "golden fixture"}],
        }]
    receipt = _enforce_snapshot_prose("Stored assessment summary.", [], [])
    report = assemble_report(
        assessment_id="integration-assessment", org_name="Fixture Co",
        scores={
            "f002": {"score": 40, "tier": "moderate", "lineage": {}},
            "f003": {"score": 10, "lineage": {"org_score": 65, "top_quartile_score": 70,
                                                   "n_peers": cohort_size}},
            "f005": {"score": 60}, "f006": {"score": 55}, "f007": {"score": 50},
            "f008": {"score": 45, "lineage": {"risk_scores": {"regulatory": 40}, "cm": 1}},
            "f010": {"score": 58, "band": "Developing"}, "f011": {"score": 62},
        },
        findings=findings, vci={"score": 60, "label": "Moderate"},
        narrative_exec="Stored assessment summary.", narrative_takeaways=[],
        narrative_recommendations=[], exemplars=exemplars or [],
        enforcement_heatmap=heatmap_to_serializable(build_regulator_heatmap([REGULATOR], counts)),
        org_clauses_by_domain=org_clauses, cohort_size=cohort_size,
        cohort_date="2026-08-21", snapshot_id="snapshot-integration",
        guardrail_result=receipt,
        extraction_quality={"status": extraction_status, "report_clause_count": len(org_clauses),
                            "scored_clause_count": len(org_clauses)},
        cohort_methodology={"dimensions": ["industry: retail"], "benchmark_population_version": 7,
                            "as_of_date": "2026-08-21", "low_confidence": cohort_size < 10,
                            "relaxations": ["geography widened"] if cohort_size < 10 else []},
        assessment_scope=scope or {},
    )
    return report, rows, counts, org_clauses


def test_full_rich_notice_flows_across_report_modules():
    scope = {
        "organization_name": {"value": "Fixture Co", "provenance": "user_declared"},
        "industry": {"value": "retail", "provenance": "user_declared"},
        "selected_laws": {"value": ["US-CA"], "provenance": "user_declared"},
    }
    report, _rows, counts, org_clauses = _build(SAMPLE_NOTICE, scope=scope)
    assert len(set(counts) & DOMAINS) >= 5
    heatmap = report.sections[4].content["heatmap"][0]["cells"]
    assert {c["domain"] for c in heatmap if c["evidenced"]} == set(counts) & DOMAINS
    assert {e["domain"] for e in report.sections[7].content["entries"]} == set(org_clauses)
    assert report.sections[5].content["findings"][0]["evidence"][0]["excerpt"]
    assert report.sections[10].content["finding_evidence"]
    assert report.sections[3].content["org_score"] == 65
    html = render_html(report)
    assert "Fixture Co" in html and "user declared" in html
    assert find_unresolved_template_tokens(html) == []
    assert "()" not in html.split("</style>", 1)[1]
    assert guardrail.check_generated_prose("Stored assessment summary.") == []


def test_sparse_golden_notice_neutralizes_unused_domains():
    # A sparse slice of the frozen golden notice: collection + sharing only.
    sparse_text = "\n\n".join(FIXTURES["retail_mid"]["text"].split("\n\n")[:3])
    report, _rows, counts, org_clauses = _build(sparse_text)
    assert 1 <= len(org_clauses) <= 2
    cells = report.sections[4].content["heatmap"][0]["cells"]
    assert sum(not c["evidenced"] for c in cells) >= 6
    assert render_html(report).count('class="heat-na"') >= 6
    assert len(report.sections[7].content["entries"]) == len(org_clauses)
    assert set(counts) <= DOMAINS | {"other"}


def test_empty_clause_set_fires_quality_gate_and_stays_coherent():
    report, _rows, _counts, _org = _build("", extraction_status="insufficient")
    assert report.sections[2].content["disclosure_maturity"] is None
    assert report.sections[3].content["org_score"] is None
    html = render_html(report)
    assert "No substantive notice clauses are available" in html
    assert "Insufficient peer data" in html


def test_no_exemplars_preserves_org_language_with_honest_absence():
    report, _rows, _counts, org_clauses = _build(FIXTURES["retail_strong"]["text"], exemplars=[])
    comparison = report.sections[7].content
    assert len(comparison["entries"]) == len(org_clauses)
    assert comparison["sme_cleaned_available"] is False
    assert all(entry["your_text"] and not entry["exemplar_text"] for entry in comparison["entries"])
    assert all("No comparable approved peer language" in entry["maturity_note"] for entry in comparison["entries"])


def test_tiny_cohort_propagates_named_low_confidence_methodology():
    report, *_ = _build(FIXTURES["retail_mid"]["text"], cohort_size=3)
    report.sections[2].content["vci_score"] = 40
    report.sections[2].content["vci_label"] = "Caution"
    html = render_html(report)
    assert "LOW-CONFIDENCE COHORT" in html
    assert "geography widened" in html
    assert report.sections[2].content["vci_score"] == 40
    assert report.sections[2].content["vci_label"] == "Caution"


def test_minimal_intake_reports_every_uncollected_input_as_absent():
    keys = ("organization_name", "organization_size", "public_private", "geography", "industry",
            "state_footprint", "selected_laws", "data_categories", "business_practices")
    scope = {key: {"value": None, "provenance": "not_recorded"} for key in keys}
    scope["source"] = {"value": "https://example.test/privacy", "provenance": "captured"}
    report, *_ = _build(FIXTURES["retail_mid"]["text"], scope=scope)
    html = render_html(report)
    assert "https://example.test/privacy" in html
    assert html.count("Not recorded") >= len(keys)


@pytest.mark.anyio
async def test_frozen_snapshot_pdf_double_pull_never_reassembles():
    import app.routers.reports as reports
    report, *_ = _build(FIXTURES["retail_strong"]["text"])
    stored = asdict(report)
    rendered = b"%PDF-1.7\nfrozen-fixture"
    now = int(time.time())
    token = jwt.encode({"sub": "sme", "aud": "authenticated", "iat": now - 10, "exp": now + 600,
                        "app_role": "sme"}, settings.supabase_jwt_secret, algorithm="HS256")
    headers = {"Authorization": f"Bearer {token}"}
    transport = ASGITransport(app=app)
    with patch.object(reports, "_load_stored_report", return_value=stored) as load, \
         patch.object(reports, "_assemble_from_live") as assemble, \
         patch("app.services.report.renderer.render_pdf", new=AsyncMock(return_value=rendered)):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            first = await client.get("/reports/integration-assessment/pdf", headers=headers)
            second = await client.get("/reports/integration-assessment/pdf", headers=headers)
    assert first.status_code == second.status_code == 200
    assert hashlib.sha256(first.content).digest() == hashlib.sha256(second.content).digest()
    assert load.call_count == 2
    assemble.assert_not_called()


@pytest.mark.anyio
async def test_cross_tenant_report_and_pdf_are_blocked_before_snapshot_access():
    import app.routers.reports as reports
    mine, other = str(uuid4()), str(uuid4())
    now = int(time.time())
    token = jwt.encode({"sub": "customer", "aud": "authenticated", "iat": now - 10, "exp": now + 600,
                        "app_role": "customer", "organization_id": mine},
                       settings.supabase_jwt_secret, algorithm="HS256")
    headers = {"Authorization": f"Bearer {token}"}
    transport = ASGITransport(app=app)
    with patch.object(reports, "assessment_org_id", return_value=other), \
         patch.object(reports, "_load_stored_report") as load:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            json_response = await client.get("/reports/integration-assessment", headers=headers)
            pdf_response = await client.get("/reports/integration-assessment/pdf", headers=headers)
    assert json_response.status_code == pdf_response.status_code == 403
    load.assert_not_called()


@pytest.mark.anyio
async def test_concurrent_pdf_render_returns_honest_retryable_503():
    import app.routers.reports as reports
    report, *_ = _build(FIXTURES["retail_strong"]["text"])
    now = int(time.time())
    token = jwt.encode({"sub": str(uuid4()), "aud": "authenticated", "iat": now - 10, "exp": now + 600,
                        "app_role": "sme"}, settings.supabase_jwt_secret, algorithm="HS256")
    await reports._PDF_RENDER_SEM.acquire()
    try:
        with patch.object(reports, "_load_stored_report", return_value=asdict(report)):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.get(
                    "/reports/integration-assessment/pdf",
                    headers={"Authorization": f"Bearer {token}"},
                )
    finally:
        reports._PDF_RENDER_SEM.release()
    assert response.status_code == 503
    assert response.headers["retry-after"] == "3"
    assert "retry in a moment" in response.json()["detail"].lower()


@pytest.mark.anyio
async def test_missing_report_returns_specific_404_without_snapshot_fabrication():
    import app.routers.reports as reports
    from fastapi import HTTPException

    now = int(time.time())
    token = jwt.encode({"sub": str(uuid4()), "aud": "authenticated", "iat": now - 10, "exp": now + 600,
                        "app_role": "sme"}, settings.supabase_jwt_secret, algorithm="HS256")
    with patch.object(reports, "_load_stored_report", return_value=None), \
         patch.object(reports, "_assemble_from_live",
                      side_effect=HTTPException(status_code=404, detail="Assessment not found")):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/reports/missing-assessment",
                headers={"Authorization": f"Bearer {token}"},
            )
    assert response.status_code == 404
    assert response.json()["detail"] == "Assessment not found"
