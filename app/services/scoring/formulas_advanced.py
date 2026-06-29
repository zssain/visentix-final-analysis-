"""Advanced formulas: F-008 through F-014.

All are pure functions reading weights from formula_version — no hardcoding.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class FormulaResult:
    formula_version_id: str
    object_type: str
    score: float
    tier: str | None = None
    source_lineage: dict = field(default_factory=dict)
    confidence_score: float = 0.5


# ── F-008: Compound Risk Score ───────────────────────────────

def compute_f008(
    risk_scores: dict[str, float],
    regulator_weights: dict[str, float],
    correlation_multiplier: float = 1.2,
) -> FormulaResult:
    """F-008 = Σ(related risk × CM × RPW) normalized, capped at 100.

    risk_scores: {domain: score} from F-002 components or clause-level risks.
    regulator_weights: {domain: weight} from the most relevant regulator.
    """
    if not risk_scores:
        return FormulaResult(
            formula_version_id="F-008_v1", object_type="compound_risk",
            score=0.0, source_lineage={"reason": "no_risk_scores"}, confidence_score=0.3,
        )

    raw = sum(
        score * correlation_multiplier * regulator_weights.get(domain, 0.5)
        for domain, score in risk_scores.items()
    )
    max_possible = sum(
        100 * correlation_multiplier * regulator_weights.get(d, 0.5)
        for d in risk_scores.keys()
    )
    score = min((raw / max(max_possible, 0.001)) * 100, 100.0)

    return FormulaResult(
        formula_version_id="F-008_v1", object_type="compound_risk",
        score=round(score, 2),
        source_lineage={
            "risk_scores": risk_scores,
            "cm": correlation_multiplier,
            "raw": round(raw, 2),
            "max_possible": round(max_possible, 2),
        },
        confidence_score=0.5,
    )


# ── F-009: Confidence-Weighted Score ─────────────────────────

def compute_f009(
    derived_score: float,
    confidence: float,
) -> FormulaResult:
    """F-009 = Derived Score × Confidence."""
    score = round(derived_score * confidence, 2)
    return FormulaResult(
        formula_version_id="F-009_v1", object_type="confidence_weighted",
        score=score,
        source_lineage={
            "derived_score": derived_score,
            "confidence": round(confidence, 4),
        },
        confidence_score=confidence,
    )


# ── F-010: Overall Privacy Intelligence Score ────────────────

def compute_f010(
    component_scores: dict[str, float],
    weights: dict[str, float],
) -> FormulaResult:
    """F-010 = 100 − weighted risk aggregate.

    weights from formula_version F-010_v1 (regulatory:0.25, benchmark:0.20, etc.).
    """
    weighted_risk = sum(
        component_scores.get(dim, 0) * w
        for dim, w in weights.items()
    )
    # Overall Intelligence = 100 - weighted risk exposure
    score = max(0.0, min(100.0, 100.0 - weighted_risk))

    return FormulaResult(
        formula_version_id="F-010_v1", object_type="overall_intelligence",
        score=round(score, 2),
        source_lineage={
            "component_scores": {k: round(v, 2) for k, v in component_scores.items()},
            "weights": weights,
            "weighted_risk": round(weighted_risk, 2),
        },
        confidence_score=0.5,
    )


# ── F-011: Benchmark Percentile ──────────────────────────────

def compute_f011(
    org_score: float,
    peer_scores: list[dict],
    cohort_size: int,
    cohort_date: str = "2026-06-18",
) -> FormulaResult:
    """F-011 = PercentileRank over NORMALIZATION-WEIGHTED peer population.

    peer_scores: [{score, weight}] — weight from benchmark_membership.
    Honest: attaches real cohort size + date + small-n label.
    """
    if not peer_scores:
        return FormulaResult(
            formula_version_id="F-011_v1", object_type="benchmark_percentile",
            score=0.0,
            source_lineage={"reason": "no_peers", "cohort_size": 0},
            confidence_score=0.3,
        )

    # Weighted percentile rank
    total_weight = sum(p["weight"] for p in peer_scores)
    if total_weight == 0:
        return FormulaResult(
            formula_version_id="F-011_v1", object_type="benchmark_percentile",
            score=50.0, source_lineage={"reason": "zero_weight"}, confidence_score=0.3,
        )

    below_weight = sum(
        p["weight"] for p in peer_scores if p["score"] < org_score
    )
    equal_weight = sum(
        p["weight"] for p in peer_scores if p["score"] == org_score
    )

    percentile = ((below_weight + 0.5 * equal_weight) / total_weight) * 100
    percentile = round(min(max(percentile, 0), 100), 2)

    # Small-n label
    if cohort_size < 20:
        n_label = "very_small_cohort"
        conf = 0.3
    elif cohort_size < 50:
        n_label = "small_cohort"
        conf = 0.4
    elif cohort_size < 100:
        n_label = "moderate_cohort"
        conf = 0.6
    else:
        n_label = "full_cohort"
        conf = 0.8

    return FormulaResult(
        formula_version_id="F-011_v1", object_type="benchmark_percentile",
        score=percentile,
        source_lineage={
            "org_score": org_score,
            "cohort_size": cohort_size,
            "cohort_date": cohort_date,
            "cohort_label": n_label,
            "weighted": True,
            "below_weight": round(below_weight, 4),
            "total_weight": round(total_weight, 4),
        },
        confidence_score=conf,
    )


# ── F-012: Trend Delta ──────────────────────────────────────
#
# Definition: F-012 = (current - prior) / prior
# When no prior exists: return 0 with reason="no_prior_history", LOW VCI,
# and a label the report surfaces as "trend unavailable — single point in time".

def compute_f012(
    current_score: float,
    prior_score: float | None,
    current_snapshot_id: str = "",
    prior_snapshot_id: str = "",
    metric_name: str = "overall_intelligence",
) -> FormulaResult:
    """F-012 Trend Delta = (current − prior) / prior.

    If prior exists: real delta, traceable to both snapshot points.
    If no prior: honest 0 with "no_prior_history" label and LOW VCI.
    """
    if prior_score is None:
        return FormulaResult(
            formula_version_id="F-012_v1", object_type="trend_delta",
            score=0.0,
            source_lineage={
                "reason": "no_prior_history",
                "label": "Trend unavailable — single point in time.",
                "metric": metric_name,
                "current_score": current_score,
                "current_snapshot_id": current_snapshot_id,
            },
            confidence_score=0.1,  # very low — no trend data
        )

    if prior_score == 0:
        # Avoid divide-by-zero; prior was 0 → infinite % change is meaningless
        return FormulaResult(
            formula_version_id="F-012_v1", object_type="trend_delta",
            score=0.0,
            source_lineage={
                "reason": "prior_score_zero",
                "label": "Trend unavailable — prior baseline is zero.",
                "current_score": current_score,
                "prior_score": 0.0,
            },
            confidence_score=0.15,
        )

    delta_pct = round(((current_score - prior_score) / prior_score) * 100, 2)

    return FormulaResult(
        formula_version_id="F-012_v1", object_type="trend_delta",
        score=delta_pct,
        source_lineage={
            "current_score": current_score,
            "prior_score": prior_score,
            "delta_pct": delta_pct,
            "current_snapshot_id": current_snapshot_id,
            "prior_snapshot_id": prior_snapshot_id,
            "metric": metric_name,
        },
        confidence_score=0.7,  # two real data points → moderate-high confidence
    )


# ── F-013: Alert Escalation ─────────────────────────────────
#
# Definition: F-013 = Risk Δ × Enforcement Correlation × Priority × Confidence
# When monitoring data is absent: degrade to low-confidence, don't invent.

def compute_f013(
    risk_increase: float = 0.0,
    enforcement_correlation: float = 0.0,
    monitoring_priority: float = 0.5,
    confidence: float = 0.5,
    has_monitoring_data: bool = False,
    monitoring_event_id: str = "",
) -> FormulaResult:
    """F-013 Alert Escalation = Risk Δ × Enforcement Correlation × Priority × Confidence.

    has_monitoring_data=True: real signal from monitoring_event → higher VCI.
    has_monitoring_data=False: no monitoring → low VCI + honest label.
    """
    score = risk_increase * enforcement_correlation * monitoring_priority * confidence * 100
    score = round(min(max(score, 0), 100), 2)

    if not has_monitoring_data:
        return FormulaResult(
            formula_version_id="F-013_v1", object_type="alert_escalation",
            score=score,
            source_lineage={
                "risk_increase": risk_increase,
                "enforcement_correlation": enforcement_correlation,
                "monitoring_priority": monitoring_priority,
                "confidence": confidence,
                "has_monitoring_data": False,
                "label": "Alert escalation based on static analysis only — "
                         "no monitoring events available. Interpret with caution.",
            },
            confidence_score=0.2,  # low — no monitoring signal
        )

    return FormulaResult(
        formula_version_id="F-013_v1", object_type="alert_escalation",
        score=score,
        source_lineage={
            "risk_increase": risk_increase,
            "enforcement_correlation": enforcement_correlation,
            "monitoring_priority": monitoring_priority,
            "confidence": confidence,
            "has_monitoring_data": True,
            "monitoring_event_id": monitoring_event_id,
        },
        confidence_score=0.6,  # real monitoring signal → moderate confidence
    )


# ── F-014: Report Confidence Index ───────────────────────────

def compute_f014(
    validated_findings: int,
    total_findings: int,
    avg_source_reliability: float,
    avg_nlp_confidence: float,
) -> FormulaResult:
    """F-014 = (Validated/Total) × avg_SR × avg_NC."""
    if total_findings == 0:
        return FormulaResult(
            formula_version_id="F-014_v1", object_type="report_confidence",
            score=0.0,
            source_lineage={"reason": "no_findings"},
            confidence_score=0.3,
        )

    ratio = validated_findings / total_findings
    score = ratio * avg_source_reliability * avg_nlp_confidence * 100
    score = round(min(max(score, 0), 100), 2)

    return FormulaResult(
        formula_version_id="F-014_v1", object_type="report_confidence",
        score=score,
        source_lineage={
            "validated": validated_findings,
            "total": total_findings,
            "ratio": round(ratio, 4),
            "avg_sr": round(avg_source_reliability, 4),
            "avg_nc": round(avg_nlp_confidence, 4),
        },
        confidence_score=min(score / 100, 1.0),
    )
