-- 0044_org_industry_source.sql
-- Author: engineer (remediation Phase 3A) · Feature: ARCH-001A · Date: 2026-08-04
--
-- CHECKLIST:
--   [x] ADDITIVE ONLY — one new NULLABLE column on organization. No changes to
--       existing columns, no DROP/destructive ALTER.
--   [x] IDEMPOTENT — ADD COLUMN IF NOT EXISTS.
--   [x] RLS — no new table; organization RLS is unchanged (already governed).
--
-- ARCH-001A: records WHERE an org's industry came from so scoring/lineage can be
-- honest about it — "user_provided" (declared at intake), "system_default"
-- (derived, e.g. from a URL domain), or "unknown" (opted out). `industry` and
-- `jurisdiction_presence` (jsonb) already exist on organization; only the
-- provenance column is new.

ALTER TABLE public.organization
    ADD COLUMN IF NOT EXISTS industry_source text;
