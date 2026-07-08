-- Migration 0014: Org profile + organization enrichment columns
-- ADDITIVE ONLY — new nullable columns via ADD COLUMN IF NOT EXISTS.
-- Supports the VICBNF v2 7-dimension profiling with tier labels.

-- ============================================================
-- organization — enrichment metadata for profiling
-- ============================================================
ALTER TABLE organization
    ADD COLUMN IF NOT EXISTS industry_id            TEXT,     -- IND-01..IND-10
    ADD COLUMN IF NOT EXISTS sub_industry            TEXT,
    ADD COLUMN IF NOT EXISTS public_company_flag     BOOLEAN,
    ADD COLUMN IF NOT EXISTS size_metadata           JSONB,   -- {employee_count, revenue_band, ...}
    ADD COLUMN IF NOT EXISTS revenue_metadata        JSONB,
    ADD COLUMN IF NOT EXISTS jurisdiction_presence    JSONB;   -- ["US-CA","US-NY",...]

-- ============================================================
-- organization_intelligence_profile — tier + IC enrichment
-- ============================================================
ALTER TABLE organization_intelligence_profile
    ADD COLUMN IF NOT EXISTS industry_id    TEXT,
    ADD COLUMN IF NOT EXISTS sub_industry   TEXT,
    ADD COLUMN IF NOT EXISTS rss_tier       TEXT,
    ADD COLUMN IF NOT EXISTS pgms_tier      TEXT,
    ADD COLUMN IF NOT EXISTS osi_tier       TEXT,
    ADD COLUMN IF NOT EXISTS dsi_tier       TEXT,
    ADD COLUMN IF NOT EXISTS ehp_tier       TEXT,
    ADD COLUMN IF NOT EXISTS aigms_tier     TEXT;
