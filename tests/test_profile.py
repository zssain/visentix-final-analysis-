"""Phase 4 profiling tests — hand-computed fixtures for each dimension."""

from collections import Counter

import pytest

from app.services.profiling.profile import (
    INDUSTRY_MAP,
    OrgData,
    compute_aigms,
    compute_confidence,
    compute_dsi,
    compute_ehp,
    compute_ic,
    compute_osi,
    compute_pgms,
    compute_profile,
    compute_rss,
    score_to_tier,
)


# ── Fixtures ──────────────────────────────────────────────────

def _make_org(
    industry: str = "fintech",
    size: str = "large",
    public_private: str | None = None,
    clause_cats: dict | None = None,
    total_clauses: int = 0,
    has_notice: bool = True,
    enforcement_count: int = 0,
    total_penalty: float = 0.0,
    regulators: list[str] | None = None,
) -> OrgData:
    return OrgData(
        organization_id="test-org-id",
        name="Test Org",
        industry=industry,
        size=size,
        geography="US",
        public_private=public_private,
        clause_categories=Counter(clause_cats or {}),
        total_clauses=total_clauses,
        has_notice=has_notice,
        enforcement_count=enforcement_count,
        total_penalty_usd=total_penalty,
        enforcement_regulators=regulators or [],
    )


# ── IC: Industry Classification ──────────────────────────────

def test_ic_fintech_maps_to_financial_services():
    org = _make_org(industry="fintech")
    ic, conf = compute_ic(org)
    assert ic == "financial_services"
    assert conf == 1.0


def test_ic_logistics_maps_to_supply_chain():
    """Known gap: logistics → supply_chain_services."""
    org = _make_org(industry="logistics")
    ic, conf = compute_ic(org)
    assert ic == "supply_chain_services"
    assert conf == 1.0


def test_ic_unmapped_industry():
    org = _make_org(industry="spacefaring")
    ic, conf = compute_ic(org)
    assert ic == "unmapped"
    assert conf == 0.5  # lower confidence for unmapped


def test_industry_map_covers_known_industries():
    """All three industries in our dataset are mapped."""
    for ind in ["fintech", "manufacturing", "logistics"]:
        assert ind in INDUSTRY_MAP


# ── RSS: Regulatory Scrutiny ─────────────────────────────────

def test_rss_high_for_data_heavy_fintech():
    org = _make_org(
        industry="fintech",
        clause_cats={"sensitive_data": 10, "data_sharing": 20, "children_teens": 5},
        total_clauses=200,
        enforcement_count=10,
    )
    rss, conf = compute_rss(org)
    # volume=30 + sensitive=25 + industry=21.25 + enforcement=20 = 96.25
    assert rss > 75, f"Expected high RSS, got {rss}"
    assert conf == 0.9


def test_rss_low_for_no_notice_org():
    org = _make_org(
        industry="manufacturing",
        total_clauses=0,
        has_notice=False,
    )
    rss, conf = compute_rss(org)
    assert rss < 50, f"Expected low RSS, got {rss}"
    assert conf == 0.3


# ── PGMS: Privacy Governance Maturity ────────────────────────

def test_pgms_zero_without_clauses():
    org = _make_org(total_clauses=0)
    pgms, conf = compute_pgms(org)
    assert pgms == 0.0
    assert conf == 0.3


def test_pgms_high_with_broad_coverage():
    org = _make_org(
        clause_cats={
            "consumer_rights": 12, "retention": 5, "cross_border": 8,
            "data_sharing": 15, "tracking_cookies": 6, "sensitive_data": 4,
        },
        total_clauses=50,
    )
    pgms, conf = compute_pgms(org)
    assert pgms > 50, f"Expected high PGMS, got {pgms}"
    assert conf == 0.8  # 6 categories present


# ── OSI: Organizational Sophistication ───────────────────────

def test_osi_large_us_with_unknown_public():
    """Large + US + unknown public_private → 75, low confidence."""
    org = _make_org(size="large", public_private=None)
    osi, conf = compute_osi(org)
    assert osi == 75.0  # 70 (large) + 5 (US)
    assert conf == 0.5  # penalized for missing public_private


def test_osi_large_public():
    org = _make_org(size="large", public_private="public")
    osi, conf = compute_osi(org)
    assert osi == 90.0  # 70 + 15 (public) + 5 (US)
    assert conf == 0.8


def test_osi_small_unknown():
    org = _make_org(size="small", public_private=None)
    osi, conf = compute_osi(org)
    assert osi == 35.0  # 30 (small) + 5 (US)
    assert conf == 0.5


# ── DSI: Data Sensitivity ────────────────────────────────────

def test_dsi_zero_without_clauses():
    org = _make_org(total_clauses=0)
    dsi, conf = compute_dsi(org)
    assert dsi == 0.0


def test_dsi_high_with_sensitive_data():
    org = _make_org(
        clause_cats={"sensitive_data": 5, "children_teens": 5, "ai_automated_decisions": 5},
        total_clauses=15,
    )
    dsi, conf = compute_dsi(org)
    assert dsi > 60, f"Expected high DSI, got {dsi}"


# ── EHP: Enforcement History ─────────────────────────────────

def test_ehp_zero_with_no_enforcement():
    org = _make_org(enforcement_count=0)
    ehp, conf = compute_ehp(org)
    assert ehp == 0.0
    assert conf == 0.4


def test_ehp_high_with_many_records():
    org = _make_org(
        enforcement_count=20,
        total_penalty=1_000_000,
        regulators=["FTC", "CPPA", "CA-AG", "CT-AG"],
    )
    ehp, conf = compute_ehp(org)
    assert ehp > 75, f"Expected high EHP, got {ehp}"


# ── AIGMS: AI Governance Maturity ────────────────────────────

def test_aigms_low_without_ai_clauses():
    org = _make_org(clause_cats={"data_sharing": 5}, total_clauses=5)
    aigms, conf = compute_aigms(org)
    assert aigms == 10.0  # baseline for no AI disclosure
    assert conf == 0.5


def test_aigms_high_with_ai_and_tracking():
    org = _make_org(
        clause_cats={"ai_automated_decisions": 5, "tracking_cookies": 3},
        total_clauses=8,
    )
    aigms, conf = compute_aigms(org)
    assert aigms >= 80, f"Expected high AIGMS, got {aigms}"


# ── Tiers ────────────────────────────────────────────────────

@pytest.mark.parametrize("score,expected_tier", [
    (0, "low"), (15, "low"), (24, "low"),
    (25, "moderate"), (49, "moderate"),
    (50, "elevated"), (74, "elevated"),
    (75, "high"), (100, "high"),
])
def test_score_to_tier(score, expected_tier):
    assert score_to_tier(score) == expected_tier


# ── Full profile ─────────────────────────────────────────────

def test_full_profile_has_all_dimensions():
    org = _make_org(
        industry="logistics",
        clause_cats={"data_sharing": 5, "consumer_rights": 3},
        total_clauses=8,
    )
    profile = compute_profile(org)
    assert profile.ic == "supply_chain_services"
    assert profile.ic_raw == "logistics"
    assert 0 <= profile.rss <= 100
    assert 0 <= profile.pgms <= 100
    assert 0 <= profile.osi <= 100
    assert 0 <= profile.dsi <= 100
    assert 0 <= profile.ehp <= 100
    assert 0 <= profile.aigms <= 100
    assert 0 < profile.confidence_score <= 1.0
    assert len(profile.tiers) == 6


def test_confidence_penalized_for_no_notice():
    org_with = _make_org(has_notice=True, clause_cats={"data_sharing": 5}, total_clauses=5)
    org_without = _make_org(has_notice=False, total_clauses=0)
    p_with = compute_profile(org_with)
    p_without = compute_profile(org_without)
    assert p_without.confidence_score < p_with.confidence_score


# ── Live data verification ───────────────────────────────────

def test_profiles_exist_in_db():
    """Verify 30 profiles were inserted."""
    import httpx
    from dotenv import dotenv_values
    import os

    config = dotenv_values(os.path.join(os.path.dirname(__file__), "..", ".env"))
    url, key = config["SUPABASE_URL"], config["SUPABASE_SERVICE_ROLE_KEY"]
    headers = {"apikey": key, "Authorization": f"Bearer {key}", "Prefer": "count=exact"}

    r = httpx.get(f"{url}/rest/v1/organization_intelligence_profile?select=*&limit=0", headers=headers, timeout=15)
    count = int(r.headers.get("content-range", "*/0").split("/")[-1])
    assert count == 30, f"Expected 30 profiles, got {count}"
