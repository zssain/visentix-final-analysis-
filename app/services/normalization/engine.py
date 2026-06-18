"""Normalization Engine — per-peer similarity weights for benchmarking.

Computes Normalization Score and Benchmark Weight for each peer relative
to a target org, based on VICBNF dimension similarity. Writes results
to benchmark_membership.normalization_score / benchmark_weight only.

Similarity weights (VICBNF spec):
    Industry 20% + RSS 20% + PGMS 15% + OSI 15% + DSI 15% + AIGMS 10% + Freshness 5%

Tier similarity:
    exact = 1.0, adjacent = 0.75, non-adjacent = 0.5, opposite = 0.4

Small-cohort relaxation bands:
    >=100: full cohort
    50-99: minor relaxation (record relaxed dimension)
    20-49: adjacent-tier expansion (flag moderate confidence)
    <20:   broader industry cohort + reduced confidence
"""

from __future__ import annotations

from dataclasses import dataclass

from app.services.profiling.profile import score_to_tier

# ── Dimension weights (VICBNF spec) ──────────────────────────
# Read from config in production; defined here as defaults.
DIMENSION_WEIGHTS: dict[str, float] = {
    "industry": 0.20,
    "rss": 0.20,
    "pgms": 0.15,
    "osi": 0.15,
    "dsi": 0.15,
    "aigms": 0.10,
    "freshness": 0.05,
}

# ── Tier ordering for adjacency computation ───────────────────
TIER_ORDER = ["low", "moderate", "elevated", "high"]
TIER_INDEX = {t: i for i, t in enumerate(TIER_ORDER)}

# ── Tier similarity scores ────────────────────────────────────
TIER_SIMILARITY = {
    0: 1.00,  # exact match
    1: 0.75,  # adjacent
    2: 0.50,  # non-adjacent
    3: 0.40,  # opposite ends
}

# ── Industry similarity ──────────────────────────────────────
# Same industry = 1.0, different = 0.4 (within broader cohort expansion)
INDUSTRY_SAME = 1.0
INDUSTRY_DIFFERENT = 0.4

# ── Freshness (all data is current vintage) ──────────────────
DEFAULT_FRESHNESS = 0.9  # same retrieval period → high freshness


@dataclass
class PeerProfile:
    """Minimal profile data needed for normalization."""

    organization_id: str
    industry: str
    rss_tier: str
    pgms_tier: str
    osi_tier: str
    dsi_tier: str
    ehp_tier: str
    aigms_tier: str


@dataclass
class NormalizationResult:
    """Per-peer normalization output."""

    organization_id: str
    normalization_score: float
    benchmark_weight: float
    inclusion_reason: str
    population_version: int


def tier_distance(t1: str, t2: str) -> int:
    """Absolute tier distance (0=exact, 1=adjacent, 2=non-adjacent, 3=opposite)."""
    i1 = TIER_INDEX.get(t1, 0)
    i2 = TIER_INDEX.get(t2, 0)
    return abs(i1 - i2)


def tier_similarity(t1: str, t2: str) -> float:
    """Similarity score between two tiers."""
    d = tier_distance(t1, t2)
    return TIER_SIMILARITY.get(d, 0.4)


def compute_peer_similarity(
    target: PeerProfile,
    peer: PeerProfile,
    weights: dict[str, float] | None = None,
) -> float:
    """Weighted similarity between target and peer across all dimensions."""
    w = weights or DIMENSION_WEIGHTS

    # Industry similarity
    ind_sim = INDUSTRY_SAME if target.industry == peer.industry else INDUSTRY_DIFFERENT

    # Tier similarities per dimension
    rss_sim = tier_similarity(target.rss_tier, peer.rss_tier)
    pgms_sim = tier_similarity(target.pgms_tier, peer.pgms_tier)
    osi_sim = tier_similarity(target.osi_tier, peer.osi_tier)
    dsi_sim = tier_similarity(target.dsi_tier, peer.dsi_tier)
    aigms_sim = tier_similarity(target.aigms_tier, peer.aigms_tier)

    # Freshness (uniform for now — all same vintage)
    fresh_sim = DEFAULT_FRESHNESS

    score = (
        w["industry"] * ind_sim
        + w["rss"] * rss_sim
        + w["pgms"] * pgms_sim
        + w["osi"] * osi_sim
        + w["dsi"] * dsi_sim
        + w["aigms"] * aigms_sim
        + w["freshness"] * fresh_sim
    )

    return round(score, 6)


def determine_relaxation_band(cohort_size: int) -> tuple[str, str]:
    """Return (band_label, inclusion_reason) based on cohort size."""
    if cohort_size >= 100:
        return "full", "full_cohort"
    elif cohort_size >= 50:
        return "minor", "minor_relaxation_n50_99"
    elif cohort_size >= 20:
        return "adjacent", "adjacent_tier_expansion_n20_49"
    else:
        return "broad", f"broader_industry_cohort_n{cohort_size}_reduced_confidence"


def compute_benchmark_weight(normalization_score: float, band: str) -> float:
    """Benchmark Weight = normalization_score × band confidence factor."""
    band_factors = {
        "full": 1.0,
        "minor": 0.95,
        "adjacent": 0.85,
        "broad": 0.70,
    }
    factor = band_factors.get(band, 0.70)
    return round(normalization_score * factor, 6)


def normalize_cohort(
    target: PeerProfile,
    peers: list[PeerProfile],
    population_version: int = 1,
    weights: dict[str, float] | None = None,
) -> list[NormalizationResult]:
    """Compute normalization for all peers relative to a target.

    Returns one NormalizationResult per peer (including self).
    """
    cohort_size = len(peers)
    band, base_reason = determine_relaxation_band(cohort_size)

    results = []
    for peer in peers:
        sim = compute_peer_similarity(target, peer, weights=weights)
        bw = compute_benchmark_weight(sim, band)

        # Build detailed inclusion_reason
        if peer.organization_id == target.organization_id:
            reason = f"target_org|band={band}|n={cohort_size}"
        else:
            reason = f"peer|band={band}|n={cohort_size}|sim={sim:.4f}"

        results.append(NormalizationResult(
            organization_id=peer.organization_id,
            normalization_score=sim,
            benchmark_weight=bw,
            inclusion_reason=reason,
            population_version=population_version,
        ))

    return results
