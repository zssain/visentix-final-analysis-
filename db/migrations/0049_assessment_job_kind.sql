-- 0049_assessment_job_kind.sql
-- Author: engineer · Feature: F01/F09/F21 (background tasks) · Date: 2026-08-31
--
-- ADDITIVE ONLY: one new NULLABLE-with-default column, one index. No DROP, no
-- destructive ALTER, no data rewritten. Re-running changes nothing.
--
-- WHY
-- `assessment_job` was intake-shaped, so every other long operation either grew
-- its own job concept or blocked the HTTP request. Two still block:
-- /admin/trigger-assessment re-scores every notice in an organization inline,
-- and the quarterly build does the same.
--
-- `kind` generalizes the table to any user-triggered task. `assessment_id` is
-- already NULLABLE, so a non-intake task simply leaves it null and reports its
-- own result through `result`.
--
-- The DEFAULT is 'intake' precisely so existing rows keep their meaning without
-- a backfill: every row written before this migration WAS an intake job.
--
-- `job_run` (scheduled cron work) is deliberately NOT merged in. Cron jobs have
-- no user waiting on them; giving one a progress bar nobody is watching would
-- make the tracker lie about what it is for.

ALTER TABLE public.assessment_job
    ADD COLUMN IF NOT EXISTS kind text NOT NULL DEFAULT 'intake';

COMMENT ON COLUMN public.assessment_job.kind IS
    'Task kind: intake | reassessment | quarterly_build | report_pdf. '
    'Default ''intake'' preserves the meaning of every pre-0049 row without a backfill.';

-- The tracker asks "what is still running for me", which is a scan by
-- (kind, status) far more often than by job_id.
CREATE INDEX IF NOT EXISTS ix_assessment_job_kind_status
    ON public.assessment_job (kind, status, created_at DESC);
