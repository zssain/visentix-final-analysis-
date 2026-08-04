"""GRD-001 — the banned-term guardrail actually runs on the report path.

Proves generated prose entering a snapshot is guardrailed (fail closed on a
banned term, e.g. a poisoned recommendation_library.body_template) and that the
real outcome is recorded in Section 11 lineage (what GRD-002's receipt displays).
"""

import pytest

from app.routers.reports import _enforce_snapshot_prose
from app.services.guardrail import GuardrailError
from app.services.report.assembly import assemble_report


CLEAN_EXEC = "Acme presents an overall privacy intelligence score of 62.0 out of 100."
CLEAN_TAKEAWAYS = ["The data sharing domain presents elevated exposure (finding C-101)."]
CLEAN_RECS = [{"severity": "high", "code": "C-101", "title": "Strengthen data sharing",
               "prose": "Review and clarify data sharing disclosures to reduce exposure."}]


def test_clean_prose_passes_and_records_result():
    result = _enforce_snapshot_prose(CLEAN_EXEC, CLEAN_TAKEAWAYS, CLEAN_RECS)
    assert result["status"] == "passed"
    # exec(1) + takeaway(1) + rec title(1) + rec prose(1) = 4 non-empty strings checked
    assert result["strings_checked"] == 4


def test_banned_term_in_recommendation_body_fails_closed():
    """A banned verdict term seeded into a recommendation body_template must abort the build."""
    poisoned = [{"severity": "high", "code": "C-101", "title": "Fix it",
                 "prose": "This clause is a clear violation of the law and the company is liable."}]
    with pytest.raises(GuardrailError):
        _enforce_snapshot_prose(CLEAN_EXEC, CLEAN_TAKEAWAYS, poisoned)


def test_banned_term_in_exec_summary_fails_closed():
    with pytest.raises(GuardrailError):
        _enforce_snapshot_prose(
            "Acme is non-compliant with CCPA.", CLEAN_TAKEAWAYS, CLEAN_RECS)


def test_contraction_bypass_caught_on_report_path():
    """GRD-003 + GRD-001 together: a contraction-wrapped verdict in a takeaway is caught."""
    with pytest.raises(GuardrailError):
        _enforce_snapshot_prose(
            CLEAN_EXEC,
            ["The company's practice violates the vendor's terms."],
            CLEAN_RECS,
        )


def test_assembly_records_guardrail_result_in_lineage():
    payload = assemble_report(
        assessment_id="a1", org_name="Acme",
        scores={"f010": {"score": 62}}, findings=[], vci={"label": "High", "score": 80},
        narrative_exec=CLEAN_EXEC, narrative_takeaways=CLEAN_TAKEAWAYS,
        narrative_recommendations=CLEAN_RECS, exemplars=[], enforcement_heatmap=[],
        guardrail_result={"status": "passed", "strings_checked": 4},
    )
    s11 = next(s for s in payload.sections if s.number == 11)
    assert s11.content["guardrail"] == {"status": "passed", "strings_checked": 4}


def test_assembly_defaults_guardrail_to_not_recorded():
    """Without a real result the lineage says not_recorded — never a fake pass (GRD-002)."""
    payload = assemble_report(
        assessment_id="a1", org_name="Acme",
        scores={}, findings=[], vci={}, narrative_exec="", narrative_takeaways=[],
        narrative_recommendations=[], exemplars=[], enforcement_heatmap=[],
    )
    s11 = next(s for s in payload.sections if s.number == 11)
    assert s11.content["guardrail"] == {"status": "not_recorded"}
