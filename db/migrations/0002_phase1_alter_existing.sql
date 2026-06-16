-- Migration 0002: Phase 1 — Add missing columns to existing tables (additive only)
-- Applied: 2026-06-16
-- All ALTER TABLE uses ADD COLUMN IF NOT EXISTS for idempotency.
-- No existing rows or columns are modified.

-- 1. risk_finding — add columns needed by the scoring engine
ALTER TABLE risk_finding ADD COLUMN IF NOT EXISTS organization_id    UUID;
ALTER TABLE risk_finding ADD COLUMN IF NOT EXISTS notice_id          UUID;
ALTER TABLE risk_finding ADD COLUMN IF NOT EXISTS finding_type_code  TEXT;
ALTER TABLE risk_finding ADD COLUMN IF NOT EXISTS snapshot_id        UUID;
ALTER TABLE risk_finding ADD COLUMN IF NOT EXISTS generated_at       TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_risk_finding_org
    ON risk_finding(organization_id);
CREATE INDEX IF NOT EXISTS idx_risk_finding_finding_type
    ON risk_finding(finding_type_code);

-- 2. clause_obligation — add match metadata columns
ALTER TABLE clause_obligation ADD COLUMN IF NOT EXISTS match_method TEXT;
ALTER TABLE clause_obligation ADD COLUMN IF NOT EXISTS similarity   FLOAT8;

-- 3. benchmark_membership — add normalization columns (30 existing rows get NULLs)
ALTER TABLE benchmark_membership ADD COLUMN IF NOT EXISTS normalization_score  FLOAT8;
ALTER TABLE benchmark_membership ADD COLUMN IF NOT EXISTS benchmark_weight     FLOAT8;
ALTER TABLE benchmark_membership ADD COLUMN IF NOT EXISTS inclusion_reason     TEXT;
ALTER TABLE benchmark_membership ADD COLUMN IF NOT EXISTS population_version   INTEGER;

-- 4. derived_data_item — add missing scoring columns
ALTER TABLE derived_data_item ADD COLUMN IF NOT EXISTS score            FLOAT8;
ALTER TABLE derived_data_item ADD COLUMN IF NOT EXISTS confidence_index FLOAT8;
ALTER TABLE derived_data_item ADD COLUMN IF NOT EXISTS source_lineage   JSONB;
