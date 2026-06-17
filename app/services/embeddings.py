"""Embeddings service — vector encoding via all-MiniLM-L6-v2.

Responsibilities (Phase 3):
- Encode disclosure clauses and enforcement records into 384-dim vectors
- Write embeddings to disclosure_clause.embedding and enforcement_record.embedding
- Encode exemplar clauses for similarity search
- All writes go to NEW rows/columns only (never overwrite existing embeddings)
"""


async def embed_clauses(clause_ids: list[str]) -> int:
    """Embed a batch of clauses. Returns count embedded. Implemented in Phase 3."""
    raise NotImplementedError("Embedding service not yet implemented")
