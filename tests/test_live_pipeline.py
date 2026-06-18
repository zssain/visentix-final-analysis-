"""Phase 5.2 live pipeline tests — end-to-end scoring with VCI and lineage."""

import json
from collections import Counter

import pytest

from app.services.intake.decompose import decompose
from app.services.pipeline import score_notice

# Sample notice matching the corpus structure
SAMPLE_NOTICE = """
# Privacy Policy

## Information We Collect
We collect your name, email address, and browsing data when you use our services.
We use cookies and tracking pixels for analytics and advertising purposes.

## How We Share Your Data
We share your personal information with third-party service providers who help us
operate our platform. We may disclose data to advertising partners.

## Your Rights
You have the right to access, delete, and correct your personal data.
You may opt out of data sales at any time by contacting us.

## Data Retention
We retain your data for as long as necessary to fulfill the purposes described.

## International Transfers
Your data may be transferred to countries outside your jurisdiction.
We use standard contractual clauses for EU data transfers.

## Children's Privacy
Our services are not directed to children under 13. We do not knowingly collect
data from minors.

## AI and Automated Decisions
We use automated systems to personalize content and detect fraud.
You may request human review of automated decisions that affect you.

## Sensitive Data
We may collect health-related data with your explicit consent. Biometric data
is processed under strict security measures.
"""

SAMPLE_REGULATORS = [
    {"id": "FTC", "jurisdiction": "US-FED", "efw": 0.9,
     "rpw": {"data_sharing": 0.9, "tracking_cookies": 0.9, "sensitive_data": 0.9,
             "consumer_rights": 0.6, "children_teens": 0.9, "retention": 0.6,
             "cross_border": 0.4, "ai_automated_decisions": 0.8}},
    {"id": "CPPA", "jurisdiction": "US-CA", "efw": 0.7,
     "rpw": {"data_sharing": 0.9, "tracking_cookies": 0.9, "sensitive_data": 0.8,
             "consumer_rights": 0.9, "retention": 0.7, "cross_border": 0.5,
             "ai_automated_decisions": 0.9}},
]

JW = {"US-FED": 0.9, "US-CA": 1.0, "_default": 0.3}

F002_THRESHOLDS = {
    "low": [0, 24], "moderate": [25, 49],
    "elevated": [50, 74], "high": [75, 100],
}

F010_WEIGHTS = {
    "regulatory": 0.25, "benchmark": 0.20, "disclosure": 0.20,
    "enforcement": 0.15, "ai": 0.10, "compound": 0.10,
}

PEER_SCORES = [
    {"score": 50, "weight": 0.6},
    {"score": 60, "weight": 0.7},
    {"score": 70, "weight": 0.65},
    {"score": 40, "weight": 0.55},
]


def _run_pipeline():
    """Run the full pipeline on the sample notice."""
    notice = decompose(SAMPLE_NOTICE)
    return score_notice(
        organization_id="test-org",
        notice_id="test-notice",
        notice=notice,
        regulators=SAMPLE_REGULATORS,
        jurisdiction_weights=JW,
        f002_thresholds=F002_THRESHOLDS,
        f010_weights=F010_WEIGHTS,
        peer_scores=PEER_SCORES,
        org_pgms=55.0,
        avg_source_reliability=0.85,
        finding_types={},
        recommendations={},
    )


# ── Decomposition ────────────────────────────────────────────

def test_decompose_sample():
    notice = decompose(SAMPLE_NOTICE)
    assert len(notice.sections) >= 5
    assert len(notice.clauses) >= 8
    categories = {c.category for c in notice.clauses}
    assert len(categories) >= 3  # at least 3 different domains


# ── End-to-end scoring ───────────────────────────────────────

def test_pipeline_produces_all_scores():
    result = _run_pipeline()
    for key in ["f002", "f003", "f005", "f006", "f007", "f008", "f009", "f010", "f011"]:
        assert key in result["scores"], f"Missing score: {key}"
        assert "score" in result["scores"][key]
        assert "lineage" in result["scores"][key]


def test_pipeline_scores_in_range():
    result = _run_pipeline()
    for key, data in result["scores"].items():
        score = data["score"]
        assert 0 <= score <= 100, f"{key} score {score} out of range"


def test_pipeline_has_vci():
    result = _run_pipeline()
    vci = result["vci"]
    assert "score" in vci
    assert "label" in vci
    assert "components" in vci
    assert 0 <= vci["score"] <= 100


def test_pipeline_vci_has_components():
    result = _run_pipeline()
    components = result["vci"]["components"]
    for key in ["nlp", "benchmark", "regulatory", "enforcement", "source"]:
        assert key in components


def test_pipeline_has_findings():
    result = _run_pipeline()
    assert "findings" in result
    assert isinstance(result["findings"], list)
    # With a rich notice, some findings should trigger
    if result["findings"]:
        f = result["findings"][0]
        assert "code" in f
        assert "domain" in f
        assert "severity" in f
        assert "score" in f


def test_pipeline_has_summary():
    result = _run_pipeline()
    summary = result["summary"]
    assert "overall_intelligence" in summary
    assert "benchmark_percentile" in summary
    assert "finding_count" in summary
    assert "vci_label" in summary


# ── Lineage ──────────────────────────────────────────────────

def test_pipeline_lineage_on_f002():
    result = _run_pipeline()
    lineage = result["scores"]["f002"]["lineage"]
    assert "domains_scored" in lineage
    assert "regulator_contributions" in lineage


def test_pipeline_lineage_on_f010():
    result = _run_pipeline()
    lineage = result["scores"]["f010"]["lineage"]
    assert "weights" in lineage
    assert lineage["weights"] == F010_WEIGHTS


def test_pipeline_lineage_on_f011():
    result = _run_pipeline()
    lineage = result["scores"]["f011"]["lineage"]
    assert lineage["weighted"] is True
    assert "cohort_size" in lineage


# ── Reproducibility ──────────────────────────────────────────

def test_pipeline_reproducible():
    r1 = _run_pipeline()
    r2 = _run_pipeline()
    for key in ["f002", "f005", "f006", "f007", "f010"]:
        assert r1["scores"][key]["score"] == r2["scores"][key]["score"], (
            f"{key} not reproducible: {r1['scores'][key]['score']} vs {r2['scores'][key]['score']}"
        )


# ── Classification constrained output ────────────────────────

def test_classification_returns_valid_domains():
    """Verify decompose produces valid taxonomy categories."""
    notice = decompose(SAMPLE_NOTICE)
    valid = {
        "data_sharing", "tracking_cookies", "consumer_rights", "cross_border",
        "sensitive_data", "retention", "children_teens", "ai_automated_decisions",
        "other",
    }
    for clause in notice.clauses:
        assert clause.category in valid, f"Invalid category: {clause.category}"
