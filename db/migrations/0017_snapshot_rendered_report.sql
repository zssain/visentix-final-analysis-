-- Migration 0017: Immutable rendered report in snapshot (VICBNF-008)
-- The report_snapshot becomes the single source of truth for report content.
-- GET /reports/{id} returns stored content verbatim — deterministic.
-- ADDITIVE ONLY.

ALTER TABLE report_snapshot
    ADD COLUMN IF NOT EXISTS rendered_report         JSONB,   -- full assembled report payload
    ADD COLUMN IF NOT EXISTS content_hash             TEXT,    -- SHA-256 of rendered_report JSON
    ADD COLUMN IF NOT EXISTS report_version           INTEGER DEFAULT 1,
    ADD COLUMN IF NOT EXISTS scoring_model_version    TEXT,
    ADD COLUMN IF NOT EXISTS glossary_version         TEXT,
    ADD COLUMN IF NOT EXISTS template_version         TEXT;
