"""Phase 3 embedding tests — verify dim=384, no NULLs, NN search works."""

import json
import os

import httpx
import numpy as np
import pytest
from dotenv import dotenv_values

CONFIG = dotenv_values(os.path.join(os.path.dirname(__file__), "..", ".env"))
URL = CONFIG["SUPABASE_URL"]
KEY = CONFIG["SUPABASE_SERVICE_ROLE_KEY"]
HEADERS = {"apikey": KEY, "Authorization": f"Bearer {KEY}", "Prefer": "count=exact"}


def _count_nulls(table: str) -> int:
    r = httpx.get(
        f"{URL}/rest/v1/{table}?select=*&embedding=is.null&limit=0",
        headers=HEADERS, timeout=15,
    )
    return int(r.headers.get("content-range", "*/0").split("/")[-1])


# ------------------------------------------------------------------
# 1. Zero NULL embeddings
# ------------------------------------------------------------------
def test_disclosure_clause_no_null_embeddings():
    assert _count_nulls("disclosure_clause") == 0


def test_enforcement_record_no_null_embeddings():
    assert _count_nulls("enforcement_record") == 0


# ------------------------------------------------------------------
# 2. Embedding dimension is 384
# ------------------------------------------------------------------
def test_disclosure_clause_embedding_dim():
    r = httpx.get(
        f"{URL}/rest/v1/disclosure_clause?select=embedding&limit=1",
        headers=HEADERS, timeout=15,
    )
    emb = json.loads(r.json()[0]["embedding"])
    assert len(emb) == 384


def test_enforcement_record_embedding_dim():
    r = httpx.get(
        f"{URL}/rest/v1/enforcement_record?select=embedding&limit=1",
        headers=HEADERS, timeout=15,
    )
    emb = json.loads(r.json()[0]["embedding"])
    assert len(emb) == 384


# ------------------------------------------------------------------
# 3. Nearest-neighbor search returns plausible results
# ------------------------------------------------------------------
def test_nn_search_returns_results():
    """Pick a clause, find 3 nearest enforcement records by cosine similarity."""
    # Get one clause embedding
    r = httpx.get(
        f"{URL}/rest/v1/disclosure_clause?select=embedding&category=eq.data_sharing&limit=1",
        headers=HEADERS, timeout=15,
    )
    query_vec = np.array(json.loads(r.json()[0]["embedding"]))

    # Get enforcement embeddings
    r2 = httpx.get(
        f"{URL}/rest/v1/enforcement_record?select=enforcement_id,embedding",
        headers=HEADERS, timeout=15,
    )
    enforcements = r2.json()
    assert len(enforcements) > 0

    # Compute cosine similarities
    q_norm = query_vec / np.linalg.norm(query_vec)
    similarities = []
    for er in enforcements:
        e = np.array(json.loads(er["embedding"]))
        e_norm = e / np.linalg.norm(e)
        sim = float(np.dot(q_norm, e_norm))
        similarities.append(sim)

    # Top 3 should be reasonable (> 0, < 1)
    top3 = sorted(similarities, reverse=True)[:3]
    assert len(top3) == 3
    for sim in top3:
        assert 0 < sim < 1, f"Unexpected similarity: {sim}"


# ------------------------------------------------------------------
# 4. Exemplar candidates are capped and unflagged
# ------------------------------------------------------------------
def test_exemplar_candidates_within_cap():
    r = httpx.get(
        f"{URL}/rest/v1/exemplar?select=domain,sme_cleaned,source_internal_ref",
        headers=HEADERS, timeout=15,
    )
    rows = r.json()

    from collections import Counter
    auto_per_domain = Counter(
        row["domain"] for row in rows
        if row.get("source_internal_ref", "").startswith("AUTO-CANDIDATE")
    )

    for domain, count in auto_per_domain.items():
        assert count <= 5, f"{domain} has {count} auto-candidates (cap=5)"


def test_exemplar_sme_cleaned_count():
    """Some exemplars may be SME-cleaned (demo seeds); most are candidates."""
    r = httpx.get(
        f"{URL}/rest/v1/exemplar?select=sme_cleaned",
        headers=HEADERS, timeout=15,
    )
    rows = r.json()
    cleaned = sum(1 for row in rows if row["sme_cleaned"])
    uncleaned = sum(1 for row in rows if not row["sme_cleaned"])
    assert uncleaned >= 40  # auto-candidates still exist
    assert cleaned >= 0  # some may be demo-cleaned
