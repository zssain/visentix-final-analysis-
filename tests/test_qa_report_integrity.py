"""Cross-module regressions for the 2026-08 report/intake QA remediation."""

from dataclasses import asdict

import pytest

from app.routers.reports import (
    _content_hash,
    _enforce_snapshot_prose,
    _recommendation_basis_label,
)
from app.services import guardrail
from app.services.report.assembly import assemble_report
from app.services.report.clause_data import (
    heatmap_counts,
    representative_clauses,
    select_comparators,
)
from app.services.report.renderer import (
    _direction,
    _domain_html,
    _heat_band,
    _ramp_key,
    _strip_placeholders,
    find_unresolved_template_tokens,
    render_html,
)
from app.services.scoring.heatmap import build_regulator_heatmap, heatmap_to_serializable
from scripts.audit_exemplar_domains import build_report as build_exemplar_audit
from scripts.ingest.update_findings import RECOMMENDATIONS


SLUGS = {"SH": "data_sharing", "RT": "retention"}
REGULATOR = {
    "regulator_id": "reg-1",
    "name": "Example regulator",
    "jurisdiction": "US",
    "priority_weights": {"data_sharing": 0.8, "retention": 0.6},
    "enforcement_frequency_weight": 0.5,
}


def _report(**overrides):
    values = {
        "assessment_id": "assessment-1",
        "org_name": "Example Co",
        "scores": {
            "f010": {"score": 82, "band": "Mature"},
            "f003": {"score": 12, "lineage": {"org_score": 76, "top_quartile_score": 70, "n_peers": 25}},
            "f011": {"score": 80},
            "f005": {"score": 75},
            "f008": {"score": 60, "lineage": {"risk_scores": {"ai": 58, "regulatory": 45}, "cm": 1.2}},
        },
        "findings": [],
        "vci": {"score": 70, "label": "High"},
        "narrative_exec": "Stored assessment summary.",
        "narrative_takeaways": [],
        "narrative_recommendations": [],
        "exemplars": [],
        "enforcement_heatmap": [],
        "cohort_size": 25,
        "cohort_date": "2026-08-21",
    }
    values.update(overrides)
    return assemble_report(**values)


def test_clause_mapping_keeps_other_in_denominator_and_marks_evidence():
    rows = [
        {"clause_id": "a", "domain_id": "SH", "is_noise": False},
        {"clause_id": "b", "category": "other", "is_noise": False},
        {"clause_id": "noise", "domain_id": "RT", "is_noise": True},
    ]
    counts = heatmap_counts(rows, SLUGS)
    assert counts == {"data_sharing": 1, "other": 1}
    grid = build_regulator_heatmap([REGULATOR], counts)
    sharing = next(cell for cell in grid[0].cells if cell.domain == "data_sharing")
    retention = next(cell for cell in grid[0].cells if cell.domain == "retention")
    assert sharing.clause_density == 0.5 and sharing.evidenced is True
    assert retention.clause_density == 0 and retention.evidenced is False
    assert _heat_band(retention.intensity, retention.evidenced) == "heat-na"


@pytest.mark.parametrize("rows", [
    [
        {"clause_id": "high", "domain_id": "SH", "normalized_text": "H" * 40, "nlp_confidence": 0.95},
        {"clause_id": "mid", "domain_id": "SH", "normalized_text": "M" * 40, "nlp_confidence": 0.60},
        {"clause_id": "low", "domain_id": "SH", "normalized_text": "L" * 40, "nlp_confidence": 0.55},
    ],
    [
        {"clause_id": "low", "domain_id": "SH", "normalized_text": "L" * 40, "nlp_confidence": 0.55},
        {"clause_id": "mid", "domain_id": "SH", "normalized_text": "M" * 40, "nlp_confidence": 0.60},
        {"clause_id": "high", "domain_id": "SH", "normalized_text": "H" * 40, "nlp_confidence": 0.95},
    ],
])
def test_representative_clause_is_true_max_wins(rows):
    assert representative_clauses(rows, SLUGS)["data_sharing"]["clause_id"] == "high"


def test_representative_clause_excludes_noise_short_text_and_breaks_ties_stably():
    rows = [
        {"clause_id": "z", "domain_id": "SH", "normalized_text": "Z" * 40, "nlp_confidence": 0.8},
        {"clause_id": "a", "domain_id": "SH", "normalized_text": "A" * 40, "nlp_confidence": 0.8},
        {"clause_id": "noise", "domain_id": "SH", "normalized_text": "N" * 40, "nlp_confidence": 1.0, "is_noise": True},
        {"clause_id": "short", "domain_id": "RT", "normalized_text": "too short", "nlp_confidence": 1.0},
    ]
    selected = representative_clauses(rows, SLUGS)
    assert selected["data_sharing"]["clause_id"] == "z"
    assert "retention" not in selected


def test_comparator_gate_is_domain_similarity_maturity_and_approval_strict():
    org = {"data_sharing": {"embedding": [1, 0], "transparency_score": 50, "text": "Org text"}}
    rows = [
        {"clause_id": "wrong-domain", "domain_id": "RT", "embedding": [1, 0], "transparency_score": 90, "is_exemplar": True, "exemplar_status": "approved", "raw_text": "Wrong"},
        {"clause_id": "immature", "domain_id": "SH", "embedding": [1, 0], "transparency_score": 49, "is_exemplar": True, "exemplar_status": "approved", "raw_text": "Immature"},
        {"clause_id": "unapproved", "domain_id": "SH", "embedding": [1, 0], "transparency_score": 90, "is_exemplar": True, "exemplar_status": "candidate", "raw_text": "Candidate"},
        {"clause_id": "accepted", "domain_id": "SH", "embedding": [1, 0], "transparency_score": 70, "is_exemplar": True, "exemplar_status": "approved", "raw_text": "Approved comparator"},
    ]
    assert [row["clause_id"] for row in select_comparators(org, rows, SLUGS)] == ["accepted"]
    assert select_comparators(org, rows, SLUGS, similarity_fn=lambda _a, _b: 0.29) == []
    assert select_comparators({"data_sharing": {"transparency_score": 50}}, rows, SLUGS) == []


def test_exemplar_audit_reports_misfiled_domain_without_mutation():
    exemplar = {"clause_id": "ex-1", "domain_id": "SH", "embedding": [0, 1], "is_exemplar": True, "exemplar_status": "approved"}
    corpus = [
        {"clause_id": "sh", "domain_id": "SH", "embedding": [1, 0], "is_exemplar": False},
        {"clause_id": "rt", "domain_id": "RT", "embedding": [0, 1], "is_exemplar": False},
    ]
    before = (dict(exemplar), [dict(row) for row in corpus])
    report = build_exemplar_audit([exemplar], corpus)
    assert report[0]["filed_domain"] == "data_sharing"
    assert report[0]["similarity_assessed_domain"] == "retention"
    assert report[0]["disagreement"] is True
    assert before == (exemplar, corpus)


def test_section4_uses_pgms_lineage_and_missing_lineage_is_honest_absence():
    report = _report()
    section = report.sections[3].content
    assert section["org_score"] == 76
    assert section["measure_label"] == "Governance Maturity (PGMS)"
    assert section["formula_ids"] == {"comparison": "F-003", "percentile": "F-011"}

    missing = _report(scores={"f010": {"score": 99}, "f003": {"score": 20, "lineage": {"reason": "no_peers"}}, "f011": {"score": 0}})
    assert missing.sections[3].content["org_score"] is None
    assert "A stored peer comparison is not available" not in render_html(missing)  # PDF uses its own honest-absence copy.
    assert "Insufficient peer data" in render_html(missing)


def test_missing_vci_remains_honest_absence_in_assembly_and_render():
    report = _report(vci={"score": None, "label": "not_recorded"})
    assert report.sections[2].content["vci_score"] is None
    html = render_html(report)
    dashboard = html[html.index("Risk Dashboard"):html.index("Benchmark Intelligence")]
    assert "Confidence (VCI)" in dashboard
    assert "Not recorded</text>" in dashboard


def test_empty_clause_quality_suppresses_parse_dependent_metrics_and_renders_notice():
    report = _report(extraction_quality={"status": "insufficient", "report_clause_count": 0, "scored_clause_count": 0})
    dashboard = report.sections[2].content
    assert dashboard["disclosure_maturity"] is None
    assert report.sections[3].content["org_score"] is None
    html = render_html(report)
    assert "No substantive notice clauses are available" in html
    assert "75.0" not in html


def test_heatmap_render_counts_real_evidence_and_neutralizes_empty_cells():
    grid = heatmap_to_serializable(build_regulator_heatmap([REGULATOR], {"data_sharing": 1}))
    report = _report(enforcement_heatmap=grid)
    html = render_html(report)
    assert "1 of 8" in html
    assert "Regulator baseline" in html
    assert 'class="heat-na"' in html


def test_template_cleanup_gate_and_customer_evidence_braces():
    source = "how consumers can submit a request ({consumer_rights}), the verification process"
    cleaned = _strip_placeholders(source)
    assert "()" not in cleaned and " ," not in cleaned and "{" not in cleaned
    assert _strip_placeholders("Fully authored prose.") == "Fully authored prose."
    assert find_unresolved_template_tokens('Customer evidence: {"key": true}') == []
    with pytest.raises(guardrail.GuardrailError):
        _enforce_snapshot_prose("Summary", [], [{"title": "Title", "prose": "Review {consumer_rights}."}])

    receipt = _enforce_snapshot_prose("Summary", [], [{"title": "Title", "prose": "Review the stored disclosure."}])
    finding = {"code": "SH-002", "domain": "data_sharing", "severity": "high", "score": 50,
               "evidence": [{"clause_id": "c1", "section_reference": "Sharing", "excerpt": "Literal {token} <source> & text"}]}
    html = render_html(_report(findings=[finding], guardrail_result=receipt))
    assert "Literal {token} &lt;source&gt; &amp; text" in html


def test_customer_evidence_with_guardrail_vocabulary_is_escaped_not_reclassified_as_prose():
    receipt = _enforce_snapshot_prose("Stored assessment summary.", [], [])
    finding = {
        "code": "SH-002", "domain": "data_sharing", "severity": "high", "score": 50,
        "evidence": [{"clause_id": "c1", "section_reference": "Sharing",
                      "excerpt": "Customer text says <script>alert(1)</script> and uses the word violation."}],
    }
    html = render_html(_report(findings=[finding], guardrail_result=receipt))
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "uses the word violation" in html
    assert "<script>alert(1)</script>" not in html


def test_compound_drivers_findings_recommendations_traceability_and_scope_render():
    finding = {
        "code": "SH-002", "domain": "data_sharing", "severity": "high", "score": 60,
        "confidence": 0.82, "formula_version": "fv-2", "clause_ids": ["c-1"],
        "evidence": [{"clause_id": "c-1", "section_reference": "Sharing", "excerpt": "A < B & C", "source_reference": "https://example.test/p?a=1&b=2"}],
    }
    rec = {"severity": "high", "code": "SH-002", "title": "Clarify sharing", "prose": "Clarify the stored disclosure.",
           "basis_label": "Peer benchmark context", "source_note": "Authored library note", "evidence": finding["evidence"]}
    scope = {"industry": {"value": "retail", "provenance": "user_declared"}, "selected_laws": {"value": None, "provenance": "not_recorded"}}
    receipt = _enforce_snapshot_prose("Stored assessment summary.", [], [rec])
    html = render_html(_report(findings=[finding], narrative_recommendations=[rec], assessment_scope=scope, guardrail_result=receipt))
    compound = html[html.index("Compound Risk Drivers"):]
    assert compound.index("AI Transparency Gap") < compound.index("Regulatory Exposure")
    assert "Correlation multiplier: 1.20" in html
    assert "A &lt; B &amp; C" in html
    assert "Peer benchmark context" in html and "Authored library note" in html
    assert "Assessment Scope" in html and "user declared" in html and "Not recorded" in html


def test_scope_changes_hash_but_volatile_methodology_date_does_not():
    first = asdict(_report(assessment_scope={"industry": {"value": "retail", "provenance": "user_declared"}},
                           cohort_methodology={"as_of_date": "2026-08-20", "benchmark_population_version": 7}))
    second = asdict(_report(assessment_scope={"industry": {"value": "retail", "provenance": "user_declared"}},
                            cohort_methodology={"as_of_date": "2026-08-21", "benchmark_population_version": 7}))
    changed = asdict(_report(assessment_scope={"industry": {"value": "healthcare", "provenance": "user_declared"}},
                             cohort_methodology={"as_of_date": "2026-08-21", "benchmark_population_version": 7}))
    assert _content_hash(first) == _content_hash(second)
    assert _content_hash(first) != _content_hash(changed)


@pytest.mark.parametrize("copy", [
    "Selected-scope requirement context",
    "Regulator sensitivity context",
    "Peer benchmark context",
    "General requirement context (outside selected scope)",
    "Basis not recorded",
    "No authored recommendation exists for this finding type yet.",
])
def test_recommendation_basis_copy_passes_guardrail(copy):
    guardrail.enforce(copy)


# ── Bucket A closeouts (RPT-005/008/009/010 + RPT-001/002/004/016 guards) ──────

def test_finding_without_confidence_shows_honest_absence_not_global_vci():
    # RPT-005: a finding with no per-finding confidence must NOT inherit the
    # global VCI label ("High" here) — Section 6 stores None (renderer/React map
    # that to "Not recorded"). A finding WITH a real confidence keeps it.
    bare = {"code": "SH-002", "domain": "data_sharing", "severity": "high", "score": 50}
    report = _report(findings=[bare], vci={"score": 70, "label": "High"})
    assert report.sections[5].content["findings"][0]["confidence"] is None

    scored = {"code": "RT-003", "domain": "retention", "severity": "medium",
              "score": 40, "confidence": 0.82}
    report2 = _report(findings=[scored], vci={"score": 70, "label": "High"})
    assert report2.sections[5].content["findings"][0]["confidence"] == 0.82


@pytest.mark.parametrize("finding,selected_laws,expected", [
    # 1. obligation in a selected law -> scoped requirement (strongest signal)
    ({"obligation_refs": [{"jurisdiction": "CCPA"}]}, {"CCPA"},
     "Selected-scope requirement context"),
    # 2. enforcement outranks an out-of-scope obligation
    ({"obligation_refs": [{"jurisdiction": "CCPA"}], "enforcement_refs": [{"id": "x"}]},
     {"GDPR"}, "Regulator sensitivity context"),
    # 3. benchmark when no obligation/enforcement matches
    ({"benchmark_reference": "peer-x"}, set(), "Peer benchmark context"),
    # 4. RPT-009 new state: obligation exists but is outside the selected scope
    ({"obligation_refs": [{"jurisdiction": "CCPA"}]}, {"GDPR"},
     "General requirement context (outside selected scope)"),
    # 5. nothing stored -> honest absence
    ({}, set(), "Basis not recorded"),
])
def test_recommendation_basis_classification_matrix(finding, selected_laws, expected):
    # RPT-009: basis derived from STORED refs only, never guessed.
    assert _recommendation_basis_label(finding, selected_laws) == expected


@pytest.mark.parametrize("code", sorted(RECOMMENDATIONS))
def test_every_authored_template_strips_clean(code):
    # RPT-008: no authored recommendation template can leave a "{token}", a
    # stray brace, or an emptied "()" after placeholder stripping.
    stripped = _strip_placeholders(RECOMMENDATIONS[code]["body_template"])
    assert "{" not in stripped and "}" not in stripped, code
    assert "()" not in stripped, code
    assert find_unresolved_template_tokens(stripped) == [], code


def test_opposite_direction_metrics_at_equal_value_get_opposite_bands():
    # RPT-010: a maturity metric (inverted) and an exposure metric (non-inverted)
    # at the SAME value must land in opposite bands — proves direction is wired
    # to colour, not merely captioned.
    assert _ramp_key(20.0, invert=True) != _ramp_key(20.0, invert=False)
    assert _ramp_key(20.0, invert=True) == "elevated"   # low maturity = bad
    assert _ramp_key(20.0, invert=False) == "low"       # low exposure = good
    assert _direction(True) != _direction(False)


def test_section4_percentile_threshold_invariant_holds_and_ignores_f010():
    # RPT-001: F-010 overall is deliberately inconsistent (30) with the PGMS
    # lineage. Section 4 must source org_score from F-003 lineage (80), so the
    # percentile>=75 <=> org_score>=top_quartile invariant holds.
    report = _report(scores={
        "f010": {"score": 30, "band": "trap"},
        "f003": {"score": 15, "lineage": {"org_score": 80, "top_quartile_score": 70, "n_peers": 30}},
        "f011": {"score": 88},
        "f008": {"score": 60, "lineage": {"risk_scores": {"ai": 58}, "cm": 1.2}},
    })
    s4 = report.sections[3].content
    assert s4["org_score"] == 80  # from F-003 lineage, never F-010 (30)
    assert (s4["percentile"] >= 75) == (s4["org_score"] >= s4["top_quartile_score"])


def test_mismatch_extraction_quality_also_suppresses_parse_dependent_metrics():
    # RPT-004: the "mismatch" branch (counts diverge, both nonzero) must suppress
    # maturity/benchmark exactly like the "insufficient" (zero) branch.
    report = _report(extraction_quality={"status": "mismatch",
                                         "report_clause_count": 2, "scored_clause_count": 9})
    assert report.sections[2].content["disclosure_maturity"] is None
    assert report.sections[3].content["org_score"] is None


def test_comparator_suppressed_when_embedding_missing():
    # RPT-002: a missing embedding (org side OR exemplar side) suppresses the
    # comparator; it never falls through to first-row selection.
    exemplar_no_embedding = [{"is_exemplar": True, "exemplar_status": "approved",
                              "domain_id": "SH", "transparency_score": 90,
                              "normalized_text": "peer language", "clause_id": "e1"}]
    org = {"data_sharing": {"text": "we share data", "transparency_score": 40,
                            "embedding": [0.1, 0.2, 0.3]}}
    assert select_comparators(org, exemplar_no_embedding, SLUGS) == []

    org_no_embedding = {"data_sharing": {"text": "we share", "transparency_score": 40}}
    good_exemplar = [{"is_exemplar": True, "exemplar_status": "approved",
                      "domain_id": "SH", "transparency_score": 90,
                      "normalized_text": "peer", "clause_id": "e2", "embedding": [0.1, 0.2, 0.3]}]
    assert select_comparators(org_no_embedding, good_exemplar, SLUGS) == []


def test_taxonomy_labels_are_controlled_never_naive_titlecase():
    # RPT-016: the QA-named defective strings never render; controlled labels do.
    grid = heatmap_to_serializable(build_regulator_heatmap([REGULATOR], {"data_sharing": 1}))
    html = render_html(_report(enforcement_heatmap=grid))
    for bad in ("Ai Automated Decisions", "Tracking Cookies", "Cross Border"):
        assert bad not in html
    assert "AI &amp; Automated Decisions" in html
    assert "Cross-Border Transfers" in html
    assert _domain_html("ai_automated_decisions") == "AI &amp; Automated Decisions"
