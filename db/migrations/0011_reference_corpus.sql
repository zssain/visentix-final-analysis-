-- Migration 0011_reference_corpus
-- Creates the three MISSING reference tables and the ingestion_run audit table.
-- Adds missing columns to enforcement_record (172 rows — ALTER only, no DROP).
-- Fully idempotent: IF NOT EXISTS / ON CONFLICT DO NOTHING throughout.
-- DOES NOT modify or delete existing data.

-- ============================================================
-- 1. legal_reference — statutes & regulations we cite
-- ============================================================
CREATE TABLE IF NOT EXISTS legal_reference (
    reference_id    TEXT PRIMARY KEY,
    jurisdiction    TEXT NOT NULL,
    framework       TEXT NOT NULL,
    law_type        TEXT NOT NULL,
    industry_scope  TEXT[] DEFAULT '{all}',
    citation        TEXT NOT NULL,
    title           TEXT NOT NULL,
    summary         TEXT NOT NULL,
    full_text       TEXT,
    domain          TEXT,
    effective_date  DATE,
    official_url    TEXT NOT NULL,
    source_name     TEXT,
    retrieved_at    TIMESTAMPTZ DEFAULT now(),
    last_verified   DATE,
    sme_authored    BOOLEAN DEFAULT false,
    content_hash    TEXT
);

CREATE INDEX IF NOT EXISTS idx_legal_ref_jurisdiction
    ON legal_reference(jurisdiction);
CREATE INDEX IF NOT EXISTS idx_legal_ref_domain
    ON legal_reference(domain);
CREATE INDEX IF NOT EXISTS idx_legal_ref_industry_scope
    ON legal_reference USING GIN (industry_scope);

-- ============================================================
-- 2. finding_legal_reference — join findings → laws
-- ============================================================
CREATE TABLE IF NOT EXISTS finding_legal_reference (
    finding_type_code TEXT NOT NULL REFERENCES finding_type(code),
    reference_id      TEXT NOT NULL REFERENCES legal_reference(reference_id),
    is_primary        BOOLEAN DEFAULT false,
    rationale         TEXT,
    PRIMARY KEY (finding_type_code, reference_id)
);

-- ============================================================
-- 3. explainability_reference — trace scores/findings to sources
-- ============================================================
CREATE TABLE IF NOT EXISTS explainability_reference (
    explainability_id TEXT PRIMARY KEY,
    intelligence_id   TEXT,
    object_type       TEXT,
    source_type       TEXT,
    source_id         TEXT,
    clause_id         TEXT,
    regulator_id      TEXT,
    reference_id      TEXT REFERENCES legal_reference(reference_id),
    rationale         TEXT,
    generated_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_explain_ref_intel
    ON explainability_reference(intelligence_id);
CREATE INDEX IF NOT EXISTS idx_explain_ref_object_type
    ON explainability_reference(object_type);

-- ============================================================
-- 4. ingestion_run — provenance/audit for every data pull
-- ============================================================
CREATE TABLE IF NOT EXISTS ingestion_run (
    run_id        TEXT PRIMARY KEY,
    source_name   TEXT NOT NULL,
    run_type      TEXT,
    started_at    TIMESTAMPTZ DEFAULT now(),
    finished_at   TIMESTAMPTZ,
    rows_inserted INT DEFAULT 0,
    rows_updated  INT DEFAULT 0,
    status        TEXT,
    notes         TEXT
);

-- ============================================================
-- 5. enforcement_record — add missing columns (table exists, 172 rows)
--    Columns already present are no-ops via IF NOT EXISTS.
-- ============================================================
ALTER TABLE enforcement_record ADD COLUMN IF NOT EXISTS jurisdiction      TEXT;
ALTER TABLE enforcement_record ADD COLUMN IF NOT EXISTS regulator_id      TEXT;
ALTER TABLE enforcement_record ADD COLUMN IF NOT EXISTS entity_name       TEXT;
ALTER TABLE enforcement_record ADD COLUMN IF NOT EXISTS entity_industry   TEXT;
ALTER TABLE enforcement_record ADD COLUMN IF NOT EXISTS action_date       DATE;
ALTER TABLE enforcement_record ADD COLUMN IF NOT EXISTS fine_amount_usd   NUMERIC;
ALTER TABLE enforcement_record ADD COLUMN IF NOT EXISTS violation_types   TEXT[];
ALTER TABLE enforcement_record ADD COLUMN IF NOT EXISTS laws_cited        TEXT[];
ALTER TABLE enforcement_record ADD COLUMN IF NOT EXISTS domains          TEXT[];
ALTER TABLE enforcement_record ADD COLUMN IF NOT EXISTS remedies          TEXT;
ALTER TABLE enforcement_record ADD COLUMN IF NOT EXISTS summary           TEXT;
ALTER TABLE enforcement_record ADD COLUMN IF NOT EXISTS official_url      TEXT;
ALTER TABLE enforcement_record ADD COLUMN IF NOT EXISTS source_name       TEXT;
ALTER TABLE enforcement_record ADD COLUMN IF NOT EXISTS retrieved_at      TIMESTAMPTZ;
ALTER TABLE enforcement_record ADD COLUMN IF NOT EXISTS content_hash      TEXT;
ALTER TABLE enforcement_record ADD COLUMN IF NOT EXISTS source_type       TEXT;
ALTER TABLE enforcement_record ADD COLUMN IF NOT EXISTS verified          BOOLEAN DEFAULT false;
