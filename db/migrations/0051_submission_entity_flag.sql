-- 0051_submission_entity_flag.sql
-- Author: engineer · Feature: F01 · Date: 2026-09-03
-- ADDITIVE, idempotent, backend-only. This is a flag and never changes a score.

CREATE TABLE IF NOT EXISTS public.submission_entity_flag (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    assessment_id      uuid NOT NULL REFERENCES public.privacy_notice(notice_id),
    detected_entities  jsonb NOT NULL,
    evidence           jsonb NOT NULL,
    confidence         numeric,
    flagged_at         timestamptz NOT NULL DEFAULT now(),
    UNIQUE (assessment_id)
);

CREATE INDEX IF NOT EXISTS idx_submission_entity_flag_assessment
    ON public.submission_entity_flag (assessment_id, flagged_at DESC);

ALTER TABLE public.submission_entity_flag ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.submission_entity_flag FROM anon, authenticated;

