-- 0053_peer_distribution.sql
-- Author: engineer · Feature: F-015 (PROPOSED — awaiting expert ratification) · Date: 2026-09-03
-- ADDITIVE, idempotent, backend-only. Stores the reflected weighted peer-density,
-- the individual peer points (the rug), n_eff, the Clopper–Pearson interval, α and
-- the bandwidth against an assessment. LOWERS the confidence of an existing
-- percentile claim (shows spread + uncertainty); it does NOT change any score.
--
-- APPEND-ONLY / VERSIONED. No UNIQUE(assessment_id): re-scoring writes a NEW row
-- (Hard Rule 6 — snapshots immutable, values never overwritten). Readers take the
-- latest generated_at. The authoritative frozen copy also lives in the report
-- snapshot (assembly). Lineage per Hard Rule 4: formula_version_id + generated_at
-- + confidence (VCI). The `proposed` marking travels with the row (OD-23 lesson).

CREATE TABLE IF NOT EXISTS public.peer_distribution (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    assessment_id       uuid NOT NULL REFERENCES public.privacy_notice(notice_id),
    formula_version_id  text NOT NULL DEFAULT 'F-015_v1',
    object_type         text NOT NULL DEFAULT 'peer_distribution',
    proposed            boolean NOT NULL DEFAULT true,
    suppressed          boolean NOT NULL DEFAULT false,
    suppression_reason  text,
    n_eff               numeric,
    n_eff_int           integer,
    cohort_size         integer,
    org_score           numeric,
    percentile          numeric,
    ci_lower            numeric,
    ci_upper            numeric,
    alpha               numeric,
    bandwidth           numeric,
    grid                jsonb,
    density             jsonb,
    peers               jsonb,
    payload             jsonb NOT NULL,
    confidence          numeric,
    generated_at        timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_peer_distribution_assessment
    ON public.peer_distribution (assessment_id, generated_at DESC);

ALTER TABLE public.peer_distribution ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.peer_distribution FROM anon, authenticated;
