"""VICBNF v2 org profiling tests — spec-exact weightings and tier boundaries."""

from collections import Counter

import pytest

from app.services.profiling.live_profile import (
    _CFG,
    _score_to_tier,
    compute_aigms,
    compute_dsi,
    compute_ehp,
    compute_ic,
    compute_org_profile,
    compute_osi,
    compute_pgms,
    compute_rss,
    OrgProfileInput,
)


# ── Helpers ──────────────────────────────────────────────────

def _inp(**kwargs) -> OrgProfileInput:
    defaults = dict(
        organization_id="test-org",
        name="Test Org",
        industry="fintech",
        size="large",
        geography="US",
        public_private=None,
        clause_categories=Counter(),
        clause_types=Counter(),
        total_clauses=0,
        has_notice=False,
    )
    defaults.update(kwargs)
    return OrgProfileInput(**defaults)


# ── IC: Industry Classification ──────────────────────────────

def test_ic_fintech_maps_to_financial_services():
    iid, sub, label, conf = compute_ic("fintech")
    assert iid == "IND-05"
    assert conf == 1.0


def test_ic_healthcare():
    iid, _, _, conf = compute_ic("healthcare")
    assert iid == "IND-04"
    assert conf == 1.0


def test_ic_unmapped_industry():
    iid, _, label, conf = compute_ic("spacefaring")
    assert iid == "IND-00"
    assert label == "Unmapped"
    assert conf < 0.5


def test_ic_manufacturing():
    iid, _, _, conf = compute_ic("manufacturing")
    assert iid == "IND-10"


# ── RSS: spec weights ───────────────────────────────────────

def test_rss_weights_sum_to_1():
    total = sum(_CFG["rss_weights"].values())
    assert abs(total - 1.0) < 0.001


def test_rss_high_for_sensitive_fintech():
    inp = _inp(
        industry="fintech",
        clause_categories=Counter({"sensitive_data": 10, "data_sharing": 20, "children_teens": 5}),
        total_clauses=200,
        enforcement_count=10,
        jurisdiction_presence=["US-CA"],
        has_notice=True,
    )
    score, conf = compute_rss(inp)
    assert score > 60, f"Expected high RSS for sensitive fintech, got {score}"
    assert conf == 0.9


def test_rss_low_for_no_data():
    inp = _inp(total_clauses=0, has_notice=False)
    score, conf = compute_rss(inp)
    assert score < 40
    assert conf == 0.3


# ── RSS tiers ────────────────────────────────────────────────

@pytest.mark.parametrize("score,expected", [
    (0, "Minimal"), (20, "Minimal"),
    (21, "Moderate"), (50, "Moderate"),
    (51, "High"), (80, "High"),
    (81, "Enhanced"), (100, "Enhanced"),
])
def test_rss_tier_boundaries(score, expected):
    tier = _score_to_tier(score, _CFG["rss_tiers"])
    assert tier == expected


# ── PGMS: spec weights ──────────────────────────────────────

def test_pgms_weights_sum_to_1():
    total = sum(_CFG["pgms_weights"].values())
    assert abs(total - 1.0) < 0.001


def test_pgms_high_with_broad_coverage():
    inp = _inp(
        clause_categories=Counter({
            "consumer_rights": 12, "retention": 5, "cross_border": 8,
            "data_sharing": 15, "tracking_cookies": 6, "sensitive_data": 4,
            "ai_automated_decisions": 3,
        }),
        total_clauses=53,
        has_notice=True,
    )
    score, conf = compute_pgms(inp)
    assert score > 40, f"Expected moderate+ PGMS, got {score}"


def test_pgms_zero_without_clauses():
    score, conf = compute_pgms(_inp())
    assert score == 0.0
    assert conf == 0.3


# ── PGMS tiers ───────────────────────────────────────────────

@pytest.mark.parametrize("score,expected", [
    (0, "Nascent"), (25, "Nascent"),
    (26, "Developing"), (50, "Developing"),
    (51, "Managed"), (75, "Managed"),
    (76, "Mature"), (90, "Mature"),
    (91, "Leading"), (100, "Leading"),
])
def test_pgms_tier_boundaries(score, expected):
    tier = _score_to_tier(score, _CFG["pgms_tiers"])
    assert tier == expected


# ── OSI: spec weights ────────────────────────────────────────

def test_osi_weights_sum_to_1():
    total = sum(_CFG["osi_weights"].values())
    assert abs(total - 1.0) < 0.001


def test_osi_large_public():
    inp = _inp(size="large", public_private="public")
    score, conf = compute_osi(inp)
    assert score > 50


def test_osi_small_unknown():
    inp = _inp(size="small", public_private=None)
    score, conf = compute_osi(inp)
    assert score < 40
    assert conf == 0.5


# ── DSI ──────────────────────────────────────────────────────

def test_dsi_high_with_sensitive_data():
    inp = _inp(
        clause_categories=Counter({"sensitive_data": 5, "children_teens": 5, "ai_automated_decisions": 3}),
        total_clauses=13,
        has_notice=True,
    )
    score, conf = compute_dsi(inp)
    assert score > 40, f"Expected moderate+ DSI, got {score}"


def test_dsi_zero_without_clauses():
    score, conf = compute_dsi(_inp())
    assert score == 0.0


# ── EHP ──────────────────────────────────────────────────────

def test_ehp_clean_without_enforcement():
    score, tier, conf = compute_ehp(_inp(enforcement_count=0))
    assert score == 0.0
    assert tier == "Clean"
    assert conf == 0.4


def test_ehp_enforcement_with_records():
    inp = _inp(
        enforcement_count=20,
        total_penalty_usd=1_000_000,
        enforcement_regulators=["FTC", "CPPA", "CA-AG", "CT-AG"],
    )
    score, tier, conf = compute_ehp(inp)
    assert score > 50
    assert tier == "Enforcement"


# ── AIGMS: spec weights ──────────────────────────────────────

def test_aigms_weights_sum_to_1():
    total = sum(_CFG["aigms_weights"].values())
    assert abs(total - 1.0) < 0.001


def test_aigms_with_ai_clauses():
    inp = _inp(
        clause_categories=Counter({"ai_automated_decisions": 5}),
        clause_types=Counter({"AI Transparency": 2, "Automated Decisions": 2, "Human Review": 1}),
        total_clauses=5,
        has_notice=True,
    )
    score, conf = compute_aigms(inp)
    assert score > 30, f"Expected developing+ AIGMS, got {score}"


def test_aigms_absent_without_ai():
    inp = _inp(
        clause_categories=Counter({"data_sharing": 5}),
        total_clauses=5,
        has_notice=True,
    )
    score, conf = compute_aigms(inp)
    assert score <= 10
    assert conf == 0.3


# ── Full profile ─────────────────────────────────────────────

def test_full_profile_has_all_dimensions():
    profile = compute_org_profile(
        org_row={
            "organization_id": "org-1",
            "name": "TestCo",
            "industry": "technology",
            "size": "medium",
            "geography": "US",
        },
        clauses=[
            {"category": "data_sharing", "clause_type": "Service Providers"},
            {"category": "consumer_rights", "clause_type": "Access"},
            {"category": "retention", "clause_type": "Specific Period"},
            {"category": "ai_automated_decisions", "clause_type": "AI Transparency"},
        ],
    )
    assert profile.industry_id == "IND-07"
    assert profile.rss >= 0
    assert profile.pgms >= 0
    assert profile.osi >= 0
    assert profile.dsi >= 0
    assert profile.ehp >= 0
    assert profile.aigms >= 0
    assert profile.rss_tier in ("Minimal", "Moderate", "High", "Enhanced")
    assert profile.pgms_tier in ("Nascent", "Developing", "Managed", "Mature", "Leading")
    assert profile.confidence_score > 0


def test_sparse_org_gets_low_confidence():
    """Brand-new org with no clauses → low confidence but still classifiable."""
    profile = compute_org_profile(
        org_row={
            "organization_id": "org-new",
            "name": "New Co",
            "industry": "unknown",
            "size": "unknown",
            "geography": "US",
        },
        clauses=[],
    )
    assert profile.confidence_score < 0.5
    assert profile.industry_id == "IND-00"
    assert profile.ehp_tier == "Clean"


def test_profile_version_is_set():
    profile = compute_org_profile(
        {"organization_id": "x", "name": "X", "industry": "retail", "size": "small", "geography": "US"},
        clauses=[{"category": "data_sharing"}],
        profile_version=3,
    )
    assert profile.profile_version == 3


# ── Config integrity ─────────────────────────────────────────

def test_all_tier_configs_are_contiguous():
    """Tier configs should cover 0-100 without gaps."""
    for key in ("rss_tiers", "pgms_tiers", "osi_tiers", "dsi_tiers", "aigms_tiers", "ehp_tiers"):
        tiers = _CFG[key]
        assert tiers[0]["min"] == 0, f"{key} doesn't start at 0"
        assert tiers[-1]["max"] == 100, f"{key} doesn't end at 100"
        for i in range(1, len(tiers)):
            assert tiers[i]["min"] == tiers[i-1]["max"] + 1, (
                f"{key} gap between tier {i-1} and {i}"
            )
