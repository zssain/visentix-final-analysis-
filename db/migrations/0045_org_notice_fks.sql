-- 0045_org_notice_fks.sql
-- Author: engineer (remediation Phase 3) · Feature: DATA-004 · Date: 2026-08-04
--
-- CHECKLIST:
--   [x] ADDITIVE + DATA-SAFE — adds FK constraints as `NOT VALID`, which enforce
--       NEW rows but do NOT scan/validate existing rows, so a legacy orphan can
--       never make this migration fail or destroy data (AGENTS §2). No DROP/
--       TRUNCATE/DELETE, no column rewrite.
--   [x] IDEMPOTENT — each ADD CONSTRAINT is guarded by a pg_constraint existence
--       check in a DO block (Postgres has no ADD CONSTRAINT IF NOT EXISTS).
--   [x] RLS — no new tables; existing table RLS unchanged.
--
-- DATA-004: risk_finding / report_snapshot / organization_intelligence_profile
-- lacked a FOREIGN KEY on organization_id (unlike privacy_notice/derived_data_item),
-- and risk_finding.notice_id was unconstrained — so a finding/report could point at
-- a non-existent org, or none. This adds those FKs.
--
-- Two-step by design (Hard Rule: never endanger existing data):
--   1) THIS migration adds the FKs as NOT VALID → integrity is enforced going
--      forward immediately, with zero risk to legacy rows.
--   2) A LATER step (after an orphan audit — see scripts/db/audit_data004_orphans.sql)
--      runs `VALIDATE CONSTRAINT` + tightens NOT NULL on scored rows. That step is
--      deliberately NOT here because it must follow a live-data audit + repair.

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'risk_finding_organization_id_fkey') THEN
    ALTER TABLE public.risk_finding
      ADD CONSTRAINT risk_finding_organization_id_fkey
      FOREIGN KEY (organization_id) REFERENCES public.organization(organization_id) NOT VALID;
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'risk_finding_notice_id_fkey') THEN
    ALTER TABLE public.risk_finding
      ADD CONSTRAINT risk_finding_notice_id_fkey
      FOREIGN KEY (notice_id) REFERENCES public.privacy_notice(notice_id) NOT VALID;
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'report_snapshot_organization_id_fkey') THEN
    ALTER TABLE public.report_snapshot
      ADD CONSTRAINT report_snapshot_organization_id_fkey
      FOREIGN KEY (organization_id) REFERENCES public.organization(organization_id) NOT VALID;
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'organization_intelligence_profile_organization_id_fkey') THEN
    ALTER TABLE public.organization_intelligence_profile
      ADD CONSTRAINT organization_intelligence_profile_organization_id_fkey
      FOREIGN KEY (organization_id) REFERENCES public.organization(organization_id) NOT VALID;
  END IF;
END $$;
