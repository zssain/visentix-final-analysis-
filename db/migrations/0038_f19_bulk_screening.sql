-- Migration 0038: F19 — Bulk Screening Mode (regulator / law-firm / insurer).
-- ADDITIVE ONLY. Idempotent.
--
-- Adds the batch-screening surface on top of the verified reassessment kernel
-- (services/reassessment.py → live_scoring.score_and_persist — the single
-- scoring path). No scoring columns are added: every score row is written by
-- the existing pipeline. Two tables track the job and its rows; the 'analyst'
-- role is added to the user_role enum (Supabase-auth path; local-auth already
-- carries role via the app_role claim).

-- ── analyst role ─────────────────────────────────────────────
-- profiles.role is the Postgres ENUM user_role ('customer','sme','admin' —
-- migration 0004). Bulk endpoints require admin|analyst. ADD VALUE is safe and
-- idempotent; it cannot run inside a txn block, so it stands alone.
ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'analyst';

-- ── bulk_job — one submitted screening batch, owned by a tenant ──────────────
CREATE TABLE IF NOT EXISTS bulk_job (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID NOT NULL REFERENCES organization(organization_id),  -- owner tenant
    created_by      UUID,
    label           TEXT,
    status          TEXT NOT NULL DEFAULT 'queued'
                        CHECK (status IN ('queued','running','partial','completed','failed')),
    row_count       INT  NOT NULL DEFAULT 0,
    completed_count INT  NOT NULL DEFAULT 0,
    failed_count    INT  NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at     TIMESTAMPTZ
);

-- List/detail are tenant-scoped; the one-running-job-per-tenant guard (AC-11)
-- needs a fast "does this tenant have an active job?" lookup.
CREATE INDEX IF NOT EXISTS idx_bulk_job_org_created ON bulk_job (org_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_bulk_job_active ON bulk_job (org_id) WHERE status IN ('queued','running');

-- ── bulk_job_row — one company/notice in a batch ────────────────────────────
-- assessment_id → privacy_notice(notice_id): the fresh assessment scored for
-- this row (NULL until scored / for non-succeeded rows). NOTE: the org that
-- assessment lives under is ALWAYS a fresh screening organization, never an
-- existing customer tenant's org record (F19 cross-tenant trap, AC-10).
CREATE TABLE IF NOT EXISTS bulk_job_row (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bulk_job_id   UUID NOT NULL REFERENCES bulk_job(id) ON DELETE CASCADE,
    position      INT  NOT NULL,
    org_name      TEXT NOT NULL,          -- display name shown in results (not organization.name)
    notice_url    TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'pending'
                      CHECK (status IN ('pending','running','succeeded','failed','insufficient_profile')),
    assessment_id UUID REFERENCES privacy_notice(notice_id),
    error         TEXT
);

CREATE INDEX IF NOT EXISTS idx_bulk_job_row_job ON bulk_job_row (bulk_job_id, position);
