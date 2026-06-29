"""Clause-obligation matching — domain filter + cosine ranking + keyword fallback.

Matches are EXPOSURE CONTEXT only — never a legal conclusion.
Unverified obligations (effective_date=NULL) carry reduced confidence.

Reuses similarity helper from similarity.py for cosine computation.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

import numpy as np


SIMILARITY_FLOOR = 0.35  # cosine floor — below this = no match
KEYWORD_MIN_HITS = 2  # minimum keyword overlaps for keyword fallback


@dataclass
class ObligationMatch:
    """One clause → obligation match."""

    clause_id: str
    obligation_id: str
    match_method: str  # 'embedding' | 'keyword' | 'embedding_unverified'
    similarity: float
    domain: str
    is_verified: bool  # True if obligation has effective_date
    confidence_note: str = ""


def match_clauses_to_obligations(
    clauses: list[dict],
    obligations: list[dict],
    similarity_floor: float = SIMILARITY_FLOOR,
) -> list[ObligationMatch]:
    """Match clauses to obligations by domain + cosine similarity.

    clauses: [{clause_id, category, embedding (list|str), normalized_text}]
    obligations: [{obligation_id, domain, embedding (list|str|None),
                   effective_date, law, requirement_type, applicability}]

    Strategy:
    1. Filter obligations by matching domain
    2. Rank by cosine similarity (if both have embeddings)
    3. Fall back to keyword matching when embeddings are missing
    4. Flag unverified obligations with reduced confidence
    """
    results = []
    seen = set()  # (clause_id, obligation_id) for dedup

    for clause in clauses:
        c_domain = clause.get("category", "other")
        c_emb = _parse_embedding(clause.get("embedding"))
        c_text = clause.get("normalized_text", "")

        # Domain-filtered candidates
        candidates = [
            ob for ob in obligations
            if ob.get("domain", "") == c_domain
        ]

        if not candidates:
            continue

        for ob in candidates:
            key = (clause["clause_id"], ob["obligation_id"])
            if key in seen:
                continue

            ob_emb = _parse_embedding(ob.get("embedding"))
            is_verified = ob.get("effective_date") is not None

            match = None

            # Try embedding match first
            if c_emb is not None and ob_emb is not None:
                sim = _cosine_similarity(c_emb, ob_emb)
                if sim >= similarity_floor:
                    method = "embedding" if is_verified else "embedding_unverified"
                    confidence_note = "" if is_verified else (
                        "Obligation not yet verified (effective_date=NULL). "
                        "Match confidence reduced — do not treat as definitive."
                    )
                    match = ObligationMatch(
                        clause_id=clause["clause_id"],
                        obligation_id=ob["obligation_id"],
                        match_method=method,
                        similarity=round(sim, 4),
                        domain=c_domain,
                        is_verified=is_verified,
                        confidence_note=confidence_note,
                    )

            # Keyword fallback when embedding match missed
            if match is None and c_text:
                hits = _keyword_overlap(c_text, ob)
                if hits >= KEYWORD_MIN_HITS:
                    sim = round(min(hits * 0.15, 0.8), 4)  # synthetic similarity
                    method = "keyword" if is_verified else "keyword_unverified"
                    confidence_note = "" if is_verified else (
                        "Obligation not yet verified. Keyword match only — reduced confidence."
                    )
                    match = ObligationMatch(
                        clause_id=clause["clause_id"],
                        obligation_id=ob["obligation_id"],
                        match_method=method,
                        similarity=sim,
                        domain=c_domain,
                        is_verified=is_verified,
                        confidence_note=confidence_note,
                    )

            if match:
                results.append(match)
                seen.add(key)

    return results


def _parse_embedding(emb) -> np.ndarray | None:
    if emb is None:
        return None
    if isinstance(emb, str):
        try:
            emb = json.loads(emb)
        except (json.JSONDecodeError, ValueError):
            return None
    arr = np.array(emb, dtype=np.float32)
    return arr if arr.size > 0 else None


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a < 1e-9 or norm_b < 1e-9:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def _keyword_overlap(clause_text: str, obligation: dict) -> int:
    """Count keyword overlaps between clause text and obligation fields."""
    ob_text = " ".join([
        obligation.get("law", ""),
        obligation.get("requirement_type", ""),
        obligation.get("applicability", ""),
    ]).lower()

    # Extract meaningful words (>3 chars)
    ob_words = set(re.findall(r'\b[a-z]{4,}\b', ob_text))
    clause_words = set(re.findall(r'\b[a-z]{4,}\b', clause_text.lower()))

    return len(ob_words & clause_words)
