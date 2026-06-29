-- Migration 0010: Additive columns for v2 classification (NEVER overwrites original)
-- Only used for reclassifying category='other' corpus clauses.

ALTER TABLE disclosure_clause ADD COLUMN IF NOT EXISTS category_v2 TEXT;
ALTER TABLE disclosure_clause ADD COLUMN IF NOT EXISTS nlp_confidence_v2 FLOAT8;
ALTER TABLE disclosure_clause ADD COLUMN IF NOT EXISTS classifier_version TEXT;
