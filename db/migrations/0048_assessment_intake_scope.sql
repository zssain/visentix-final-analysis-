-- 0048_assessment_intake_scope.sql
-- Feature: F01 / INT-01..04, INT-10. ADDITIVE and idempotent.
-- User-declared assessment scope is versioned per notice instead of adding
-- mutable fields to protected corpus rows.

CREATE TABLE IF NOT EXISTS public.assessment_intake_scope (
    scope_id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    notice_id             uuid NOT NULL REFERENCES public.privacy_notice(notice_id),
    organization_id       uuid NOT NULL REFERENCES public.organization(organization_id),
    organization_name     text,
    organization_size     text,
    public_private        text,
    geography             text,
    state_footprint       text[],
    selected_laws         text[],
    data_categories       text[],
    business_practices    text[],
    provenance            jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at            timestamptz NOT NULL DEFAULT now(),
    UNIQUE (notice_id)
);

CREATE INDEX IF NOT EXISTS idx_assessment_intake_scope_org
    ON public.assessment_intake_scope (organization_id, created_at DESC);

ALTER TABLE public.assessment_intake_scope ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.assessment_intake_scope FROM anon, authenticated;
