"""Phase 4.0B normalization tests — similarity, weights, relaxation bands."""

import pytest

from app.services.normalization.engine import (
    DIMENSION_WEIGHTS,
    PeerProfile,
    compute_benchmark_weight,
    compute_peer_similarity,
    determine_relaxation_band,
    normalize_cohort,
    tier_distance,
    tier_similarity,
)


# ── Tier similarity ──────────────────────────────────────────

def test_exact_tier_similarity():
    assert tier_similarity("high", "high") == 1.0
    assert tier_similarity("low", "low") == 1.0


def test_adjacent_tier_similarity():
    assert tier_similarity("low", "moderate") == 0.75
    assert tier_similarity("elevated", "high") == 0.75


def test_non_adjacent_tier_similarity():
    assert tier_similarity("low", "elevated") == 0.50
    assert tier_similarity("moderate", "high") == 0.50


def test_opposite_tier_similarity():
    assert tier_similarity("low", "high") == 0.40


def test_tier_distance_symmetric():
    assert tier_distance("low", "high") == tier_distance("high", "low")


# ── Peer similarity ──────────────────────────────────────────

def _make_peer(
    org_id: str = "peer-1",
    industry: str = "financial_services",
    rss: str = "moderate",
    pgms: str = "moderate",
    osi: str = "high",
    dsi: str = "moderate",
    ehp: str = "high",
    aigms: str = "low",
) -> PeerProfile:
    return PeerProfile(
        organization_id=org_id,
        industry=industry,
        rss_tier=rss,
        pgms_tier=pgms,
        osi_tier=osi,
        dsi_tier=dsi,
        ehp_tier=ehp,
        aigms_tier=aigms,
    )


def test_identical_peers_max_similarity():
    target = _make_peer("t")
    peer = _make_peer("p")
    sim = compute_peer_similarity(target, peer)
    # All tiers match, same industry → near 1.0 (freshness 0.9 caps it slightly)
    assert sim > 0.95


def test_different_industry_lowers_similarity():
    target = _make_peer("t", industry="financial_services")
    same_ind = _make_peer("p1", industry="financial_services")
    diff_ind = _make_peer("p2", industry="supply_chain_services")

    sim_same = compute_peer_similarity(target, same_ind)
    sim_diff = compute_peer_similarity(target, diff_ind)
    assert sim_same > sim_diff, "Same industry should have higher similarity"


def test_mature_vs_nascent_not_equal():
    """A mature program (high tiers) should NOT be weighted equally to a nascent one."""
    target = _make_peer("t", rss="high", pgms="high", dsi="high", aigms="high")
    mature_peer = _make_peer("p1", rss="high", pgms="high", dsi="high", aigms="high")
    nascent_peer = _make_peer("p2", rss="low", pgms="low", dsi="low", aigms="low")

    sim_mature = compute_peer_similarity(target, mature_peer)
    sim_nascent = compute_peer_similarity(target, nascent_peer)
    assert sim_mature > sim_nascent, (
        f"Mature peer sim ({sim_mature}) should exceed nascent ({sim_nascent})"
    )


def test_adjacent_tiers_better_than_opposite():
    target = _make_peer("t", rss="elevated")
    adjacent = _make_peer("p1", rss="high")  # 1 tier away
    opposite = _make_peer("p2", rss="low")   # 2 tiers away

    sim_adj = compute_peer_similarity(target, adjacent)
    sim_opp = compute_peer_similarity(target, opposite)
    assert sim_adj > sim_opp


# ── Relaxation bands ─────────────────────────────────────────

def test_band_full():
    band, reason = determine_relaxation_band(100)
    assert band == "full"


def test_band_minor():
    band, reason = determine_relaxation_band(75)
    assert band == "minor"


def test_band_adjacent():
    """n=30 falls in the 20-49 band."""
    band, reason = determine_relaxation_band(30)
    assert band == "adjacent"
    assert "20_49" in reason or "adjacent" in reason


def test_band_broad():
    band, reason = determine_relaxation_band(15)
    assert band == "broad"
    assert "reduced_confidence" in reason


# ── Benchmark weight ─────────────────────────────────────────

def test_benchmark_weight_full_band():
    bw = compute_benchmark_weight(0.8, "full")
    assert bw == 0.8  # 1.0 factor


def test_benchmark_weight_adjacent_band():
    bw = compute_benchmark_weight(0.8, "adjacent")
    assert bw == pytest.approx(0.68)  # 0.85 factor


def test_benchmark_weight_broad_band():
    bw = compute_benchmark_weight(0.8, "broad")
    assert bw == pytest.approx(0.56)  # 0.70 factor


# ── Full cohort normalization ────────────────────────────────

def test_normalize_cohort_returns_all_peers():
    target = _make_peer("target")
    peers = [_make_peer(f"p{i}") for i in range(30)]
    peers.append(target)

    results = normalize_cohort(target, peers)
    assert len(results) == 31  # 30 peers + target


def test_normalize_cohort_records_band():
    target = _make_peer("target")
    peers = [_make_peer(f"p{i}") for i in range(30)]

    results = normalize_cohort(target, peers)
    for r in results:
        assert "band=adjacent" in r.inclusion_reason
        assert "n=30" in r.inclusion_reason


def test_normalize_cohort_target_flagged():
    target = _make_peer("target")
    peers = [target, _make_peer("p1")]

    results = normalize_cohort(target, peers)
    target_result = [r for r in results if r.organization_id == "target"][0]
    assert "target_org" in target_result.inclusion_reason


# ── Live data verification ───────────────────────────────────

def test_benchmark_membership_has_weights():
    """Verify all 30 rows have non-NULL normalization columns."""
    import os
    import httpx
    from dotenv import dotenv_values

    config = dotenv_values(os.path.join(os.path.dirname(__file__), "..", ".env"))
    url, key = config["SUPABASE_URL"], config["SUPABASE_SERVICE_ROLE_KEY"]
    headers = {"apikey": key, "Authorization": f"Bearer {key}"}

    r = httpx.get(
        f"{url}/rest/v1/benchmark_membership"
        f"?select=normalization_score,benchmark_weight,inclusion_reason,population_version",
        headers=headers, timeout=15,
    )
    rows = r.json()
    assert len(rows) == 30

    for row in rows:
        assert row["normalization_score"] is not None, "normalization_score is NULL"
        assert row["benchmark_weight"] is not None, "benchmark_weight is NULL"
        assert row["inclusion_reason"] is not None, "inclusion_reason is NULL"
        assert row["population_version"] is not None, "population_version is NULL"
        assert 0 < row["normalization_score"] <= 1.0
        assert 0 < row["benchmark_weight"] <= 1.0
        assert "band=" in row["inclusion_reason"]
