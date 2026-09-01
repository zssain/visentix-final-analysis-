"""RPT-007 — source summary (F05).

Guards the property that makes the block worth printing: it summarises evidence
ALREADY in the snapshot and never invents. A confident-looking summary standing
on nothing is worse than no summary.
"""
import pytest

from app.services.report.assembly import _build_source_summary


def _summary(**over):
    base = dict(
        findings_table=[],
        scores={},
        cohort_size=0,
        cohort_date="2026-08-31",
        vci={},
        guardrail_result=None,
        extraction_quality=None,
        assessment_scope=None,
        enforcement_heatmap=[],
    )
    base.update(over)
    return _build_source_summary(**base)


def test_no_cohort_is_named_as_a_limitation_not_hidden():
    s = _summary(scores={"f010": {"score": 71.0}})
    assert any("No peer cohort" in x for x in s["limitations"])
    driver = next(d for d in s["drivers"] if d["judgment"] == "Overall standing")
    # The EVIDENCE BASE is limited even though the score exists.
    assert driver["strength"] == "limited"
    assert "on its own scale" in driver["why"]


def test_small_cohort_is_indicative_not_settled():
    s = _summary(scores={"f010": {"score": 71.0}}, cohort_size=4)
    assert any("small (4)" in x for x in s["limitations"])
    assert next(d for d in s["drivers"] if d["judgment"] == "Overall standing")["strength"] == "moderate"


def test_large_cohort_is_a_stated_strength():
    s = _summary(scores={"f010": {"score": 71.0}}, cohort_size=30)
    assert any("30 comparable organizations" in x for x in s["strengths"])
    assert next(d for d in s["drivers"] if d["judgment"] == "Overall standing")["strength"] == "strong"


def test_unevidenced_findings_are_counted_not_glossed():
    findings = [
        {"clause_ids": ["c1"], "evidence": [{"clause_id": "c1"}]},
        {"clause_ids": [], "evidence": []},
        {"clause_ids": [], "evidence": []},
    ]
    s = _summary(findings_table=findings)
    assert s["evidence_base"]["findings_clause_evidenced"] == 1
    assert s["evidence_base"]["findings_total"] == 3
    assert any("2 of 3 findings are not tied to a specific clause" in x for x in s["limitations"])
    assert next(d for d in s["drivers"] if d["judgment"] == "Individual findings")["strength"] == "limited"


def test_fully_evidenced_findings_are_a_strength():
    findings = [{"clause_ids": ["c1"], "evidence": [{"clause_id": "c1"}]}]
    s = _summary(findings_table=findings)
    assert any("Every finding cites a specific clause" in x for x in s["strengths"])
    assert next(d for d in s["drivers"] if d["judgment"] == "Individual findings")["strength"] == "strong"


def test_missing_provenance_is_declared_never_defaulted():
    """Hard Rule 7: an unrecorded source must not silently read as recorded."""
    s = _summary()
    assert s["evidence_base"]["source_label"] is None
    assert s["evidence_base"]["captured_at"] is None
    assert any("assessed source was not recorded" in x for x in s["limitations"])
    assert any("captured was not recorded" in x for x in s["limitations"])


def test_scope_provenance_is_used_when_present():
    s = _summary(assessment_scope={"source_label": "privacy.example.com", "captured_at": "2026-07-30"})
    assert s["evidence_base"]["source_label"] == "privacy.example.com"
    assert s["evidence_base"]["captured_at"] == "2026-07-30"
    assert not any("assessed source was not recorded" in x for x in s["limitations"])


def test_notice_only_scope_is_always_stated():
    """The single most important limitation for a forwarded report: we read the
    published notice, not the organisation's actual practice."""
    for kw in ("does not", "internal practice"):
        assert any(kw in x for x in _summary()["limitations"])


def test_no_scores_yields_no_invented_drivers():
    s = _summary()
    assert all(d["judgment"] != "Overall standing" for d in s["drivers"])
    assert all(d["judgment"] != "Regulator exposure" for d in s["drivers"])


def test_confidence_absent_stays_none():
    assert _summary()["evidence_base"]["confidence_score"] is None
    assert _summary(vci={"label": "moderate", "score": 62})["evidence_base"]["confidence_score"] == 62


def test_renderer_shows_honest_absence_for_legacy_snapshots():
    from app.services.report.renderer import _render_source_summary
    html = _render_source_summary({})
    assert "No source summary was recorded" in html
    # It must not imply lineage is missing too — that would be a false alarm.
    assert "Per-figure lineage is unaffected" in html


def test_renderer_emits_drivers_and_limitations():
    from app.services.report.renderer import _render_source_summary
    html = _render_source_summary({"source_summary": _summary(
        scores={"f010": {"score": 71.0}}, cohort_size=30,
        findings_table=[{"clause_ids": ["c1"], "evidence": [{"clause_id": "c1"}]}],
    )})
    assert "Overall standing" in html
    assert "STRONG" in html
    assert "Limitations of this evidence base" in html
