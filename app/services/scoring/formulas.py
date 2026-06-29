"""Formula implementations: F-002, F-003, F-005, F-006, F-007.

Each function is pure (no side effects, no DB calls) and reads weights
from FormulaVersion / config structures passed as arguments.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field


@dataclass
class ScoringContext:
    """All data needed to score one org/notice."""

    organization_id: str
    notice_id: str | None = None
    industry: str = ""
    jurisdiction: str = "US"

    # Clause data
    clause_categories: Counter = field(default_factory=Counter)
    total_clauses: int = 0
    avg_ambiguity: float = 0.0
    avg_readability: float = 0.0
    avg_nlp_confidence: float = 0.0
    domains_present: set = field(default_factory=set)

    # Regulator data
    regulators: list[dict] = field(default_factory=list)  # [{id, jurisdiction, efw, rpw}]
    jurisdiction_weights: dict[str, float] = field(default_factory=dict)  # JW

    # Benchmark data (from normalization)
    peer_scores: list[dict] = field(default_factory=list)  # [{org_id, score, weight}]
    org_score: float = 0.0  # this org's score for benchmark comparison

    # AI-specific
    ai_clauses: int = 0
    ai_domains_present: set = field(default_factory=set)


@dataclass
class FormulaResult:
    """Output of a formula computation."""

    formula_version_id: str
    object_type: str
    score: float
    tier: str | None = None
    source_lineage: dict = field(default_factory=dict)
    confidence_score: float = 0.5  # placeholder until VCI (P4.3)


# ── F-002: Regulatory Exposure Score ─────────────────────────

def compute_f002(
    ctx: ScoringContext,
    thresholds: dict[str, list],
) -> FormulaResult:
    """F-002 = Σ(JW × RPW × DS) normalized 0-100.

    DS (disclosure severity) = proportion of clauses in each domain.
    JW from targets.yaml, RPW from regulator.priority_weights.
    """
    if ctx.total_clauses == 0:
        return FormulaResult(
            formula_version_id="F-002_v1",
            object_type="regulatory_exposure",
            score=0.0,
            tier="low",
            source_lineage={"reason": "no_clauses"},
            confidence_score=0.3,
        )

    # Compute DS per domain (proportion of clauses)
    ds_by_domain = {}
    for domain, count in ctx.clause_categories.items():
        if domain != "other":
            ds_by_domain[domain] = count / ctx.total_clauses

    # Sum JW × RPW × DS across all regulators × domains
    raw_sum = 0.0
    max_possible = 0.0
    regulator_contributions = {}

    for reg in ctx.regulators:
        jw = ctx.jurisdiction_weights.get(
            reg["jurisdiction"],
            ctx.jurisdiction_weights.get("_default", 0.3),
        )
        efw = reg.get("efw", 0.5)
        rpw = reg.get("rpw", {})

        reg_score = 0.0
        for domain, ds in ds_by_domain.items():
            rpw_val = rpw.get(domain, 0.0)
            contribution = jw * rpw_val * ds * efw
            reg_score += contribution

        raw_sum += reg_score
        max_possible += jw * efw  # theoretical max if all RPW=1, DS=1
        regulator_contributions[reg["id"]] = round(reg_score, 4)

    # Normalize to 0-100
    score = min((raw_sum / max(max_possible, 0.001)) * 100, 100.0)
    score = round(score, 2)

    # Map to tier using stored thresholds
    tier = _threshold_tier(score, thresholds)

    return FormulaResult(
        formula_version_id="F-002_v1",
        object_type="regulatory_exposure",
        score=score,
        tier=tier,
        source_lineage={
            "domains_scored": list(ds_by_domain.keys()),
            "regulator_contributions": regulator_contributions,
            "raw_sum": round(raw_sum, 4),
            "max_possible": round(max_possible, 4),
            "total_clauses": ctx.total_clauses,
        },
        confidence_score=0.5,  # placeholder
    )


# ── F-003: Benchmark Deviation Score ─────────────────────────

def compute_f003(
    ctx: ScoringContext,
) -> FormulaResult:
    """F-003 = max(0, TopQuartileScore - OrgScore) over WEIGHTED peers.

    Uses benchmark_weight from normalization (P4.0B) — never raw unweighted.
    """
    if not ctx.peer_scores:
        return FormulaResult(
            formula_version_id="F-003_v1",
            object_type="benchmark_deviation",
            score=0.0,
            source_lineage={"reason": "no_peers"},
            confidence_score=0.3,
        )

    # Weighted percentile computation
    # Sort peers by score, compute weighted median and top quartile
    sorted_peers = sorted(ctx.peer_scores, key=lambda p: p["score"])
    total_weight = sum(p["weight"] for p in sorted_peers)

    if total_weight == 0:
        return FormulaResult(
            formula_version_id="F-003_v1",
            object_type="benchmark_deviation",
            score=0.0,
            source_lineage={"reason": "zero_total_weight"},
            confidence_score=0.3,
        )

    # Find weighted 75th percentile (top quartile threshold)
    cumulative = 0.0
    top_quartile_score = sorted_peers[-1]["score"]
    for peer in sorted_peers:
        cumulative += peer["weight"]
        if cumulative >= total_weight * 0.75:
            top_quartile_score = peer["score"]
            break

    deviation = max(0, top_quartile_score - ctx.org_score)
    # Normalize: deviation as % of top quartile
    score = min((deviation / max(top_quartile_score, 0.001)) * 100, 100.0)
    score = round(score, 2)

    n_peers = len(ctx.peer_scores)
    return FormulaResult(
        formula_version_id="F-003_v1",
        object_type="benchmark_deviation",
        score=score,
        source_lineage={
            "org_score": ctx.org_score,
            "top_quartile_score": round(top_quartile_score, 2),
            "deviation": round(deviation, 2),
            "n_peers": n_peers,
            "weighted": True,
            "cohort_band": "adjacent_n20_49" if n_peers < 50 else "full",
        },
        confidence_score=0.4 if n_peers < 50 else 0.7,  # honest small-n
    )


# ── F-005: Disclosure Maturity Score ─────────────────────────

def compute_f005(
    ctx: ScoringContext,
    expected_elements: list[dict],
) -> FormulaResult:
    """F-005 = (present/expected × 100) − ambiguity penalty − missing category penalty.

    Expected elements from config/element_checklist.csv.
    """
    if not expected_elements:
        return FormulaResult(
            formula_version_id="F-005_v1",
            object_type="disclosure_maturity",
            score=0.0,
            source_lineage={"reason": "no_expected_elements"},
            confidence_score=0.3,
        )

    total_expected = len(expected_elements)

    # Count domains present in the org's clauses
    expected_domains = set(e["domain"] for e in expected_elements)
    present_domains = ctx.domains_present & expected_domains
    missing_domains = expected_domains - present_domains

    # Elements present = domains with clauses (proxy — actual element detection is Phase 5)
    present_count = sum(
        1 for e in expected_elements
        if e["domain"] in ctx.domains_present
    )

    # Base score
    base = (present_count / total_expected) * 100

    # Ambiguity penalty: avg_ambiguity scaled to 0-15 penalty
    ambiguity_penalty = ctx.avg_ambiguity * 150  # e.g. 0.05 → 7.5 penalty

    # Missing category penalty: 5 points per missing domain
    missing_penalty = len(missing_domains) * 5

    score = max(0.0, base - ambiguity_penalty - missing_penalty)
    score = min(score, 100.0)
    score = round(score, 2)

    return FormulaResult(
        formula_version_id="F-005_v1",
        object_type="disclosure_maturity",
        score=score,
        source_lineage={
            "present_count": present_count,
            "total_expected": total_expected,
            "base_score": round(base, 2),
            "ambiguity_penalty": round(ambiguity_penalty, 2),
            "missing_penalty": missing_penalty,
            "missing_domains": sorted(missing_domains),
            "present_domains": sorted(present_domains),
        },
        confidence_score=0.5,
    )


# ── F-006: Transparency Score ────────────────────────────────

def compute_f006(
    ctx: ScoringContext,
) -> FormulaResult:
    """F-006 = Completeness × Clarity × Specificity × Explainability.

    Each factor is 0-1, product scaled to 0-100.
    """
    if ctx.total_clauses == 0:
        return FormulaResult(
            formula_version_id="F-006_v1",
            object_type="transparency",
            score=0.0,
            source_lineage={"reason": "no_clauses"},
            confidence_score=0.3,
        )

    # Completeness: fraction of taxonomy domains covered
    all_domains = {
        "data_sharing", "tracking_cookies", "consumer_rights", "cross_border",
        "sensitive_data", "retention", "children_teens", "ai_automated_decisions",
    }
    completeness = len(ctx.domains_present & all_domains) / len(all_domains)

    # Clarity: inverse of ambiguity (1 - avg_ambiguity)
    clarity = max(0.0, 1.0 - ctx.avg_ambiguity * 10)  # scale ambiguity

    # Specificity: readability score as proxy
    specificity = min(ctx.avg_readability, 1.0)

    # Explainability: NLP confidence as proxy for how well-structured the notice is
    explainability = min(ctx.avg_nlp_confidence, 1.0)

    product = completeness * clarity * specificity * explainability
    score = round(product * 100, 2)

    return FormulaResult(
        formula_version_id="F-006_v1",
        object_type="transparency",
        score=score,
        source_lineage={
            "completeness": round(completeness, 4),
            "clarity": round(clarity, 4),
            "specificity": round(specificity, 4),
            "explainability": round(explainability, 4),
            "product": round(product, 4),
            "domains_present": sorted(ctx.domains_present),
            "total_clauses": ctx.total_clauses,
        },
        confidence_score=0.5,
    )


# ── F-007: AI Transparency Maturity ──────────────────────────

def compute_f007(
    ctx: ScoringContext,
    ai_expected_elements: list[dict],
) -> FormulaResult:
    """F-007 = (AI controls present / expected) × 100 − AI ambiguity penalty.

    Expected AI controls from element_checklist.csv (ai_specific=true).
    """
    if not ai_expected_elements:
        return FormulaResult(
            formula_version_id="F-007_v1",
            object_type="ai_transparency",
            score=0.0,
            source_lineage={"reason": "no_expected_ai_elements"},
            confidence_score=0.3,
        )

    total_expected = len(ai_expected_elements)

    # AI controls present: proxy = has ai_automated_decisions clauses
    ai_present = 1 if ctx.ai_clauses > 0 else 0
    # Depth: more AI clauses = more controls likely addressed
    depth_ratio = min(ctx.ai_clauses / total_expected, 1.0) if total_expected > 0 else 0

    base = depth_ratio * 100

    # AI ambiguity penalty
    ai_ambiguity_penalty = ctx.avg_ambiguity * 100  # heavier for AI

    score = max(0.0, base - ai_ambiguity_penalty)
    score = min(score, 100.0)
    score = round(score, 2)

    return FormulaResult(
        formula_version_id="F-007_v1",
        object_type="ai_transparency",
        score=score,
        source_lineage={
            "ai_clauses": ctx.ai_clauses,
            "total_expected_controls": total_expected,
            "depth_ratio": round(depth_ratio, 4),
            "base_score": round(base, 2),
            "ai_ambiguity_penalty": round(ai_ambiguity_penalty, 2),
        },
        confidence_score=0.5 if ctx.ai_clauses > 0 else 0.3,
    )


# ── F-004: Enforcement Correlation Score ──────────────────────

def compute_f004(
    clause_embeddings: list[list[float]],
    enforcement_embeddings: list[list[float]],
    enforcement_ids: list[str],
    top_k: int = 5,
) -> FormulaResult:
    """F-004 = avg cosine similarity of top-K clause↔enforcement matches.

    Uses pre-computed embeddings (384-dim, all-MiniLM-L6-v2).
    Higher score = notice language closely resembles enforced practices.
    """
    if not clause_embeddings or not enforcement_embeddings:
        return FormulaResult(
            formula_version_id="F-004_v1",
            object_type="enforcement_correlation",
            score=0.0,
            source_lineage={"reason": "no_embeddings"},
            confidence_score=0.3,
        )

    import numpy as np

    clauses = np.array(clause_embeddings)
    enforcements = np.array(enforcement_embeddings)

    # Normalize for cosine similarity
    clauses_norm = clauses / (np.linalg.norm(clauses, axis=1, keepdims=True) + 1e-9)
    enf_norm = enforcements / (np.linalg.norm(enforcements, axis=1, keepdims=True) + 1e-9)

    # Compute similarity matrix: (n_clauses, n_enforcements)
    sim_matrix = clauses_norm @ enf_norm.T

    # For each clause, take the max enforcement similarity
    max_sims = sim_matrix.max(axis=1)

    # Top-K clause correlations
    top_k_actual = min(top_k, len(max_sims))
    top_sims = np.sort(max_sims)[-top_k_actual:]

    avg_correlation = float(np.mean(top_sims))

    # Scale to 0-100
    score = round(min(avg_correlation * 100, 100.0), 2)

    # Identify which enforcement records matched best
    best_enf_indices = sim_matrix.max(axis=0).argsort()[-3:][::-1]
    top_matches = [
        {"enforcement_id": enforcement_ids[i], "similarity": round(float(sim_matrix.max(axis=0)[i]), 4)}
        for i in best_enf_indices if i < len(enforcement_ids)
    ]

    return FormulaResult(
        formula_version_id="F-004_v1",
        object_type="enforcement_correlation",
        score=score,
        source_lineage={
            "n_clauses": len(clause_embeddings),
            "n_enforcements": len(enforcement_embeddings),
            "top_k": top_k_actual,
            "avg_top_k_similarity": round(avg_correlation, 4),
            "top_enforcement_matches": top_matches,
        },
        confidence_score=0.6 if len(clause_embeddings) > 10 else 0.4,
    )


# ── Helpers ──────────────────────────────────────────────────

def _threshold_tier(score: float, thresholds: dict[str, list]) -> str:
    for tier, bounds in thresholds.items():
        if bounds[0] <= score <= bounds[1]:
            return tier
    return "high" if score > 100 else "low"
