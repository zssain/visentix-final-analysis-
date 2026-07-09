-- Migration 0018: Add columns required by the intake pipeline.
-- ADDITIVE ONLY. Idempotent.

-- privacy_notice: extraction confidence from NLP classification
ALTER TABLE privacy_notice ADD COLUMN IF NOT EXISTS extraction_confidence FLOAT DEFAULT 0;

-- disclosure_clause: v2 taxonomy fields used by live scoring
ALTER TABLE disclosure_clause ADD COLUMN IF NOT EXISTS domain_id TEXT;
ALTER TABLE disclosure_clause ADD COLUMN IF NOT EXISTS transparency_score FLOAT DEFAULT 0;
ALTER TABLE disclosure_clause ADD COLUMN IF NOT EXISTS specificity_score FLOAT DEFAULT 0;
