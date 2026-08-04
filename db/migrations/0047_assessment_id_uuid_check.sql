-- 0047_assessment_id_uuid_check.sql
-- Author: engineer (remediation Phase 4) · Feature: DB-002 · Date: 2026-08-04
--
-- CHECKLIST:
--   [x] ADDITIVE + DATA-SAFE — adds CHECK constraints as `NOT VALID` (enforce new
--       rows are UUID-shaped; do NOT scan/fail on legacy rows). No type change, no
--       DROP, no rewrite. A `text`→`uuid` type change IS destructive (AGENTS §2)
--       and is therefore NOT done here — see the staged plan below.
--   [x] IDEMPOTENT — pg_constraint existence guard per constraint.
--
-- DB-002: `assessment_id` is `text` (unconstrained) in five places, vs `uuid`+FK
-- elsewhere. Full remediation (convert to uuid + FK → privacy_notice(notice_id))
-- is a destructive, staged migration that must run against a data-audited live DB.
-- This migration is the SAFE first step: it constrains NEW rows to a UUID shape so
-- the drift stops growing, without touching legacy data or column types.
--
-- STAGED FULL FIX (external, after a live audit — do NOT run blind):
--   1) audit: SELECT assessment_id FROM <t> WHERE assessment_id !~ '<uuid-regex>';
--   2) repair/quarantine any non-uuid legacy rows (never destroy);
--   3) VALIDATE CONSTRAINT <t>_assessment_id_is_uuid;  (proves all rows conform)
--   4) ALTER COLUMN assessment_id TYPE uuid USING assessment_id::uuid;  (destructive
--      — owner-approved, on a backed-up DB, in a maintenance window)
--   5) ADD FOREIGN KEY (assessment_id) REFERENCES privacy_notice(notice_id) NOT VALID → VALIDATE.
--   Also update the approve_and_freeze(p_assessment_id text) RPC signature to uuid.

DO $$
DECLARE
  uuid_re CONSTANT text := '^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$';
  t text;
BEGIN
  FOREACH t IN ARRAY ARRAY['assessment_review','report_snapshot','review_queue_item','training_label']
  LOOP
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = t || '_assessment_id_is_uuid') THEN
      EXECUTE format(
        'ALTER TABLE public.%I ADD CONSTRAINT %I CHECK (assessment_id IS NULL OR assessment_id ~ %L) NOT VALID',
        t, t || '_assessment_id_is_uuid', uuid_re
      );
    END IF;
  END LOOP;
END $$;
