"""F-012 Trend Delta + F-013 Alert Escalation tests — honest results with/without history."""

import pytest

from app.services.scoring.formulas_advanced import compute_f012, compute_f013


# ══════════════════════════════════════════════════════════════
# F-012: Trend Delta
# ══════════════════════════════════════════════════════════════

# ── With prior data: real delta ──────────────────────────────

def test_f012_positive_delta():
    """Current > prior → positive % change."""
    r = compute_f012(current_score=72.0, prior_score=60.0,
                     current_snapshot_id="snap-2", prior_snapshot_id="snap-1")
    # (72 - 60) / 60 = 0.2 = 20%
    assert r.score == 20.0
    assert r.source_lineage["current_score"] == 72.0
    assert r.source_lineage["prior_score"] == 60.0
    assert r.source_lineage["delta_pct"] == 20.0


def test_f012_negative_delta():
    """Current < prior → negative % change."""
    r = compute_f012(current_score=45.0, prior_score=60.0)
    # (45 - 60) / 60 = -0.25 = -25%
    assert r.score == -25.0


def test_f012_zero_delta():
    """Same score → 0% change."""
    r = compute_f012(current_score=60.0, prior_score=60.0)
    assert r.score == 0.0


def test_f012_traces_both_snapshots():
    """Lineage includes both snapshot IDs."""
    r = compute_f012(current_score=70.0, prior_score=55.0,
                     current_snapshot_id="snap-current", prior_snapshot_id="snap-prior",
                     metric_name="overall_intelligence")
    assert r.source_lineage["current_snapshot_id"] == "snap-current"
    assert r.source_lineage["prior_snapshot_id"] == "snap-prior"
    assert r.source_lineage["metric"] == "overall_intelligence"


def test_f012_with_prior_has_good_confidence():
    """Two real data points → confidence >= 0.6."""
    r = compute_f012(current_score=70.0, prior_score=55.0)
    assert r.confidence_score >= 0.6


# ── Without prior data: honest "no history" ──────────────────

def test_f012_no_prior_returns_zero():
    """No prior data → score = 0."""
    r = compute_f012(current_score=65.0, prior_score=None)
    assert r.score == 0.0


def test_f012_no_prior_has_reason():
    """No prior → lineage says 'no_prior_history'."""
    r = compute_f012(current_score=65.0, prior_score=None)
    assert r.source_lineage["reason"] == "no_prior_history"


def test_f012_no_prior_has_label():
    """No prior → label for report to surface."""
    r = compute_f012(current_score=65.0, prior_score=None)
    assert "single point" in r.source_lineage["label"].lower()


def test_f012_no_prior_low_vci():
    """No prior → VCI is very low (never presents as definitive)."""
    r = compute_f012(current_score=65.0, prior_score=None)
    assert r.confidence_score <= 0.2


def test_f012_no_prior_is_not_fabricated():
    """No prior → the score is 0, not a fabricated trend number."""
    r = compute_f012(current_score=65.0, prior_score=None)
    assert r.score == 0.0
    assert r.source_lineage.get("delta_pct") is None  # no fabricated delta


def test_f012_prior_zero_handled():
    """Prior = 0 → can't divide, returns honest zero."""
    r = compute_f012(current_score=50.0, prior_score=0.0)
    assert r.score == 0.0
    assert "zero" in r.source_lineage["reason"]


# ── Reproducibility ──────────────────────────────────────────

def test_f012_reproducible():
    r1 = compute_f012(70.0, 55.0, "s2", "s1")
    r2 = compute_f012(70.0, 55.0, "s2", "s1")
    assert r1.score == r2.score
    assert r1.source_lineage == r2.source_lineage


# ══════════════════════════════════════════════════════════════
# F-013: Alert Escalation
# ══════════════════════════════════════════════════════════════

def test_f013_with_monitoring():
    """Real monitoring data → score from all four factors."""
    r = compute_f013(
        risk_increase=0.3,
        enforcement_correlation=0.6,
        monitoring_priority=0.8,
        confidence=0.7,
        has_monitoring_data=True,
        monitoring_event_id="evt-001",
    )
    # 0.3 × 0.6 × 0.8 × 0.7 × 100 = 10.08
    assert abs(r.score - 10.08) < 0.1
    assert r.source_lineage["has_monitoring_data"] is True
    assert r.source_lineage["monitoring_event_id"] == "evt-001"


def test_f013_with_monitoring_good_confidence():
    r = compute_f013(risk_increase=0.5, enforcement_correlation=0.5,
                     has_monitoring_data=True)
    assert r.confidence_score >= 0.5


def test_f013_without_monitoring_low_confidence():
    """No monitoring → low VCI + honest label."""
    r = compute_f013(risk_increase=0.0, enforcement_correlation=0.0,
                     has_monitoring_data=False)
    assert r.confidence_score <= 0.3
    assert "no monitoring" in r.source_lineage["label"].lower()


def test_f013_without_monitoring_not_fabricated():
    """No risk increase + no monitoring → score = 0 (not invented)."""
    r = compute_f013(risk_increase=0.0, enforcement_correlation=0.0,
                     has_monitoring_data=False)
    assert r.score == 0.0


def test_f013_clamped_0_100():
    r = compute_f013(risk_increase=1.0, enforcement_correlation=1.0,
                     monitoring_priority=1.0, confidence=1.0,
                     has_monitoring_data=True)
    assert r.score <= 100.0

    r2 = compute_f013(risk_increase=-0.5, enforcement_correlation=0.5,
                      has_monitoring_data=True)
    assert r2.score >= 0.0


def test_f013_combines_factors_correctly():
    """Verify multiplication: 0.4 × 0.5 × 0.6 × 0.8 × 100 = 9.6."""
    r = compute_f013(risk_increase=0.4, enforcement_correlation=0.5,
                     monitoring_priority=0.6, confidence=0.8,
                     has_monitoring_data=True)
    assert abs(r.score - 9.6) < 0.1
