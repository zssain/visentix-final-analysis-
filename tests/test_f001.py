"""F-001 Source Reliability tests — hand-computed fixtures, deterministic, insert-only."""

import pytest

from app.services.scoring.f001 import F001Result, compute_f001


# ── Hand-computed fixtures ───────────────────────────────────

def test_equal_weights_simple_average():
    """With equal 0.25 weights: (1.0 + 0.7 + 1.0 + 1.0) / 4 = 0.925."""
    r = compute_f001("SRC-001", 1.0, 0.7, 1.0, 1.0,
                     weights={"authority": 0.25, "freshness": 0.25,
                              "completeness": 0.25, "extraction_confidence": 0.25})
    assert r.score == 0.925
    assert r.score_100 == 92.5


def test_all_ones():
    """All components = 1.0 → score = 1.0."""
    r = compute_f001("SRC-002", 1.0, 1.0, 1.0, 1.0)
    assert r.score == 1.0
    assert r.score_100 == 100.0


def test_all_zeros():
    """All components = 0 → score = 0."""
    r = compute_f001("SRC-003", 0.0, 0.0, 0.0, 0.0)
    assert r.score == 0.0


def test_mixed_values():
    """(0.8 + 0.5 + 0.9 + 0.6) × 0.25 each = 0.7."""
    r = compute_f001("SRC-004", 0.8, 0.5, 0.9, 0.6,
                     weights={"authority": 0.25, "freshness": 0.25,
                              "completeness": 0.25, "extraction_confidence": 0.25})
    assert r.score == 0.7
    assert r.score_100 == 70.0


def test_unequal_weights():
    """Custom weights: auth=0.4, fresh=0.2, compl=0.3, extr=0.1.
    Score = 1.0×0.4 + 0.5×0.2 + 0.8×0.3 + 0.6×0.1 = 0.4+0.1+0.24+0.06 = 0.8."""
    r = compute_f001("SRC-005", 1.0, 0.5, 0.8, 0.6,
                     weights={"authority": 0.4, "freshness": 0.2,
                              "completeness": 0.3, "extraction_confidence": 0.1})
    assert r.score == 0.8
    assert r.score_100 == 80.0


# ── Clamping ─────────────────────────────────────────────────

def test_clamped_to_1():
    """Score > 1.0 should clamp to 1.0."""
    r = compute_f001("SRC-006", 1.5, 1.5, 1.5, 1.5)
    assert r.score == 1.0


def test_clamped_to_0():
    """Negative components clamp score to 0."""
    r = compute_f001("SRC-007", -0.5, -0.5, -0.5, -0.5)
    assert r.score == 0.0


# ── Deterministic ────────────────────────────────────────────

def test_reproducible():
    """Same inputs → identical score."""
    r1 = compute_f001("SRC-008", 0.9, 0.7, 0.8, 0.95)
    r2 = compute_f001("SRC-008", 0.9, 0.7, 0.8, 0.95)
    assert r1.score == r2.score
    assert r1.components == r2.components


# ── Lineage ──────────────────────────────────────────────────

def test_components_stored():
    r = compute_f001("SRC-009", 0.8, 0.6, 0.9, 0.7)
    assert r.components["authority"] == 0.8
    assert r.components["freshness"] == 0.6
    assert r.components["completeness"] == 0.9
    assert r.components["extraction_confidence"] == 0.7


def test_formula_version_id():
    r = compute_f001("SRC-010", 1.0, 1.0, 1.0, 1.0)
    assert r.formula_version_id == "F-001_v1"


def test_source_id_preserved():
    r = compute_f001("SRC-CUSTOM-ID", 0.5, 0.5, 0.5, 0.5)
    assert r.source_id == "SRC-CUSTOM-ID"


# ── No LLM ───────────────────────────────────────────────────

def test_no_llm_in_module():
    import inspect
    source = inspect.getsource(compute_f001)
    for word in ["ollama", "qwen", "openai", "model.encode"]:
        assert word not in source.lower()
