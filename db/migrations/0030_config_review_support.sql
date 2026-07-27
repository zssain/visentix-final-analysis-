-- Migration 0030: config-review support for the expert-gated crosswalks (Phase 1)
-- ADDITIVE ONLY. Idempotent.
--
-- The interim AI reviewer approves internal data-preparation gates but must NEVER
-- impersonate the human SME. The existing mapped_by CHECK on both crosswalk tables
-- allowed only 'draft'/'approved' (and 'unmapped' on the FTC map) — so an AI review
-- had no honest state to record: 'approved' is the human SME gate. This migration
-- adds a distinct 'ai_reviewed' state (AI-reviewed, pending human SME re-review) and
-- reviewer/timestamp columns so every AI approval carries attribution + a timestamp.
--
-- Also constrains ftc_topic_domain_map.domain to the eight canonical Visentix
-- disclosure-domain codes (intelligence-logic.md §4) or NULL.

-- ── sic_industry_map ────────────────────────────────────────────────
ALTER TABLE sic_industry_map DROP CONSTRAINT IF EXISTS sic_industry_map_mapped_by_check;
ALTER TABLE sic_industry_map DROP CONSTRAINT IF EXISTS sic_industry_map_mapped_by_check2;
ALTER TABLE sic_industry_map
    ADD CONSTRAINT sic_industry_map_mapped_by_check2
    CHECK (mapped_by IN ('draft', 'ai_reviewed', 'approved'));
ALTER TABLE sic_industry_map ADD COLUMN IF NOT EXISTS reviewed_by TEXT;
ALTER TABLE sic_industry_map ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMPTZ;

-- ── ftc_topic_domain_map ────────────────────────────────────────────
ALTER TABLE ftc_topic_domain_map DROP CONSTRAINT IF EXISTS ftc_topic_domain_map_mapped_by_check;
ALTER TABLE ftc_topic_domain_map DROP CONSTRAINT IF EXISTS ftc_topic_domain_map_mapped_by_check2;
ALTER TABLE ftc_topic_domain_map
    ADD CONSTRAINT ftc_topic_domain_map_mapped_by_check2
    CHECK (mapped_by IN ('unmapped', 'draft', 'ai_reviewed', 'approved'));
ALTER TABLE ftc_topic_domain_map DROP CONSTRAINT IF EXISTS ftc_topic_domain_map_domain_check;
ALTER TABLE ftc_topic_domain_map
    ADD CONSTRAINT ftc_topic_domain_map_domain_check
    CHECK (domain IS NULL OR domain IN ('CR','DC','SH','RT','AI','SEC','TRK','XB'));
ALTER TABLE ftc_topic_domain_map ADD COLUMN IF NOT EXISTS reviewed_by TEXT;
ALTER TABLE ftc_topic_domain_map ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMPTZ;
