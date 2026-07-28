"""Embeddings service — local sentence-transformers encoder (all-MiniLM-L6-v2).

Model is named authoritatively in schema.md §Storage (`all-MiniLM-L6-v2`, 384-dim)
and `settings.embedding_model`. **Local model only — no external embedding API**
(Rule 7 / MUST NOT). GPU-aware: prefers CUDA (RunPod), then Apple MPS, then CPU.

Responsibilities:
- Encode text into 384-dim vectors, batched (default 256), on the best device.
- Provide the record of which model produced a vector (`EMBEDDING_MODEL_NAME`),
  written to each row's `embedding_model` column by the backfill.
- `embed_clauses()`: idempotent batch embed of specific clauses — only rows whose
  `embedding IS NULL` are encoded and written; already-embedded rows are skipped.

All writes go to the `embedding` / `embedding_model` columns only; no existing
embedding is ever overwritten.
"""

from __future__ import annotations

import logging
import threading
from functools import lru_cache

import httpx

from app.config import settings
from app.db import get_service_headers, supabase_rest_get

log = logging.getLogger(__name__)

# Single source of truth for the model tag stored per row.
EMBEDDING_MODEL_NAME = settings.embedding_model  # "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIM = 384
DEFAULT_BATCH_SIZE = 256

_model_lock = threading.Lock()


def _select_device() -> str:
    """Pick the best available device: CUDA (RunPod GPU) > Apple MPS > CPU."""
    try:
        import torch
    except ImportError:  # pragma: no cover - torch ships with sentence-transformers
        return "cpu"
    if torch.cuda.is_available():
        return "cuda"
    if getattr(torch.backends, "mps", None) is not None and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


@lru_cache(maxsize=1)
def get_model():
    """Load (once) the local SentenceTransformer on the best device. Cached."""
    from sentence_transformers import SentenceTransformer

    device = _select_device()
    with _model_lock:
        model = SentenceTransformer(EMBEDDING_MODEL_NAME, device=device)
    dim = model.get_sentence_embedding_dimension()
    if dim != EMBEDDING_DIM:
        raise RuntimeError(
            f"Model {EMBEDDING_MODEL_NAME} produced dim {dim}, expected {EMBEDDING_DIM}"
        )
    log.info("Embedding model loaded: %s on device=%s (dim=%d)",
             EMBEDDING_MODEL_NAME, device, dim)
    return model


def embed_texts(
    texts: list[str],
    batch_size: int = DEFAULT_BATCH_SIZE,
    normalize: bool = True,
) -> list[list[float]]:
    """Encode texts → list of 384-dim float lists. GPU-aware, batched.

    normalize=True returns unit vectors, so downstream cosine similarity is a
    plain dot product (matches similarity.py / obligation_match.py conventions).
    """
    if not texts:
        return []
    model = get_model()
    vecs = model.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=False,
        normalize_embeddings=normalize,
        convert_to_numpy=True,
    )
    return vecs.tolist()


def to_pgvector(vec: list[float]) -> str:
    """Serialize a vector to the pgvector text form PostgREST accepts."""
    return "[" + ",".join(f"{x:.7f}" for x in vec) + "]"


def write_clause_embeddings(rows: list[dict], timeout: float = 60.0) -> int:
    """Bulk-write clause embeddings via the idempotent apply_clause_embeddings RPC.

    rows: [{"clause_id", "embedding" (list[float]), ...}]. The RPC updates only
    rows whose `embedding IS NULL`, so re-running never overwrites. Returns the
    number of rows actually updated (already-embedded rows count as 0). Sync so
    the batch backfill script can call it in a simple loop.
    """
    if not rows:
        return 0
    payload = {
        "rows": [
            {
                "clause_id": r["clause_id"],
                "embedding": to_pgvector(r["embedding"]),
                "embedding_model": EMBEDDING_MODEL_NAME,
            }
            for r in rows
        ]
    }
    resp = httpx.post(
        f"{settings.supabase_url}/rest/v1/rpc/apply_clause_embeddings",
        headers={**get_service_headers(), "Content-Type": "application/json"},
        json=payload,
        timeout=timeout,
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"apply_clause_embeddings failed: {resp.status_code} {resp.text[:200]}")
    try:
        return int(resp.json())
    except (ValueError, TypeError):
        return 0


async def embed_clauses(clause_ids: list[str], batch_size: int = DEFAULT_BATCH_SIZE) -> int:
    """Idempotently embed the given clauses. Returns count newly embedded.

    Only clauses whose `embedding IS NULL` are encoded (already-embedded rows are
    skipped). Writes `embedding` + `embedding_model` via the bulk-update RPC.
    """
    if not clause_ids:
        return 0

    embedded = 0
    for i in range(0, len(clause_ids), 200):
        chunk = clause_ids[i:i + 200]
        in_list = ",".join(f'"{c}"' for c in chunk)
        r = await supabase_rest_get(
            "disclosure_clause",
            select="clause_id,normalized_text",
            filters=f"clause_id=in.({in_list})&embedding=is.null",
            limit=len(chunk),
        )
        rows = [x for x in (r.json() if r.status_code == 200 else []) if isinstance(x, dict)]
        rows = [x for x in rows if (x.get("normalized_text") or "").strip()]
        if not rows:
            continue

        vecs = embed_texts([x["normalized_text"] for x in rows], batch_size=batch_size)
        embedded += write_clause_embeddings(
            [{"clause_id": x["clause_id"], "embedding": v} for x, v in zip(rows, vecs)]
        )

    return embedded
