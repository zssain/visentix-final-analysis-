-- Migration 0019: Add versioning columns required by live_scoring.py.
-- ADDITIVE ONLY. Idempotent.

ALTER TABLE derived_data_item ADD COLUMN IF NOT EXISTS scoring_model_version TEXT;
ALTER TABLE derived_data_item ADD COLUMN IF NOT EXISTS source_corpus_version TEXT;
ALTER TABLE derived_data_item ADD COLUMN IF NOT EXISTS benchmark_population_version TEXT;

ALTER TABLE risk_finding ADD COLUMN IF NOT EXISTS scoring_model_version TEXT;
ALTER TABLE risk_finding ADD COLUMN IF NOT EXISTS source_corpus_version TEXT;
