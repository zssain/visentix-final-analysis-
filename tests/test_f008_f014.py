"""Tests for F-008 through F-014."""

import pytest

from app.services.scoring.formulas_advanced import (
    compute_f008, compute_f009, compute_f010, compute_f011,
    compute_f012, compute_f013, compute_f014,
)


# ── F-008: Compound Risk ─────────────────────────────────────

def test_f008_zero_without_risks():
    r = compute_f008({}, {})
    assert r.score == 0.0


def test_f008_scales_with_risk():
    low = compute_f008({"data_sharing": 20}, {"data_sharing": 0.9})
    high = compute_f008({"data_sharing": 80}, {"data_sharing": 0.9})
    assert high.score > low.score


def test_f008_capped_at_100():
    r = compute_f008({"a": 100, "b": 100, "c": 100}, {"a": 1, "b": 1, "c": 1}, correlation_multiplier=5)
    assert r.score <= 100


# ── F-009: Confidence-Weighted ───────────────────────────────

def test_f009_full_confidence():
    r = compute_f009(80.0, 1.0)
    assert r.score == 80.0


def test_f009_half_confidence():
    r = compute_f009(80.0, 0.5)
    assert r.score == 40.0


def test_f009_zero_confidence():
    r = compute_f009(80.0, 0.0)
    assert r.score == 0.0


# ── F-010: Overall Intelligence ──────────────────────────────

F010_WEIGHTS = {"regulatory": 0.25, "benchmark": 0.20, "disclosure": 0.20,
                "enforcement": 0.15, "ai": 0.10, "compound": 0.10}


def test_f010_zero_risk_max_score():
    scores = {k: 0 for k in F010_WEIGHTS}
    r = compute_f010(scores, F010_WEIGHTS)
    assert r.score == 100.0


def test_f010_max_risk_zero_score():
    scores = {k: 100 for k in F010_WEIGHTS}
    r = compute_f010(scores, F010_WEIGHTS)
    assert r.score == 0.0


def test_f010_reads_weights_from_arg():
    """Weights must come from formula_version, not hardcoded."""
    custom_weights = {"regulatory": 1.0}  # all weight on regulatory
    scores = {"regulatory": 50}
    r = compute_f010(scores, custom_weights)
    assert r.score == 50.0  # 100 - 50*1.0


def test_f010_lineage_includes_weights():
    r = compute_f010({"regulatory": 30}, F010_WEIGHTS)
    assert "weights" in r.source_lineage
    assert r.source_lineage["weights"] == F010_WEIGHTS


# ── F-011: Benchmark Percentile ──────────────────────────────

def test_f011_no_peers():
    r = compute_f011(50, [], cohort_size=0)
    assert r.score == 0.0


def test_f011_top_percentile():
    peers = [{"score": 30, "weight": 0.7}, {"score": 40, "weight": 0.7}]
    r = compute_f011(90, peers, cohort_size=3)
    assert r.score > 90


def test_f011_bottom_percentile():
    peers = [{"score": 80, "weight": 0.7}, {"score": 90, "weight": 0.7}]
    r = compute_f011(10, peers, cohort_size=3)
    assert r.score < 10


def test_f011_small_cohort_label():
    peers = [{"score": 50, "weight": 0.6} for _ in range(29)]
    r = compute_f011(50, peers, cohort_size=30)
    assert r.source_lineage["cohort_label"] == "small_cohort"
    assert r.source_lineage["cohort_size"] == 30
    assert r.source_lineage["weighted"] is True
    assert r.confidence_score <= 0.5


def test_f011_honest_cohort_size():
    """Must never fabricate cohort size."""
    peers = [{"score": 50, "weight": 0.6} for _ in range(29)]
    r = compute_f011(50, peers, cohort_size=30)
    assert r.source_lineage["cohort_size"] == 30  # real n, not "1,250+"


# ── F-012: Trend Delta ──────────────────────────────────────

def test_f012_no_prior():
    r = compute_f012(80, None)
    assert r.score == 0.0
    assert r.source_lineage.get("reason") == "no_prior_history"


def test_f012_positive_delta():
    r = compute_f012(80, 60)
    assert r.score > 0  # improved


def test_f012_negative_delta():
    r = compute_f012(40, 60)
    assert r.score < 0  # worsened


# ── F-013: Alert Escalation ─────────────────────────────────

def test_f013_zero_without_risk_increase():
    r = compute_f013(risk_increase=0)
    assert r.score == 0.0


def test_f013_scales_with_inputs():
    r = compute_f013(risk_increase=0.5, enforcement_correlation=0.8,
                     monitoring_priority=0.9, confidence=0.7,
                     has_monitoring_data=True)
    assert r.score > 0


# ── F-014: Report Confidence ────────────────────────────────

def test_f014_no_findings():
    r = compute_f014(0, 0, 0.9, 0.8)
    assert r.score == 0.0


def test_f014_all_validated():
    r = compute_f014(10, 10, 0.9, 0.8)
    assert r.score == pytest.approx(72.0)  # 1.0 * 0.9 * 0.8 * 100


def test_f014_partial_validation():
    r = compute_f014(5, 10, 0.9, 0.8)
    assert r.score == pytest.approx(36.0)  # 0.5 * 0.9 * 0.8 * 100
