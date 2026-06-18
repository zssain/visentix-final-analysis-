"""Findings reproducibility tests — same inputs must yield identical findings."""

from collections import Counter

import pytest

from app.services.scoring.findings import (
    DOMAIN_TO_FINDING,
    FindingInput,
    FindingResult,
    select_findings,
)


def _make_input(**kwargs) -> FindingInput:
    defaults = dict(
        organization_id="org-1",
        notice_id="notice-1",
        clause_categories=Counter({
            "data_sharing": 10, "tracking_cookies": 5,
            "retention": 2, "ai_automated_decisions": 3,
            "other": 20,
        }),
        clause_ids_by_domain={
            "data_sharing": [f"c-ds-{i}" for i in range(10)],
            "tracking_cookies": [f"c-trk-{i}" for i in range(5)],
            "retention": [f"c-ret-{i}" for i in range(2)],
            "ai_automated_decisions": [f"c-ai-{i}" for i in range(3)],
            "other": [f"c-oth-{i}" for i in range(20)],
        },
        domain_scores={
            "data_sharing": 60,  # below threshold → fires
            "tracking_cookies": 40,  # below → fires
            "retention": 30,  # below → fires
            "ai_automated_decisions": 45,  # below → fires
        },
        avg_ambiguity_by_domain={
            "data_sharing": 0.02,
            "tracking_cookies": 0.03,
            "retention": 0.06,  # above threshold
            "ai_automated_decisions": 0.01,
        },
        enforcement_matches=[],
        vci_score=55.0,
        formula_version_id="F-002_v1",
        finding_types={},
        recommendations={"SH-002": "rec-sh", "TRK-007": "rec-trk",
                         "RT-003": "rec-rt", "AI-004": "rec-ai"},
    )
    defaults.update(kwargs)
    return FindingInput(**defaults)


# ── Reproducibility ──────────────────────────────────────────

def test_same_inputs_same_findings():
    """Core reproducibility: running twice yields identical results."""
    inp = _make_input()
    r1 = select_findings(inp)
    r2 = select_findings(inp)

    assert len(r1) == len(r2)
    for f1, f2 in zip(r1, r2):
        assert f1.finding_type_code == f2.finding_type_code
        assert f1.domain == f2.domain
        assert f1.severity == f2.severity
        assert f1.score == f2.score
        assert f1.triggering_clause_ids == f2.triggering_clause_ids


def test_deterministic_ordering():
    """Findings come out in deterministic (sorted) domain order."""
    inp = _make_input()
    findings = select_findings(inp)
    domains = [f.domain for f in findings]
    assert domains == sorted(domains)


# ── Catalog selection ────────────────────────────────────────

def test_findings_come_from_catalog():
    """Every finding code must exist in DOMAIN_TO_FINDING."""
    inp = _make_input()
    findings = select_findings(inp)
    valid_codes = set(DOMAIN_TO_FINDING.values())
    for f in findings:
        assert f.finding_type_code in valid_codes, (
            f"Finding {f.finding_type_code} not in catalog"
        )


def test_data_sharing_triggers_sh002():
    inp = _make_input(
        clause_categories=Counter({"data_sharing": 5}),
        clause_ids_by_domain={"data_sharing": ["c1", "c2"]},
        domain_scores={"data_sharing": 40},
    )
    findings = select_findings(inp)
    codes = [f.finding_type_code for f in findings]
    assert "SH-002" in codes


def test_retention_triggers_rt003():
    inp = _make_input(
        clause_categories=Counter({"retention": 2}),
        clause_ids_by_domain={"retention": ["c1"]},
        domain_scores={"retention": 30},
    )
    findings = select_findings(inp)
    codes = [f.finding_type_code for f in findings]
    assert "RT-003" in codes


def test_ai_triggers_ai004():
    inp = _make_input(
        clause_categories=Counter({"ai_automated_decisions": 3}),
        clause_ids_by_domain={"ai_automated_decisions": ["c1"]},
        domain_scores={"ai_automated_decisions": 45},
    )
    findings = select_findings(inp)
    codes = [f.finding_type_code for f in findings]
    assert "AI-004" in codes


# ── Trigger thresholds ───────────────────────────────────────

def test_high_maturity_no_finding():
    """Domain with score >= 70 and low ambiguity should not trigger."""
    inp = _make_input(
        clause_categories=Counter({"data_sharing": 10}),
        clause_ids_by_domain={"data_sharing": ["c1"]},
        domain_scores={"data_sharing": 85},
        avg_ambiguity_by_domain={"data_sharing": 0.01},
    )
    findings = select_findings(inp)
    codes = [f.finding_type_code for f in findings]
    assert "SH-002" not in codes


def test_high_ambiguity_triggers_even_with_good_score():
    """High ambiguity should trigger a finding even if maturity is ok."""
    inp = _make_input(
        clause_categories=Counter({"data_sharing": 10}),
        clause_ids_by_domain={"data_sharing": ["c1"]},
        domain_scores={"data_sharing": 75},  # above threshold
        avg_ambiguity_by_domain={"data_sharing": 0.08},  # above ambiguity threshold
    )
    findings = select_findings(inp)
    codes = [f.finding_type_code for f in findings]
    assert "SH-002" in codes


# ── DC-005: thin coverage ────────────────────────────────────

def test_dc005_fires_on_thin_coverage():
    """DC-005 fires when < 4 non-other domains are present."""
    inp = _make_input(
        clause_categories=Counter({"data_sharing": 5, "other": 20}),
        clause_ids_by_domain={"data_sharing": ["c1"], "other": ["c2"]},
        domain_scores={"data_sharing": 85},  # high maturity → SH-002 won't fire
        avg_ambiguity_by_domain={"data_sharing": 0.01},
    )
    findings = select_findings(inp)
    codes = [f.finding_type_code for f in findings]
    assert "DC-005" in codes


# ── Lineage ──────────────────────────────────────────────────

def test_findings_have_clause_lineage():
    inp = _make_input()
    findings = select_findings(inp)
    for f in findings:
        assert len(f.triggering_clause_ids) > 0


def test_findings_have_recommendation():
    inp = _make_input()
    findings = select_findings(inp)
    for f in findings:
        if f.finding_type_code in inp.recommendations:
            assert f.recommendation_id is not None


def test_findings_have_formula_version():
    inp = _make_input()
    findings = select_findings(inp)
    for f in findings:
        assert f.formula_version_id == "F-002_v1"


# ── Score sanity ─────────────────────────────────────────────

def test_finding_scores_in_range():
    inp = _make_input()
    findings = select_findings(inp)
    for f in findings:
        assert 0 <= f.score <= 100
        assert 0 <= f.confidence_score <= 1
