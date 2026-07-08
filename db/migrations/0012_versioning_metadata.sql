-- Migration 0012: Versioning metadata foundation
-- ADDITIVE ONLY — new nullable columns on existing tables.
-- Implements the VICBNF v2 "versioning quintet" requirement:
--   Every derived value must carry scoring_model_version,
--   source_corpus_version, and benchmark_population_version
--   alongside the existing formula_version_id and generated_at.
--
-- Idempotent: ADD COLUMN IF NOT EXISTS.

-- ============================================================
-- derived_data_item — the core score/value store
-- ============================================================
ALTER TABLE derived_data_item
    ADD COLUMN IF NOT EXISTS scoring_model_version       TEXT,
    ADD COLUMN IF NOT EXISTS source_corpus_version        TEXT,
    ADD COLUMN IF NOT EXISTS benchmark_population_version TEXT;

-- ============================================================
-- risk_finding — findings also need model + corpus version
-- ============================================================
ALTER TABLE risk_finding
    ADD COLUMN IF NOT EXISTS scoring_model_version TEXT,
    ADD COLUMN IF NOT EXISTS source_corpus_version  TEXT;
