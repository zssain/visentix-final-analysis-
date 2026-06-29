"""Reusable pgvector nearest-neighbour helpers.

Used by F-004 (enforcement correlation) and clause_obligation matching.
All functions are pure reads — they never write to the database.
"""

from __future__ import annotations

import json

import httpx

from app.config import settings
from app.db import get_service_headers

# Defaults — callers may override
DEFAULT_K = 5
SIMILARITY_FLOOR = 0.30  # ignore matches below this cosine similarity


async def top_k_enforcement_for_clause(
    clause_id: str,
    k: int = DEFAULT_K,
    domain: str | None = None,
    similarity_floor: float = SIMILARITY_FLOOR,
) -> list[dict]:
    """Find the k nearest enforcement_record embeddings to a clause.

    Uses Supabase PostgREST with the pgvector cosine operator.
    Since PostgREST doesn't support <=> directly, we fetch the clause
    embedding and compute similarity client-side against enforcement
    embeddings. The ivfflat index accelerates the DB reads.

    Returns: [{enforcement_id, regulator_id, cosine_similarity}]
             sorted by similarity descending, filtered by floor.
    """
    headers = get_service_headers()

    # Fetch clause embedding
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(
            f"{settings.supabase_url}/rest/v1/disclosure_clause"
            f"?select=embedding,category&clause_id=eq.{clause_id}&limit=1",
            headers=headers,
        )
        clause_rows = r.json()
        if not clause_rows or not clause_rows[0].get("embedding"):
            return []

        clause_emb = clause_rows[0]["embedding"]
        clause_domain = clause_rows[0].get("category", "")
        if isinstance(clause_emb, str):
            clause_emb = json.loads(clause_emb)

        # Fetch enforcement embeddings (with optional domain filter via issue_tags)
        r2 = await client.get(
            f"{settings.supabase_url}/rest/v1/enforcement_record"
            f"?select=enforcement_id,regulator_id,embedding",
            headers=headers,
        )
        enforcements = r2.json()

    return _compute_top_k(clause_emb, enforcements, k, similarity_floor)


def top_k_enforcement_sync(
    clause_embedding: list[float],
    enforcement_rows: list[dict],
    k: int = DEFAULT_K,
    similarity_floor: float = SIMILARITY_FLOOR,
) -> list[dict]:
    """Synchronous version — embeddings already loaded in memory.

    clause_embedding: 384-dim list
    enforcement_rows: [{enforcement_id, regulator_id, embedding (str or list)}]
    Returns: [{enforcement_id, regulator_id, cosine_similarity}]
    """
    return _compute_top_k(clause_embedding, enforcement_rows, k, similarity_floor)


def _compute_top_k(
    clause_emb: list[float],
    enforcement_rows: list[dict],
    k: int,
    similarity_floor: float,
) -> list[dict]:
    """Core computation: cosine similarity, top-k, floor filter."""
    import numpy as np

    if not clause_emb:
        return []

    q = np.array(clause_emb, dtype=np.float32)
    if q.size == 0:
        return []
    q_norm = q / (np.linalg.norm(q) + 1e-9)

    results = []
    for er in enforcement_rows:
        emb = er.get("embedding")
        if not emb:
            continue
        if isinstance(emb, str):
            emb = json.loads(emb)

        e = np.array(emb, dtype=np.float32)
        e_norm = e / (np.linalg.norm(e) + 1e-9)

        cos_sim = float(np.dot(q_norm, e_norm))

        if cos_sim >= similarity_floor:
            results.append({
                "enforcement_id": er["enforcement_id"],
                "regulator_id": er.get("regulator_id", ""),
                "cosine_similarity": round(cos_sim, 6),
            })

    # Sort descending, take top-k
    results.sort(key=lambda x: -x["cosine_similarity"])
    return results[:k]
