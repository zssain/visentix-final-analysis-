-- Migration 0001: Phase 1 — New tables (additive only)
-- Applied: 2026-06-16
-- All CREATE TABLE uses IF NOT EXISTS for idempotency.

-- 1. finding_type — fixed catalog of finding codes
CREATE TABLE IF NOT EXISTS finding_type (
    code                     TEXT PRIMARY KEY,
    title                    TEXT NOT NULL,
    default_severity         TEXT NOT NULL DEFAULT 'medium',
    domain                   TEXT NOT NULL,
    regulator_relevance      JSONB,
    linked_recommendation_id TEXT,
    sme_authored             BOOLEAN NOT NULL DEFAULT false
);

-- 2. recommendation_library — authored remediation templates
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

-- 3. exemplar — de-identified best/worst practice clause examples
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

-- ivfflat index for vector similarity search (will be used in Phase 3+)
-- Note: ivfflat requires at least some rows to build lists; with few rows
-- this index is safe to create but only becomes useful at scale.
CREATE INDEX IF NOT EXISTS idx_exemplar_embedding_ivfflat
    ON exemplar USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 10);

-- 4. organization_intelligence_profile — 7-score org profile (populated Phase 4)
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

-- 5. report_snapshot — frozen report payloads for reproducibility
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
