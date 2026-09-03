-- 0052_f23_internal_demo_workspace.sql
-- Author: engineer · Feature: F23 · Date: 2026-09-03
-- ADDITIVE ONLY: one new mapping table, nullable columns, and indexes. Existing
-- rows are not backfilled or rewritten.

CREATE TABLE IF NOT EXISTS public.workspace_target (
    workspace_target_id       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_organization_id uuid NOT NULL REFERENCES public.organization(organization_id),
    target_organization_id    uuid NOT NULL REFERENCES public.organization(organization_id),
    normalized_domain         text NOT NULL,
    registered_by             uuid NOT NULL REFERENCES auth.users(id),
    created_at                timestamptz NOT NULL DEFAULT now(),
    UNIQUE (workspace_organization_id, normalized_domain),
    UNIQUE (workspace_organization_id, target_organization_id)
);

CREATE INDEX IF NOT EXISTS idx_workspace_target_workspace_created
    ON public.workspace_target (workspace_organization_id, created_at DESC);

ALTER TABLE public.workspace_target ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.workspace_target FROM anon, authenticated;

ALTER TABLE public.profiles
    ADD COLUMN IF NOT EXISTS third_party_assessment_enabled boolean;

ALTER TABLE public.privacy_notice
    ADD COLUMN IF NOT EXISTS workspace_organization_id uuid REFERENCES public.organization(organization_id);
ALTER TABLE public.risk_finding
    ADD COLUMN IF NOT EXISTS workspace_organization_id uuid REFERENCES public.organization(organization_id);
ALTER TABLE public.derived_data_item
    ADD COLUMN IF NOT EXISTS workspace_organization_id uuid REFERENCES public.organization(organization_id);
ALTER TABLE public.report_snapshot
    ADD COLUMN IF NOT EXISTS workspace_organization_id uuid REFERENCES public.organization(organization_id);
ALTER TABLE public.assessment_job
    ADD COLUMN IF NOT EXISTS workspace_organization_id uuid REFERENCES public.organization(organization_id);
ALTER TABLE public.assessment_intake_scope
    ADD COLUMN IF NOT EXISTS workspace_organization_id uuid REFERENCES public.organization(organization_id);

CREATE INDEX IF NOT EXISTS idx_privacy_notice_workspace_created
    ON public.privacy_notice (workspace_organization_id, retrieval_date DESC);
CREATE INDEX IF NOT EXISTS idx_risk_finding_workspace_notice
    ON public.risk_finding (workspace_organization_id, notice_id);
CREATE INDEX IF NOT EXISTS idx_derived_data_item_workspace_generated
    ON public.derived_data_item (workspace_organization_id, generated_at DESC);
CREATE INDEX IF NOT EXISTS idx_report_snapshot_workspace_created
    ON public.report_snapshot (workspace_organization_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_assessment_job_workspace_created
    ON public.assessment_job (workspace_organization_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_assessment_intake_scope_workspace_created
    ON public.assessment_intake_scope (workspace_organization_id, created_at DESC);

