-- Migration 0013: VICBNF v2 clause taxonomy columns
-- ADDITIVE ONLY — new nullable columns. Existing `category` column is preserved
-- and continues to hold the legacy 9-slug value for backward compatibility
-- with all existing scoring code.
--
-- Idempotent: ADD COLUMN IF NOT EXISTS.

ALTER TABLE disclosure_clause
    ADD COLUMN IF NOT EXISTS domain_id           TEXT,   -- CR/DC/SH/RT/AI/SEC/TRK/XB
    ADD COLUMN IF NOT EXISTS clause_type          TEXT,   -- one of the 30 VICBNF clause types
    ADD COLUMN IF NOT EXISTS transparency_score   FLOAT8; -- 0-1 specificity heuristic
