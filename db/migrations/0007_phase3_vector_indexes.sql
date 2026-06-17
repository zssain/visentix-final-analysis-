-- Migration 0007: Phase 3 — Vector indexes on disclosure_clause and enforcement_record
-- Applied after embedding backfill (0 NULLs remaining).

-- ivfflat cosine index on disclosure_clause.embedding
CREATE INDEX IF NOT EXISTS idx_disclosure_clause_embedding_ivfflat
    ON disclosure_clause USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 50);

-- ivfflat cosine index on enforcement_record.embedding
CREATE INDEX IF NOT EXISTS idx_enforcement_record_embedding_ivfflat
    ON enforcement_record USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 10);

-- Refresh planner stats
ANALYZE disclosure_clause;
ANALYZE enforcement_record;
