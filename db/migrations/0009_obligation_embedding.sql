-- Migration 0009: Add embedding column to obligation table (additive only)
-- Idempotent: IF NOT EXISTS on column and index.

ALTER TABLE obligation ADD COLUMN IF NOT EXISTS embedding vector(384);

CREATE INDEX IF NOT EXISTS idx_obligation_embedding_ivfflat
    ON obligation USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 10);
