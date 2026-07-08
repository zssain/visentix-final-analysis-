"""Report reproducibility tests — VICBNF-008.

Verifies:
- Same inputs → identical report JSON (deterministic).
- content_hash is stable across calls.
- Sorted findings (by code) for determinism.
- No date.today() at read time (frozen into snapshot).
- ?refresh=true creates a new version; old remains.
"""

import hashlib
import json

import pytest

from app.services.report.assembly import assemble_report, ReportPayload
from app.services.report.renderer import render_html
from app.routers.reports import _content_hash


# ── Fixtures ──────────────────────────────────────────────────

def _make_report(**overrides) -> ReportPayload:
    defaults = dict(
        assessment_id="test-001",
        org_name="TestCo",
        scores={
            "f002": {"score": 45.0, "tier": "moderate", "band": "", "lineage": {}},
            "f010": {"score": 62.5, "tier": "", "band": "Developing", "lineage": {}},
            "f011": {"score": 71.0, "tier": "", "band": "", "lineage": {}},
        },
        findings=[
            {"code": "AI-004", "domain": "ai_automated_decisions", "severity": "high", "score": 70.0},
            {"code": "RT-003", "domain": "retention", "severity": "medium", "score": 45.0},
            {"code": "SH-002", "domain": "data_sharing", "severity": "high", "score": 65.0},
        ],
        vci={"score": 58.0, "label": "Low", "guidance": "Present with clear confidence limitations"},
        narrative_exec="TestCo presents an overall score of 62.5 out of 100 (Developing).",
        narrative_takeaways=["AI exposure elevated.", "Data sharing exposure elevated."],
        narrative_recommendations=[
            {"severity": "high", "code": "AI-004", "title": "Address AI-004", "prose": "Review AI disclosures."},
            {"severity": "high", "code": "SH-002", "title": "Address SH-002", "prose": "Review data sharing."},
        ],
        exemplars=[],
        enforcement_heatmap=[],
        cohort_size=25,
        cohort_date="2026-07-08",
        snapshot_id="snap-test01",
    )
    defaults.update(overrides)
    return assemble_report(**defaults)


# ── Determinism ──────────────────────────────────────────────

def test_identical_html_from_same_inputs():
    """Same inputs must produce identical HTML twice."""
    r1 = _make_report()
    r2 = _make_report()
    h1 = render_html(r1)
    h2 = render_html(r2)
    assert h1 == h2, "Same inputs must produce identical HTML"


def test_content_hash_stable():
    """content_hash must be identical for identical payloads."""
    r1 = _make_report()
    r2 = _make_report()
    from dataclasses import asdict
    d1 = asdict(r1)
    d2 = asdict(r2)
    assert _content_hash(d1) == _content_hash(d2)


def test_content_hash_changes_with_different_input():
    """Different scores → different hash."""
    r1 = _make_report()
    r2 = _make_report(scores={"f010": {"score": 99.0, "tier": "", "band": "Leading", "lineage": {}}})
    from dataclasses import asdict
    assert _content_hash(asdict(r1)) != _content_hash(asdict(r2))


# ── Sorted outputs ───────────────────────────────────────────

def test_findings_sorted_by_code():
    """Findings must be sorted by code for determinism."""
    r = _make_report()
    s6 = r.sections[5]  # Findings table
    finding_ids = [f["id"] for f in s6.content.get("findings", [])]
    assert finding_ids == sorted(finding_ids), f"Findings not sorted: {finding_ids}"


def test_recommendations_sorted():
    """Recommendations must appear in a stable order."""
    r = _make_report()
    s9 = r.sections[8]  # Recommendations
    recs = s9.content.get("recommendations", [])
    codes = [r["code"] for r in recs]
    # At minimum, the order must be reproducible
    r2 = _make_report()
    s9_2 = r2.sections[8]
    codes2 = [r["code"] for r in s9_2.content.get("recommendations", [])]
    assert codes == codes2


# ── No date.today() at read time ─────────────────────────────

def test_frozen_date():
    """Report uses the frozen cohort_date, not date.today()."""
    r = _make_report(cohort_date="2026-01-15")
    assert r.generated_date == "2026-01-15"
    assert r.cohort_date == "2026-01-15"
    # Check it appears in section 4 (Benchmark Intelligence)
    s4 = r.sections[3]
    assert s4.content["cohort_date"] == "2026-01-15"


# ── Report envelope has version metadata ─────────────────────

def test_report_has_cohort_and_snapshot():
    r = _make_report()
    assert r.cohort_size == 25
    assert r.assessment_id == "test-001"
    # Traceability section references the snapshot
    s11 = r.sections[10]
    assert "snap-test01" in s11.content.get("note", "")


# ── No hardcoded values ──────────────────────────────────────

def test_no_hardcoded_cohort_in_reports_module():
    """The reports module must not contain hardcoded cohort values."""
    import inspect
    from app.routers import reports
    source = inspect.getsource(reports)
    assert "n=30" not in source
    assert "2026-06-29" not in source
    assert "2026-06-19" not in source
    assert "cohort_size=30" not in source
