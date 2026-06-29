"""Clause-obligation matching tests — domain filter, cosine ranking, keyword fallback,
unverified flagging, idempotency."""

import numpy as np
import pytest

from app.services.scoring.obligation_match import (
    ObligationMatch,
    match_clauses_to_obligations,
)


# ── Fixture helpers ──────────────────────────────────────────

def _vec(angle_deg: float) -> list[float]:
    """384-dim unit vector at given angle in first 2 dims."""
    rad = np.radians(angle_deg)
    v = np.zeros(384)
    v[0] = np.cos(rad)
    v[1] = np.sin(rad)
    return v.tolist()

VEC_0 = _vec(0)
VEC_20 = _vec(20)    # cos(20°) ≈ 0.940
VEC_45 = _vec(45)    # cos(45°) ≈ 0.707
VEC_80 = _vec(80)    # cos(80°) ≈ 0.174


def _clause(cid="c1", domain="data_sharing", emb=VEC_0, text="share data with third party"):
    return {"clause_id": cid, "category": domain, "embedding": emb, "normalized_text": text}


def _obligation(oid="ob1", domain="data_sharing", emb=VEC_20, verified=False,
                law="CCPA/CPRA", req_type="notice_requirement", applicability="data sharing third party"):
    return {
        "obligation_id": oid, "domain": domain, "embedding": emb,
        "effective_date": "2025-01-01" if verified else None,
        "law": law, "requirement_type": req_type, "applicability": applicability,
    }


# ── Domain filter ────────────────────────────────────────────

def test_domain_filter_respected():
    """Only obligations matching the clause domain are considered."""
    clauses = [_clause(domain="data_sharing")]
    obligations = [
        _obligation(oid="ob-match", domain="data_sharing", emb=VEC_20),
        _obligation(oid="ob-wrong", domain="retention", emb=VEC_0),  # same vector but wrong domain
    ]
    matches = match_clauses_to_obligations(clauses, obligations)
    matched_ids = {m.obligation_id for m in matches}
    assert "ob-match" in matched_ids
    assert "ob-wrong" not in matched_ids


# ── Cosine ranking ───────────────────────────────────────────

def test_cosine_ranking_correct():
    """Closer embedding → higher similarity score."""
    clauses = [_clause(emb=VEC_0)]
    obligations = [
        _obligation(oid="ob-close", emb=VEC_20),   # cos≈0.94
        _obligation(oid="ob-far", emb=VEC_45),      # cos≈0.71
    ]
    matches = match_clauses_to_obligations(clauses, obligations, similarity_floor=0.3)
    sims = {m.obligation_id: m.similarity for m in matches}
    assert sims["ob-close"] > sims["ob-far"]


def test_similarity_floor_drops_weak():
    """Matches below floor are excluded (when keyword fallback also fails)."""
    clauses = [_clause(emb=VEC_0, text="unrelated topic xyz")]
    obligations = [
        _obligation(oid="ob-good", emb=VEC_20, applicability="unrelated topic xyz"),  # cos≈0.94
        _obligation(oid="ob-weak", emb=VEC_80, applicability="completely different content"),  # cos≈0.17
    ]
    matches = match_clauses_to_obligations(clauses, obligations, similarity_floor=0.35)
    matched_ids = {m.obligation_id for m in matches}
    assert "ob-good" in matched_ids
    assert "ob-weak" not in matched_ids


def test_known_cosine_value():
    """cos(20°) ≈ 0.940 — verify exact value."""
    clauses = [_clause(emb=VEC_0)]
    obligations = [_obligation(oid="ob1", emb=VEC_20)]
    matches = match_clauses_to_obligations(clauses, obligations, similarity_floor=0.0)
    assert len(matches) == 1
    assert abs(matches[0].similarity - 0.9397) < 0.01


# ── Keyword fallback ─────────────────────────────────────────

def test_keyword_fallback_fires():
    """When embeddings are missing, keyword matching kicks in."""
    clauses = [_clause(emb=None, text="data sharing with third party providers")]
    obligations = [_obligation(oid="ob-kw", emb=None,
                               applicability="data sharing third party providers")]
    matches = match_clauses_to_obligations(clauses, obligations)
    assert len(matches) >= 1
    assert matches[0].match_method in ("keyword", "keyword_unverified")


def test_keyword_fallback_no_match_on_low_overlap():
    """Too few keyword overlaps → no match."""
    clauses = [_clause(emb=None, text="cookies analytics")]
    obligations = [_obligation(oid="ob-no", emb=None,
                               applicability="completely different content here nothing shared")]
    matches = match_clauses_to_obligations(clauses, obligations)
    assert len(matches) == 0


# ── Unverified obligation flagging ───────────────────────────

def test_unverified_obligation_flagged():
    """Unverified obligations get 'embedding_unverified' method + confidence note."""
    clauses = [_clause(emb=VEC_0)]
    obligations = [_obligation(oid="ob-unv", emb=VEC_20, verified=False)]
    matches = match_clauses_to_obligations(clauses, obligations)
    assert len(matches) == 1
    m = matches[0]
    assert "unverified" in m.match_method
    assert m.is_verified is False
    assert "reduced" in m.confidence_note.lower() or "not yet verified" in m.confidence_note.lower()


def test_verified_obligation_normal_confidence():
    """Verified obligations get 'embedding' method, no confidence note."""
    clauses = [_clause(emb=VEC_0)]
    obligations = [_obligation(oid="ob-ver", emb=VEC_20, verified=True)]
    matches = match_clauses_to_obligations(clauses, obligations)
    assert len(matches) == 1
    m = matches[0]
    assert m.match_method == "embedding"
    assert m.is_verified is True
    assert m.confidence_note == ""


# ── Idempotency (dedup) ─────────────────────────────────────

def test_no_duplicate_matches():
    """Same (clause_id, obligation_id) pair never appears twice."""
    clauses = [_clause(cid="c1", emb=VEC_0)]
    obligations = [_obligation(oid="ob1", emb=VEC_20)]
    # Run twice with same inputs
    m1 = match_clauses_to_obligations(clauses, obligations)
    m2 = match_clauses_to_obligations(clauses, obligations)
    # Each run produces exactly 1 match (no duplicates within a run)
    assert len(m1) == 1
    assert len(m2) == 1


def test_multiple_clauses_multiple_obligations():
    """Each clause matched against its domain's obligations only."""
    clauses = [
        _clause(cid="c-ds", domain="data_sharing", emb=VEC_0),
        _clause(cid="c-ret", domain="retention", emb=VEC_0),
    ]
    obligations = [
        _obligation(oid="ob-ds", domain="data_sharing", emb=VEC_20),
        _obligation(oid="ob-ret", domain="retention", emb=VEC_20),
    ]
    matches = match_clauses_to_obligations(clauses, obligations)
    pairs = {(m.clause_id, m.obligation_id) for m in matches}
    assert ("c-ds", "ob-ds") in pairs
    assert ("c-ret", "ob-ret") in pairs
    assert ("c-ds", "ob-ret") not in pairs  # cross-domain blocked


# ── Empty inputs ─────────────────────────────────────────────

def test_empty_clauses():
    assert match_clauses_to_obligations([], [_obligation()]) == []


def test_empty_obligations():
    assert match_clauses_to_obligations([_clause()], []) == []
