-- 0043_assessment_job.sql
-- Author: engineer (remediation Phase 2) · Feature: QA-011 · Date: 2026-08-04
--
-- CHECKLIST:
--   [x] ADDITIVE ONLY — one new table, no changes to existing tables.
--   [x] IDEMPOTENT — CREATE TABLE/INDEX IF NOT EXISTS.
--   [x] RLS ON — enabled + anon/authenticated revoked (backend service-role only;
--       the /assessments/{id}/status endpoint enforces org ownership in app code).
--   [x] No lineage/score rows here — this is intake job/progress state only.
--
-- QA-011: asynchronous intake. POST /assessments/async creates a row here and
-- returns 202 immediately; the pipeline runs in the background and updates
-- `stage`/`status` so a browser refresh recovers progress from SERVER state
-- (not client memory). `assessment_id` is filled in once the notice is persisted.

CREATE TABLE IF NOT EXISTS public.assessment_job (
    job_id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    -- Client-supplied idempotency key: a double-submit / retry with the same key
    -- returns the SAME job instead of creating a duplicate assessment.
    idempotency_key  text,
    organization_id  uuid,
    -- The persisted privacy_notice.notice_id, once intake reaches persistence.
    assessment_id    uuid,
    status           text NOT NULL DEFAULT 'queued',   -- queued|running|complete|failed
    stage            text NOT NULL DEFAULT 'queued',   -- fine-grained pipeline stage
    error            text,
    result           jsonb,                            -- final response payload (scores, counts)
    created_by       text,                             -- user_id that submitted
    created_at       timestamptz NOT NULL DEFAULT now(),
    updated_at       timestamptz NOT NULL DEFAULT now()
);

-- Dedupe handle for idempotent submits (partial: only non-null keys are unique).
CREATE UNIQUE INDEX IF NOT EXISTS uq_assessment_job_idem
    ON public.assessment_job (idempotency_key)
    WHERE idempotency_key IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_assessment_job_assessment
    ON public.assessment_job (assessment_id);

CREATE INDEX IF NOT EXISTS idx_assessment_job_org_created
    ON public.assessment_job (organization_id, created_at DESC);

-- 🔒 RLS: backend/service-role only (matches migration 0042 posture).
ALTER TABLE public.assessment_job ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.assessment_job FROM anon, authenticated;
