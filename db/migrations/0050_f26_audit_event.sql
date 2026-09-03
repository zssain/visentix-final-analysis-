-- 0050_f26_audit_event.sql
-- Author: engineer · Feature: F26 · Date: 2026-09-03
-- ADDITIVE, idempotent, backend-only. Stores request metadata only: never a
-- request body, query string, credential, token, notice text, or raw URL.

CREATE TABLE IF NOT EXISTS public.audit_event (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id  uuid NOT NULL REFERENCES public.organization(organization_id),
    user_id           uuid NOT NULL REFERENCES auth.users(id),
    action            text NOT NULL,
    resource_type     text NOT NULL,
    resource_id       text,
    at                timestamptz NOT NULL DEFAULT now(),
    request_id        uuid NOT NULL,
    expires_at        timestamptz NOT NULL DEFAULT (now() + interval '12 months')
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_audit_event_request
    ON public.audit_event (request_id);

CREATE INDEX IF NOT EXISTS idx_audit_event_org_user_at
    ON public.audit_event (organization_id, user_id, at DESC);

ALTER TABLE public.audit_event ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.audit_event FROM anon, authenticated;

