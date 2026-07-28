-- Migration 0035: embedding backfill support + clause_obligation match provenance
-- ADDITIVE ONLY. Idempotent.
--
-- (1) clause_obligation gains `matched_terms` (the keyword overlap that supported
--     the match — lineage/explainability) and `model_version` (the embedding model
--     that produced the similarity). Existing rows: NULL.
-- (2) apply_clause_embeddings(rows): high-throughput, IDEMPOTENT bulk UPDATE of
--     disclosure_clause.embedding + embedding_model from a JSON array. Used by the
--     embedding backfill so 665k rows are written in batches (not one PATCH each).
--     The `embedding IS NULL` guard means an existing embedding is NEVER overwritten.

ALTER TABLE clause_obligation
    ADD COLUMN IF NOT EXISTS matched_terms JSONB,
    ADD COLUMN IF NOT EXISTS model_version TEXT;

CREATE OR REPLACE FUNCTION apply_clause_embeddings(rows JSONB)
RETURNS INTEGER
LANGUAGE plpgsql
AS $$
DECLARE
    n INTEGER;
BEGIN
    UPDATE disclosure_clause dc
    SET embedding = (r->>'embedding')::vector,
        embedding_model = r->>'embedding_model'
    FROM jsonb_array_elements(rows) AS r
    WHERE dc.clause_id = (r->>'clause_id')::uuid
      AND dc.embedding IS NULL;   -- idempotent: never overwrite an existing vector
    GET DIAGNOSTICS n = ROW_COUNT;
    RETURN n;
END;
$$;
