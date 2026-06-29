"""F-004 Enforcement Correlation tests — fixture corpus with known similarities."""

import numpy as np
import pytest

from app.services.scoring.formulas import EnforcementMatch, FormulaResult, compute_f004
from app.services.scoring.similarity import top_k_enforcement_sync


# ── Fixture embeddings with KNOWN cosine similarities ────────

def _unit_vec(angle_deg: float) -> list[float]:
    """Create a 384-dim unit vector at a given angle in the first 2 dims."""
    rad = np.radians(angle_deg)
    v = np.zeros(384)
    v[0] = np.cos(rad)
    v[1] = np.sin(rad)
    return v.tolist()


# Known pairs:
#   0° vs 0° = cos(0) = 1.0
#   0° vs 30° = cos(30°) ≈ 0.866
#   0° vs 60° = cos(60°) = 0.5
#   0° vs 90° = cos(90°) = 0.0
CLAUSE_0 = _unit_vec(0)
ENF_0 = _unit_vec(0)      # sim = 1.0
ENF_30 = _unit_vec(30)    # sim ≈ 0.866
ENF_60 = _unit_vec(60)    # sim = 0.5
ENF_90 = _unit_vec(90)    # sim ≈ 0.0


# ── similarity.py tests ─────────────────────────────────────

def test_top_k_returns_sorted_desc():
    rows = [
        {"enforcement_id": "e1", "regulator_id": "FTC", "embedding": ENF_30},
        {"enforcement_id": "e2", "regulator_id": "CPPA", "embedding": ENF_0},
        {"enforcement_id": "e3", "regulator_id": "FTC", "embedding": ENF_60},
    ]
    results = top_k_enforcement_sync(CLAUSE_0, rows, k=3, similarity_floor=0.0)
    assert len(results) == 3
    assert results[0]["enforcement_id"] == "e2"  # sim=1.0
    assert results[1]["enforcement_id"] == "e1"  # sim≈0.866
    assert results[2]["enforcement_id"] == "e3"  # sim=0.5


def test_top_k_respects_floor():
    rows = [
        {"enforcement_id": "e1", "regulator_id": "FTC", "embedding": ENF_0},   # 1.0
        {"enforcement_id": "e2", "regulator_id": "FTC", "embedding": ENF_90},  # ~0.0
    ]
    results = top_k_enforcement_sync(CLAUSE_0, rows, k=5, similarity_floor=0.30)
    assert len(results) == 1
    assert results[0]["enforcement_id"] == "e1"


def test_top_k_caps_at_k():
    rows = [
        {"enforcement_id": f"e{i}", "regulator_id": "FTC", "embedding": ENF_0}
        for i in range(20)
    ]
    results = top_k_enforcement_sync(CLAUSE_0, rows, k=5, similarity_floor=0.0)
    assert len(results) == 5


def test_top_k_known_cosine_sim():
    rows = [{"enforcement_id": "e30", "regulator_id": "FTC", "embedding": ENF_30}]
    results = top_k_enforcement_sync(CLAUSE_0, rows, k=1, similarity_floor=0.0)
    # cos(30°) ≈ 0.866
    assert abs(results[0]["cosine_similarity"] - 0.866) < 0.01


def test_top_k_empty_inputs():
    assert top_k_enforcement_sync(CLAUSE_0, [], k=5) == []
    assert top_k_enforcement_sync([], [{"enforcement_id": "e1", "regulator_id": "FTC", "embedding": ENF_0}], k=5) == []


# ── compute_f004 tests ───────────────────────────────────────

def _make_match(es: float, rpw: float, efw: float, **kwargs) -> EnforcementMatch:
    return EnforcementMatch(
        clause_id=kwargs.get("clause_id", "c1"),
        enforcement_id=kwargs.get("enforcement_id", "e1"),
        regulator_id=kwargs.get("regulator_id", "FTC"),
        cosine_similarity=es,
        rpw=rpw,
        efw=efw,
        domain=kwargs.get("domain", "data_sharing"),
    )


def test_f004_basic_score():
    """ES=0.8, RPW=0.9, EFW=0.9 → 0.8×0.9×0.9×100 = 64.8."""
    m = _make_match(es=0.8, rpw=0.9, efw=0.9)
    result = compute_f004([m])
    # Single match: weighted mean = match_score itself
    assert abs(result.score - 64.8) < 0.5
    assert result.formula_version_id == "F-004_v1"


def test_f004_floor_filters():
    """Matches below floor are dropped."""
    m_good = _make_match(es=0.5, rpw=0.9, efw=0.9)
    m_bad = _make_match(es=0.20, rpw=0.9, efw=0.9)
    result = compute_f004([m_good, m_bad], similarity_floor=0.30)
    # Only m_good contributes
    assert result.source_lineage["n_matches"] == 1


def test_f004_zero_when_no_matches():
    result = compute_f004([], similarity_floor=0.30)
    assert result.score == 0.0
    assert result.source_lineage["reason"] == "no_matches_above_floor"


def test_f004_clamped_0_100():
    """Even extreme values clamp to 100."""
    m = _make_match(es=1.0, rpw=1.0, efw=1.0)
    result = compute_f004([m])
    assert result.score <= 100.0
    assert result.score >= 0.0


def test_f004_rpw_efw_multiply():
    """Higher RPW/EFW → higher score at same ES."""
    m_high = _make_match(es=0.6, rpw=0.9, efw=0.9)
    m_low = _make_match(es=0.6, rpw=0.3, efw=0.3)
    r_high = compute_f004([m_high])
    r_low = compute_f004([m_low])
    assert r_high.score > r_low.score


def test_f004_threshold_mapping():
    """When thresholds are provided, tier is set."""
    m = _make_match(es=0.8, rpw=0.9, efw=0.9)
    thresholds = {"low": [0, 24], "moderate": [25, 49], "elevated": [50, 74], "high": [75, 100]}
    result = compute_f004([m], thresholds=thresholds)
    assert result.tier in ("low", "moderate", "elevated", "high")


def test_f004_reproducibility():
    """Same inputs → identical score twice."""
    matches = [
        _make_match(es=0.7, rpw=0.8, efw=0.7, clause_id="c1", enforcement_id="e1"),
        _make_match(es=0.5, rpw=0.6, efw=0.9, clause_id="c2", enforcement_id="e2"),
        _make_match(es=0.4, rpw=0.9, efw=0.5, clause_id="c3", enforcement_id="e3"),
    ]
    r1 = compute_f004(matches)
    r2 = compute_f004(matches)
    assert r1.score == r2.score
    assert r1.source_lineage == r2.source_lineage


def test_f004_lineage_includes_matches():
    m = _make_match(es=0.6, rpw=0.9, efw=0.8, enforcement_id="e-test")
    result = compute_f004([m])
    lineage = result.source_lineage
    assert "matches" in lineage
    assert len(lineage["matches"]) == 1
    assert lineage["matches"][0]["enforcement_id"] == "e-test"
    assert lineage["matches"][0]["ES"] == 0.6
    assert lineage["matches"][0]["RPW"] == 0.9
    assert lineage["matches"][0]["EFW"] == 0.8


def test_f004_no_llm_calls():
    """Verify no model/LLM imports in the scoring module."""
    import inspect
    source = inspect.getsource(compute_f004)
    for banned in ["ollama", "qwen", "openai", "anthropic", "SentenceTransformer", "model.encode"]:
        assert banned not in source.lower()
