-- Migrations 0009 + 0010: Paste into Supabase Dashboard SQL Editor and Run.
-- All additive, all idempotent (IF NOT EXISTS).

-- 0009: Obligation embedding column
ALTER TABLE obligation ADD COLUMN IF NOT EXISTS embedding vector(384);

CREATE INDEX IF NOT EXISTS idx_obligation_embedding_ivfflat
    ON obligation USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 10);

-- 0010: Category v2 columns for corpus reclassification
ALTER TABLE disclosure_clause ADD COLUMN IF NOT EXISTS category_v2 TEXT;
ALTER TABLE disclosure_clause ADD COLUMN IF NOT EXISTS nlp_confidence_v2 FLOAT8;
ALTER TABLE disclosure_clause ADD COLUMN IF NOT EXISTS classifier_version TEXT;
