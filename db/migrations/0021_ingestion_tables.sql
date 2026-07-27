-- Migration 0021: Ingestion, connector & external-signal layer (schema.md v1.3 §2.9)
-- ADDITIVE ONLY. Idempotent (CREATE TABLE / ADD COLUMN / CREATE INDEX IF NOT EXISTS).
--
-- Four new tables (source_registry, parser_version, security_event,
-- organization_alias) + additive columns on the existing ingestion_run
-- table (migration 0011c). No existing table or column is altered or dropped.
--
-- FK type notes (verified against live via PostgREST reflection, 2026-07-20):
--   source_record.source_id      is TEXT  -> *_record_id FKs are TEXT
--   organization.organization_id is UUID  -> organization_id FKs are UUID
--
-- RLS: all five tables (the four new + ingestion_run) are server-side only.
--   service_role bypasses RLS; anon/authenticated are denied entirely
--   (RLS enabled with no permissive policy + REVOKE). Never exposed to the
--   browser client (AGENTS.md §3).

-- ============================================================
-- 1. source_registry — configurable list of source families
-- ============================================================
CREATE TABLE IF NOT EXISTS source_registry (
    registry_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    family           TEXT NOT NULL
                        CHECK (family IN ('sec_edgar','hhs_ocr','ftc','cppa',
                                          'state_ag','princeton_leuven','open_web')),
    display_name     TEXT NOT NULL,
    base_url         TEXT,
    cadence          TEXT CHECK (cadence IN ('manual','daily','weekly','monthly')),
    reliability_tier INTEGER CHECK (reliability_tier BETWEEN 1 AND 3),
    parser_type      TEXT,
    enabled          BOOLEAN NOT NULL DEFAULT false,
    config           JSONB,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT source_registry_family_key UNIQUE (family)   -- one row per family (seed upserts on family)
);

-- ============================================================
-- 2. parser_version — versioned parser registry (lineage §4)
-- ============================================================
CREATE TABLE IF NOT EXISTS parser_version (
    parser_version_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    family            TEXT NOT NULL,
    version           TEXT NOT NULL,
    description       TEXT,
    effective_from    TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT parser_version_family_version_key UNIQUE (family, version)
);

-- ============================================================
-- 3. security_event — breach / security-incident signals
--    RATIONALE (OD-06): these are org-risk signals, NOT enforcement
--    actions. They must NEVER populate enforcement_record or feed F-004
--    without a separate, expert-approved formula change.
-- ============================================================
CREATE TABLE IF NOT EXISTS security_event (
    event_id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_record_id     TEXT REFERENCES source_record(source_id),
    organization_id      UUID REFERENCES organization(organization_id),   -- nullable: unresolved entities
    entity_name_raw      TEXT,
    entity_type          TEXT,
    state                TEXT,
    breach_date          DATE,
    submission_date      DATE,
    individuals_affected INTEGER,
    breach_type          TEXT,
    information_location  TEXT,
    description          TEXT,
    source_url           TEXT,
    capture_date         TIMESTAMPTZ NOT NULL DEFAULT now(),
    extraction_confidence REAL,
    resolution_status    TEXT NOT NULL DEFAULT 'unresolved'
                            CHECK (resolution_status IN ('unresolved','resolved'))
);

-- ============================================================
-- 4. organization_alias — identifier/alias resolution
-- ============================================================
CREATE TABLE IF NOT EXISTS organization_alias (
    alias_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id  UUID NOT NULL REFERENCES organization(organization_id),
    alias_type       TEXT NOT NULL
                        CHECK (alias_type IN ('cik','ticker','domain','legal_name','dba')),
    value            TEXT NOT NULL,
    match_confidence REAL,
    source_record_id TEXT REFERENCES source_record(source_id),   -- nullable
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT organization_alias_type_value_key UNIQUE (alias_type, value)
);

-- ============================================================
-- 5. ingestion_run — ADDITIVE columns on the existing 0011c table
--    Mapping to existing columns (retained, not dropped):
--      rows_inserted ≈ records_new   ·   status ≈ outcome
--      source_name retained alongside the new registry_id FK
-- ============================================================
ALTER TABLE ingestion_run
    ADD COLUMN IF NOT EXISTS registry_id       UUID REFERENCES source_registry(registry_id),
    ADD COLUMN IF NOT EXISTS outcome           TEXT CHECK (outcome IN ('ok','partial','failed')),
    ADD COLUMN IF NOT EXISTS records_seen      INTEGER,
    ADD COLUMN IF NOT EXISTS records_new       INTEGER,
    ADD COLUMN IF NOT EXISTS records_changed   INTEGER,
    ADD COLUMN IF NOT EXISTS records_skipped   INTEGER,
    ADD COLUMN IF NOT EXISTS error_summary     TEXT,
    ADD COLUMN IF NOT EXISTS parser_version_id UUID REFERENCES parser_version(parser_version_id);

-- ============================================================
-- 6. Indexes (FK lookups)
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_parser_version_family        ON parser_version(family);
CREATE INDEX IF NOT EXISTS idx_security_event_source_record ON security_event(source_record_id);
CREATE INDEX IF NOT EXISTS idx_security_event_organization  ON security_event(organization_id);
CREATE INDEX IF NOT EXISTS idx_security_event_resolution    ON security_event(resolution_status);
CREATE INDEX IF NOT EXISTS idx_org_alias_organization       ON organization_alias(organization_id);
CREATE INDEX IF NOT EXISTS idx_ingestion_run_registry       ON ingestion_run(registry_id);

-- ============================================================
-- 7. RLS — server-side (service_role) only; anon/authenticated denied
-- ============================================================
ALTER TABLE source_registry    ENABLE ROW LEVEL SECURITY;
ALTER TABLE parser_version     ENABLE ROW LEVEL SECURITY;
ALTER TABLE security_event     ENABLE ROW LEVEL SECURITY;
ALTER TABLE organization_alias ENABLE ROW LEVEL SECURITY;
ALTER TABLE ingestion_run      ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON source_registry    FROM anon, authenticated;
REVOKE ALL ON parser_version     FROM anon, authenticated;
REVOKE ALL ON security_event     FROM anon, authenticated;
REVOKE ALL ON organization_alias FROM anon, authenticated;
REVOKE ALL ON ingestion_run      FROM anon, authenticated;
