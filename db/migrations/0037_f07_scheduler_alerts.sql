-- Migration 0037: F07 completion — scheduler, alert delivery, monitored notices,
-- litigation skeleton. ADDITIVE ONLY. Idempotent.
--
-- Reconciliation (verified live, 2026-07-28): monitoring_event has NO
-- organization_id / event_type / payload; privacy_notice has NO
-- monitoring_enabled. The F07 jobs must emit org-attributed events with
-- structured payloads, so those columns are added ADDITIVELY (nullable, no
-- backfill — old events stay NULL and remain URL-scoped as today). Event-type
-- vocabulary is unchanged: the four §2.8 values only.

-- ── job execution ledger ─────────────────────────────────────
CREATE TABLE IF NOT EXISTS job_run (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_name        TEXT NOT NULL,
    started_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at     TIMESTAMPTZ,
    status          TEXT NOT NULL CHECK (status IN ('running', 'succeeded', 'failed')),
    items_processed INT NOT NULL DEFAULT 0,
    items_changed   INT NOT NULL DEFAULT 0,
    error           TEXT,
    triggered_by    TEXT NOT NULL CHECK (triggered_by IN ('schedule', 'manual'))
);
CREATE INDEX IF NOT EXISTS idx_job_run_name_started ON job_run (job_name, started_at DESC);
-- Concurrency guard support: fast "is this job already running?" lookup.
CREATE INDEX IF NOT EXISTS idx_job_run_running ON job_run (job_name) WHERE status = 'running';

-- ── alert delivery ledger ────────────────────────────────────
CREATE TABLE IF NOT EXISTS alert_delivery (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    monitoring_event_id UUID NOT NULL REFERENCES monitoring_event(event_id),
    org_id              UUID REFERENCES organization(organization_id),
    channel             TEXT CHECK (channel IN ('email', 'webhook')),
    destination         TEXT,
    status              TEXT NOT NULL CHECK (status IN ('pending', 'sent', 'failed', 'suppressed_no_threshold')),
    sent_at             TIMESTAMPTZ,
    error               TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_alert_delivery_org ON alert_delivery (org_id);
CREATE INDEX IF NOT EXISTS idx_alert_delivery_event ON alert_delivery (monitoring_event_id);
CREATE INDEX IF NOT EXISTS idx_alert_delivery_suppressed ON alert_delivery (status)
    WHERE status = 'suppressed_no_threshold';

-- ── per-org notification settings ────────────────────────────
CREATE TABLE IF NOT EXISTS org_notification_setting (
    org_id       UUID PRIMARY KEY REFERENCES organization(organization_id),
    email_to     TEXT,
    webhook_url  TEXT,
    min_severity TEXT,                       -- NULL = inherit platform default
    webhook_secret TEXT,                     -- per-org HMAC secret (generated)
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── monitoring_event: additive org + typed payload ───────────
ALTER TABLE monitoring_event
    ADD COLUMN IF NOT EXISTS organization_id UUID REFERENCES organization(organization_id),
    ADD COLUMN IF NOT EXISTS event_type TEXT,
    ADD COLUMN IF NOT EXISTS payload JSONB;
ALTER TABLE monitoring_event DROP CONSTRAINT IF EXISTS monitoring_event_event_type_check;
ALTER TABLE monitoring_event
    ADD CONSTRAINT monitoring_event_event_type_check
    CHECK (event_type IS NULL OR event_type IN
        ('notice_changed', 'score_moved', 'regulator_signal', 'cohort_rebenchmarked'));
CREATE INDEX IF NOT EXISTS idx_monitoring_event_org ON monitoring_event (organization_id);

-- ── privacy_notice: opt-in monitoring flag ───────────────────
ALTER TABLE privacy_notice
    ADD COLUMN IF NOT EXISTS monitoring_enabled BOOLEAN NOT NULL DEFAULT false;

-- ── litigation (court-filing SKELETON — NOT wired to scoring) ─
CREATE TABLE IF NOT EXISTS litigation (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source      TEXT,
    title       TEXT,
    court       TEXT,
    filed_at    TIMESTAMPTZ,
    url         TEXT UNIQUE,
    issue_tags  TEXT[],
    reliability TEXT NOT NULL DEFAULT 'low',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
