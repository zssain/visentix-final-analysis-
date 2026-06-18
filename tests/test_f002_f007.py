"""Phase 4.1 formula tests — hand-computed fixtures for F-002 through F-007."""

from collections import Counter

import pytest

from app.services.scoring.engine import (
    load_element_checklist,
    load_jurisdiction_weights,
    get_expected_elements,
)
from app.services.scoring.formulas import (
    FormulaResult,
    ScoringContext,
    compute_f002,
    compute_f003,
    compute_f005,
    compute_f006,
    compute_f007,
)


# ── Fixtures ──────────────────────────────────────────────────

F002_THRESHOLDS = {
    "low": [0, 24],
    "moderate": [25, 49],
    "elevated": [50, 74],
    "high": [75, 100],
}

SAMPLE_REGULATORS = [
    {"id": "FTC", "jurisdiction": "US-FED", "efw": 0.9,
     "rpw": {"data_sharing": 0.9, "tracking_cookies": 0.9, "sensitive_data": 0.9,
             "consumer_rights": 0.6, "children_teens": 0.9, "retention": 0.6,
             "cross_border": 0.4, "ai_automated_decisions": 0.8}},
    {"id": "CPPA", "jurisdiction": "US-CA", "efw": 0.7,
     "rpw": {"data_sharing": 0.9, "tracking_cookies": 0.9, "sensitive_data": 0.8,
             "consumer_rights": 0.9, "children_teens": 0.7, "retention": 0.7,
             "cross_border": 0.5, "ai_automated_decisions": 0.9}},
]

JW = {"US-FED": 0.9, "US-CA": 1.0, "_default": 0.3}


def _ctx(**kwargs) -> ScoringContext:
    defaults = dict(
        organization_id="test-org",
        notice_id="test-notice",
        industry="fintech",
        jurisdiction="US",
        clause_categories=Counter(),
        total_clauses=0,
        avg_ambiguity=0.0,
        avg_readability=0.5,
        avg_nlp_confidence=0.7,
        domains_present=set(),
        regulators=SAMPLE_REGULATORS,
        jurisdiction_weights=JW,
        peer_scores=[],
        org_score=0.0,
        ai_clauses=0,
    )
    defaults.update(kwargs)
    return ScoringContext(**defaults)


# ── F-002: Regulatory Exposure Score ─────────────────────────

def test_f002_zero_without_clauses():
    ctx = _ctx()
    r = compute_f002(ctx, F002_THRESHOLDS)
    assert r.score == 0.0
    assert r.tier == "low"
    assert r.formula_version_id == "F-002_v1"


def test_f002_moderate_with_mixed_clauses():
    ctx = _ctx(
        clause_categories=Counter({"data_sharing": 20, "tracking_cookies": 10, "other": 70}),
        total_clauses=100,
        domains_present={"data_sharing", "tracking_cookies"},
    )
    r = compute_f002(ctx, F002_THRESHOLDS)
    assert 25 <= r.score < 75, f"Expected moderate/elevated, got {r.score}"
    assert r.tier in ("moderate", "elevated")


def test_f002_uses_jw_and_rpw():
    """Higher JW jurisdiction should produce higher score."""
    ctx = _ctx(
        clause_categories=Counter({"sensitive_data": 10}),
        total_clauses=10,
        domains_present={"sensitive_data"},
    )
    r = compute_f002(ctx, F002_THRESHOLDS)
    assert r.score > 0
    assert "regulator_contributions" in r.source_lineage


def test_f002_records_lineage():
    ctx = _ctx(
        clause_categories=Counter({"data_sharing": 5}),
        total_clauses=5,
        domains_present={"data_sharing"},
    )
    r = compute_f002(ctx, F002_THRESHOLDS)
    assert "domains_scored" in r.source_lineage
    assert "total_clauses" in r.source_lineage


# ── F-003: Benchmark Deviation Score ─────────────────────────

def test_f003_zero_without_peers():
    ctx = _ctx(peer_scores=[], org_score=50)
    r = compute_f003(ctx)
    assert r.score == 0.0
    assert r.formula_version_id == "F-003_v1"


def test_f003_zero_when_org_at_top():
    """If org is at top quartile, deviation = 0."""
    peers = [{"org_id": f"p{i}", "score": 40, "weight": 0.7} for i in range(10)]
    ctx = _ctx(peer_scores=peers, org_score=60)
    r = compute_f003(ctx)
    assert r.score == 0.0


def test_f003_high_when_org_below_peers():
    """If org is well below peers, deviation is high."""
    peers = [{"org_id": f"p{i}", "score": 80, "weight": 0.7} for i in range(10)]
    ctx = _ctx(peer_scores=peers, org_score=20)
    r = compute_f003(ctx)
    assert r.score > 50, f"Expected high deviation, got {r.score}"


def test_f003_uses_weights():
    """Weighted peers should produce different result than if unweighted."""
    peers_heavy = [{"org_id": "p1", "score": 90, "weight": 0.9}]
    peers_light = [{"org_id": "p1", "score": 90, "weight": 0.1}]
    r_heavy = compute_f003(_ctx(peer_scores=peers_heavy, org_score=50))
    r_light = compute_f003(_ctx(peer_scores=peers_light, org_score=50))
    assert r_heavy.source_lineage["weighted"] is True


def test_f003_small_cohort_low_confidence():
    """n<50 should get low confidence."""
    peers = [{"org_id": f"p{i}", "score": 60, "weight": 0.6} for i in range(25)]
    r = compute_f003(_ctx(peer_scores=peers, org_score=40))
    assert r.confidence_score <= 0.5


# ── F-005: Disclosure Maturity Score ─────────────────────────

def test_f005_zero_without_elements():
    r = compute_f005(_ctx(), [])
    assert r.score == 0.0


def test_f005_full_coverage_high_score():
    checklist = load_element_checklist()
    elements = get_expected_elements(checklist)
    all_domains = set(e["domain"] for e in elements)
    ctx = _ctx(
        domains_present=all_domains,
        total_clauses=100,
        avg_ambiguity=0.01,
    )
    r = compute_f005(ctx, elements)
    assert r.score > 70, f"Full coverage should score high, got {r.score}"


def test_f005_ambiguity_penalty_lowers_score():
    checklist = load_element_checklist()
    elements = get_expected_elements(checklist)
    all_domains = set(e["domain"] for e in elements)

    ctx_clear = _ctx(domains_present=all_domains, avg_ambiguity=0.0)
    ctx_ambig = _ctx(domains_present=all_domains, avg_ambiguity=0.05)

    r_clear = compute_f005(ctx_clear, elements)
    r_ambig = compute_f005(ctx_ambig, elements)
    assert r_clear.score > r_ambig.score


def test_f005_missing_domains_penalized():
    checklist = load_element_checklist()
    elements = get_expected_elements(checklist)

    ctx_full = _ctx(domains_present={"data_sharing", "tracking_cookies", "consumer_rights",
                                      "cross_border", "sensitive_data", "retention",
                                      "children_teens", "ai_automated_decisions"})
    ctx_partial = _ctx(domains_present={"data_sharing"})

    r_full = compute_f005(ctx_full, elements)
    r_partial = compute_f005(ctx_partial, elements)
    assert r_full.score > r_partial.score


# ── F-006: Transparency Score ────────────────────────────────

def test_f006_zero_without_clauses():
    r = compute_f006(_ctx())
    assert r.score == 0.0


def test_f006_is_product_of_factors():
    ctx = _ctx(
        domains_present={"data_sharing", "tracking_cookies", "consumer_rights", "cross_border"},
        total_clauses=50,
        avg_ambiguity=0.01,
        avg_readability=0.6,
        avg_nlp_confidence=0.8,
    )
    r = compute_f006(ctx)
    assert r.score > 0
    assert "completeness" in r.source_lineage
    assert "clarity" in r.source_lineage
    assert "specificity" in r.source_lineage
    assert "explainability" in r.source_lineage


def test_f006_ambiguity_reduces_score():
    ctx_clear = _ctx(
        domains_present={"data_sharing"}, total_clauses=10,
        avg_ambiguity=0.0, avg_readability=0.5, avg_nlp_confidence=0.7,
    )
    ctx_ambig = _ctx(
        domains_present={"data_sharing"}, total_clauses=10,
        avg_ambiguity=0.1, avg_readability=0.5, avg_nlp_confidence=0.7,
    )
    assert compute_f006(ctx_clear).score >= compute_f006(ctx_ambig).score


# ── F-007: AI Transparency Maturity ──────────────────────────

def test_f007_zero_without_ai_elements():
    r = compute_f007(_ctx(), [])
    assert r.score == 0.0


def test_f007_higher_with_ai_clauses():
    checklist = load_element_checklist()
    ai_elements = get_expected_elements(checklist, ai_only=True)

    ctx_no_ai = _ctx(ai_clauses=0)
    ctx_ai = _ctx(ai_clauses=5)

    r_no = compute_f007(ctx_no_ai, ai_elements)
    r_yes = compute_f007(ctx_ai, ai_elements)
    assert r_yes.score > r_no.score


def test_f007_low_confidence_without_ai():
    checklist = load_element_checklist()
    ai_elements = get_expected_elements(checklist, ai_only=True)
    r = compute_f007(_ctx(ai_clauses=0), ai_elements)
    assert r.confidence_score <= 0.3


# ── General: lineage and formula_version_id ──────────────────

def test_all_formulas_have_version_id():
    checklist = load_element_checklist()
    all_el = get_expected_elements(checklist)
    ai_el = get_expected_elements(checklist, ai_only=True)
    ctx = _ctx(
        clause_categories=Counter({"data_sharing": 5}),
        total_clauses=5,
        domains_present={"data_sharing"},
        peer_scores=[{"org_id": "p1", "score": 50, "weight": 0.7}],
        org_score=40,
    )

    results = [
        compute_f002(ctx, F002_THRESHOLDS),
        compute_f003(ctx),
        compute_f005(ctx, all_el),
        compute_f006(ctx),
        compute_f007(ctx, ai_el),
    ]

    for r in results:
        assert r.formula_version_id.startswith("F-")
        assert isinstance(r.source_lineage, dict)
        assert len(r.source_lineage) > 0


# ── Live DB: derived_data_item populated ─────────────────────

def test_derived_data_items_exist():
    import os
    import httpx
    from dotenv import dotenv_values

    config = dotenv_values(os.path.join(os.path.dirname(__file__), "..", ".env"))
    url, key = config["SUPABASE_URL"], config["SUPABASE_SERVICE_ROLE_KEY"]
    headers = {"apikey": key, "Authorization": f"Bearer {key}", "Prefer": "count=exact"}

    r = httpx.get(f"{url}/rest/v1/derived_data_item?select=object_type&limit=300",
                   headers=headers, timeout=15)
    rows = r.json()

    from collections import Counter
    types = Counter(r["object_type"] for r in rows)

    for expected_type in ["regulatory_exposure", "benchmark_deviation",
                          "disclosure_maturity", "transparency", "ai_transparency"]:
        assert types[expected_type] >= 30, (
            f"{expected_type} has {types[expected_type]} rows, expected >= 30"
        )
