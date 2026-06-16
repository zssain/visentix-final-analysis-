-- ================================================================
-- PHASE 1: ALL MIGRATIONS — Paste this entire block into the
-- Supabase Dashboard SQL Editor and click "Run".
-- Everything is idempotent (IF NOT EXISTS / ON CONFLICT DO NOTHING).
-- ================================================================

-- ==== Migration 0001: New tables ====

CREATE TABLE IF NOT EXISTS finding_type (
    code                     TEXT PRIMARY KEY,
    title                    TEXT NOT NULL,
    default_severity         TEXT NOT NULL DEFAULT 'medium',
    domain                   TEXT NOT NULL,
    regulator_relevance      JSONB,
    linked_recommendation_id TEXT,
    sme_authored             BOOLEAN NOT NULL DEFAULT false
);

CREATE TABLE IF NOT EXISTS recommendation_library (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    finding_type_code TEXT NOT NULL REFERENCES finding_type(code),
    severity_bucket   TEXT NOT NULL,
    title             TEXT NOT NULL,
    body_template     TEXT NOT NULL,
    source_note       TEXT,
    sme_authored      BOOLEAN NOT NULL DEFAULT false,
    version           INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_recommendation_library_finding_type
    ON recommendation_library(finding_type_code);

CREATE TABLE IF NOT EXISTS exemplar (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    domain              TEXT NOT NULL,
    category            TEXT NOT NULL,
    clause_text         TEXT NOT NULL,
    maturity_note       TEXT,
    source_internal_ref TEXT,
    embedding           vector(384),
    sme_cleaned         BOOLEAN NOT NULL DEFAULT false
);

CREATE INDEX IF NOT EXISTS idx_exemplar_domain_category
    ON exemplar(domain, category);

CREATE INDEX IF NOT EXISTS idx_exemplar_embedding_ivfflat
    ON exemplar USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 10);

CREATE TABLE IF NOT EXISTS organization_intelligence_profile (
    profile_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id  UUID NOT NULL,
    ic               FLOAT8,
    rss              FLOAT8,
    pgms             FLOAT8,
    osi              FLOAT8,
    dsi              FLOAT8,
    ehp              FLOAT8,
    aigms            FLOAT8,
    profile_version  INTEGER NOT NULL DEFAULT 1,
    confidence_score FLOAT8,
    generated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_oip_organization
    ON organization_intelligence_profile(organization_id);

CREATE TABLE IF NOT EXISTS report_snapshot (
    snapshot_id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id              UUID NOT NULL,
    notice_id                    UUID,
    payload                      JSONB NOT NULL,
    formula_version_set          JSONB NOT NULL,
    benchmark_population_version INTEGER,
    source_corpus_version        INTEGER,
    created_at                   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_report_snapshot_org
    ON report_snapshot(organization_id);

-- ==== Migration 0002: Add columns to existing tables ====

ALTER TABLE risk_finding ADD COLUMN IF NOT EXISTS organization_id    UUID;
ALTER TABLE risk_finding ADD COLUMN IF NOT EXISTS notice_id          UUID;
ALTER TABLE risk_finding ADD COLUMN IF NOT EXISTS finding_type_code  TEXT;
ALTER TABLE risk_finding ADD COLUMN IF NOT EXISTS snapshot_id        UUID;
ALTER TABLE risk_finding ADD COLUMN IF NOT EXISTS generated_at       TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_risk_finding_org
    ON risk_finding(organization_id);
CREATE INDEX IF NOT EXISTS idx_risk_finding_finding_type
    ON risk_finding(finding_type_code);

ALTER TABLE clause_obligation ADD COLUMN IF NOT EXISTS match_method TEXT;
ALTER TABLE clause_obligation ADD COLUMN IF NOT EXISTS similarity   FLOAT8;

ALTER TABLE benchmark_membership ADD COLUMN IF NOT EXISTS normalization_score  FLOAT8;
ALTER TABLE benchmark_membership ADD COLUMN IF NOT EXISTS benchmark_weight     FLOAT8;
ALTER TABLE benchmark_membership ADD COLUMN IF NOT EXISTS inclusion_reason     TEXT;
ALTER TABLE benchmark_membership ADD COLUMN IF NOT EXISTS population_version   INTEGER;

ALTER TABLE derived_data_item ADD COLUMN IF NOT EXISTS score            FLOAT8;
ALTER TABLE derived_data_item ADD COLUMN IF NOT EXISTS confidence_index FLOAT8;
ALTER TABLE derived_data_item ADD COLUMN IF NOT EXISTS source_lineage   JSONB;

-- ==== Migration 0003: Seed stub rows ====

INSERT INTO finding_type (code, title, default_severity, domain, regulator_relevance, sme_authored)
VALUES
    ('AI-004',  'STUB — AI Transparency Gap',           'high',     'ai_automated_decisions',
     '{"FTC": 0.8, "CPPA": 0.7}'::jsonb, false),
    ('TRK-007', 'STUB — Tracking Disclosure Weakness',  'medium',   'tracking_cookies',
     '{"FTC": 0.7, "CPPA": 0.6}'::jsonb, false),
    ('SH-002',  'STUB — Data Sharing Exposure',         'high',     'data_sharing',
     '{"FTC": 0.9, "AG-CA": 0.8}'::jsonb, false),
    ('RT-003',  'STUB — Retention Period Omission',     'medium',   'retention',
     '{"FTC": 0.6, "CPPA": 0.7}'::jsonb, false),
    ('CR-001',  'STUB — Consumer Rights Gap',           'high',     'consumer_rights',
     '{"CPPA": 0.9, "AG-CA": 0.8}'::jsonb, false),
    ('DC-005',  'STUB — Disclosure Completeness Issue', 'medium',   'other',
     '{"FTC": 0.5}'::jsonb, false),
    ('SEC-002', 'STUB — Sensitive Data Handling Risk',  'high',     'sensitive_data',
     '{"FTC": 0.8, "HHS": 0.7}'::jsonb, false),
    ('XB-001',  'STUB — Cross-Border Transfer Gap',    'medium',   'cross_border',
     '{"FTC": 0.6, "EDPB": 0.9}'::jsonb, false)
ON CONFLICT (code) DO NOTHING;

INSERT INTO recommendation_library
    (finding_type_code, severity_bucket, title, body_template, source_note, sme_authored)
VALUES
    ('AI-004',  'high',   'STUB — Strengthen AI Transparency Disclosure',
     'Consider disclosing {ai_use_cases} and the logic involved in automated decision-making. STUB — replace with SME content.',
     'STUB — replace with SME content', false),
    ('TRK-007', 'medium', 'STUB — Enhance Tracking Technology Disclosure',
     'Consider specifying {tracking_technologies} used and their purposes. STUB — replace with SME content.',
     'STUB — replace with SME content', false),
    ('SH-002',  'high',   'STUB — Clarify Data Sharing Practices',
     'Consider enumerating {third_party_categories} and sharing purposes. STUB — replace with SME content.',
     'STUB — replace with SME content', false),
    ('RT-003',  'medium', 'STUB — Define Retention Periods',
     'Consider specifying retention periods for {data_categories}. STUB — replace with SME content.',
     'STUB — replace with SME content', false),
    ('CR-001',  'high',   'STUB — Expand Consumer Rights Section',
     'Consider detailing the process for exercising {consumer_rights}. STUB — replace with SME content.',
     'STUB — replace with SME content', false),
    ('DC-005',  'medium', 'STUB — Improve Disclosure Completeness',
     'Consider addressing {missing_elements} in the privacy notice. STUB — replace with SME content.',
     'STUB — replace with SME content', false),
    ('SEC-002', 'high',   'STUB — Sensitive Data Safeguards',
     'Consider disclosing safeguards for {sensitive_data_types}. STUB — replace with SME content.',
     'STUB — replace with SME content', false),
    ('XB-001',  'medium', 'STUB — Cross-Border Transfer Mechanisms',
     'Consider disclosing transfer mechanisms for {destination_countries}. STUB — replace with SME content.',
     'STUB — replace with SME content', false);

INSERT INTO exemplar
    (domain, category, clause_text, maturity_note, source_internal_ref, sme_cleaned)
VALUES
    ('data_sharing', 'data_sharing',
     'STUB — [Company] may share your personal information with third-party service providers who assist us in operating our platform. STUB — replace with SME content.',
     'STUB maturity note: moderate — names categories but not specific entities.',
     'STUB-EXEMPLAR-001', false),
    ('ai_automated_decisions', 'ai_automated_decisions',
     'STUB — We use automated systems to personalize your experience. You may request human review of decisions. STUB — replace with SME content.',
     'STUB maturity note: high — discloses use and opt-out mechanism.',
     'STUB-EXEMPLAR-002', false),
    ('retention', 'retention',
     'STUB — We retain your data for as long as necessary to fulfill the purposes described in this notice. STUB — replace with SME content.',
     'STUB maturity note: low — no specific periods given.',
     'STUB-EXEMPLAR-003', false);
