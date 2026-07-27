-- Migration 0032: disclosure_clause exemplar flags (Phase 5 / M-03, F06)
-- ADDITIVE ONLY. Idempotent.
--
-- schema.md §L45 declares disclosure_clause.is_exemplar + exemplar_status
-- (candidate/deidentified/approved), but the live table lacks both — so the F06
-- exemplar pipeline has no column to mark an approved, de-identified exemplar, and
-- M-03 (BenchmarkLanguage reads `disclosure_clause WHERE is_exemplar = true`) is
-- unbuildable. This adds them. Approval is gated on de-identification (F06); nothing
-- is set is_exemplar=true until it passes the de-id checker.

ALTER TABLE disclosure_clause
    ADD COLUMN IF NOT EXISTS is_exemplar     BOOLEAN NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS exemplar_status TEXT;

ALTER TABLE disclosure_clause DROP CONSTRAINT IF EXISTS disclosure_clause_exemplar_status_check;
ALTER TABLE disclosure_clause
    ADD CONSTRAINT disclosure_clause_exemplar_status_check
    CHECK (exemplar_status IS NULL OR exemplar_status IN ('candidate', 'deidentified', 'approved'));

-- Fast lookup for the BenchmarkLanguage query (WHERE is_exemplar = true).
CREATE INDEX IF NOT EXISTS idx_disclosure_clause_is_exemplar
    ON disclosure_clause (is_exemplar) WHERE is_exemplar = true;
