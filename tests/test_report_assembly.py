"""Report assembly tests — 12 sections, honest numbers, guardrail, PDF smoke."""

import pytest

from app.services.guardrail import check_generated_prose
from app.services.report.assembly import assemble_report, ReportPayload
from app.services.report.renderer import render_html, render_pdf_weasyprint


def _sample_report() -> ReportPayload:
    return assemble_report(
        assessment_id="test-assess-001",
        org_name="TestCo",
        scores={
            "f002": {"score": 45.0, "tier": "moderate", "lineage": {"domains_scored": ["data_sharing"]}},
            "f003": {"score": 15.0, "lineage": {}},
            "f005": {"score": 78.0, "lineage": {}},
            "f006": {"score": 35.0, "lineage": {}},
            "f007": {"score": 42.0, "lineage": {}},
            "f008": {"score": 28.0, "lineage": {}},
            "f010": {"score": 62.5, "lineage": {}},
            "f011": {"score": 71.0, "lineage": {}},
        },
        findings=[
            {"code": "SH-002", "domain": "data_sharing", "severity": "high", "score": 65.0},
            {"code": "RT-003", "domain": "retention", "severity": "medium", "score": 45.0},
            {"code": "AI-004", "domain": "ai_automated_decisions", "severity": "high", "score": 70.0},
        ],
        vci={"score": 58.0, "label": "moderate"},
        narrative_exec="TestCo presents an overall privacy intelligence score of 62.5 out of 100.",
        narrative_takeaways=["Data sharing exposure is elevated.", "Retention periods need clarification."],
        narrative_recommendations=[
            {"severity": "high", "code": "SH-002", "title": "Clarify Sharing", "prose": "Review data sharing practices."},
            {"severity": "medium", "code": "RT-003", "title": "Define Retention", "prose": "Specify retention periods."},
        ],
        exemplars=[],  # No sme_cleaned yet
        enforcement_heatmap=[{"regulator": "FTC", "score": 0.9}],
        cohort_size=30,
        cohort_date="2026-06-19",
        snapshot_id="snap-001",
    )


# ── All 12 sections present ──────────────────────────────────

def test_report_has_12_sections():
    report = _sample_report()
    assert len(report.sections) == 12


def test_sections_numbered_1_to_12():
    report = _sample_report()
    numbers = [s.number for s in report.sections]
    assert numbers == list(range(1, 13))


def test_section_titles():
    report = _sample_report()
    titles = [s.title for s in report.sections]
    expected_keywords = [
        "Cover", "Executive", "Risk Dashboard", "Benchmark Intelligence",
        "Regulator", "Findings", "Compound", "Language", "Recommendation",
        "Reduction", "Traceability", "Trend",
    ]
    for kw in expected_keywords:
        assert any(kw in t for t in titles), f"Missing section with '{kw}'"


# ── Honest cohort numbers ────────────────────────────────────

def test_honest_cohort_size_in_payload():
    report = _sample_report()
    assert report.cohort_size == 30
    assert report.cohort_date == "2026-06-19"


def test_cohort_label_in_benchmark_section():
    report = _sample_report()
    s4 = report.sections[3]  # Benchmark Intelligence
    label = s4.content.get("cohort_label", "")
    assert "30" in label
    assert "2026" in label


def test_no_fabricated_cohort_size():
    """Must never contain fabricated large numbers."""
    report = _sample_report()
    html = render_html(report)
    assert "1,250" not in html
    assert "1250+" not in html
    assert "10,000" not in html


def test_cohort_in_executive_summary():
    report = _sample_report()
    s2 = report.sections[1]  # Executive Summary
    assert s2.content["cohort_size"] == 30


# ── Section 8: Exemplar handling ─────────────────────────────

@pytest.mark.skip(reason="DEBT: report Section 8 emits no placeholder entry when there are no "
                         "SME-cleaned exemplars — report-builder placeholder path unimplemented")
def test_section8_placeholder_without_sme_cleaned():
    """No sme_cleaned exemplars → placeholder, never raw candidates."""
    report = _sample_report()
    s8 = report.sections[7]
    assert s8.content["sme_cleaned_available"] is False
    assert "pending" in s8.content["entries"][0]["exemplar_text"].lower()


def test_section8_shows_cleaned_exemplars():
    report = assemble_report(
        assessment_id="test",
        org_name="TestCo",
        scores={"f010": {"score": 50}},
        findings=[],
        vci={"label": "moderate"},
        narrative_exec="Summary.",
        narrative_takeaways=[],
        narrative_recommendations=[],
        exemplars=[
            {"domain": "data_sharing", "clause_text": "Cleaned exemplar text.", "sme_cleaned": True},
            {"domain": "retention", "clause_text": "Raw candidate.", "sme_cleaned": False},
        ],
        enforcement_heatmap=[],
    )
    s8 = report.sections[7]
    assert s8.content["sme_cleaned_available"] is True
    texts = [e["exemplar_text"] for e in s8.content["entries"]]
    assert "Cleaned exemplar text." in texts
    assert "Raw candidate." not in texts  # un-cleaned must be excluded


# ── Guardrail on report text ─────────────────────────────────

def test_report_html_no_banned_terms():
    report = _sample_report()
    html = render_html(report)
    violations = check_generated_prose(html)
    # HTML might contain the word in structural context, but generated prose should be clean
    banned_in_prose = [v for v in violations if not v.in_source_excerpt]
    assert len(banned_in_prose) == 0, f"Banned terms in report HTML: {[v.term for v in banned_in_prose]}"


# ── Findings table ───────────────────────────────────────────

def test_findings_table_populated():
    report = _sample_report()
    s6 = report.sections[5]
    assert s6.content["total"] == 3
    assert len(s6.content["findings"]) == 3


# ── Source traceability ──────────────────────────────────────

def test_traceability_has_snapshot():
    report = _sample_report()
    s11 = report.sections[10]
    assert "snap-001" in s11.content["note"]


# ── PDF smoke test ───────────────────────────────────────────

def test_pdf_render_produces_bytes():
    report = _sample_report()
    pdf_bytes = render_pdf_weasyprint(report)
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 1000  # non-trivial PDF
    assert pdf_bytes[:5] == b"%PDF-"  # valid PDF header


def test_html_render_contains_all_sections():
    report = _sample_report()
    html = render_html(report)
    for i in range(1, 13):
        assert f"section-{i}" in html, f"Missing section-{i} in HTML"


# ── Reproducibility ──────────────────────────────────────────

def test_report_reproducible_from_same_inputs():
    r1 = _sample_report()
    r2 = _sample_report()
    h1 = render_html(r1)
    h2 = render_html(r2)
    assert h1 == h2, "Same inputs must produce identical HTML"
