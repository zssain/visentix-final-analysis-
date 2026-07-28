-- Migration 0039: F20 — Partner Portal (Deliverable 3, white-label channel).
-- ADDITIVE ONLY. Idempotent.
--
-- Real tenancy + branding + hardened feed on top of the existing single
-- pipeline. No forked review, no forked scorer. partner_admin is added to the
-- user_role enum and profiles/local-auth carry partner_id the same way they
-- carry organization_id (F10 parity). report_snapshot gains branding_applied,
-- frozen at approval so a branded PDF is byte-identical per snapshot.

-- ── partner_admin role (Supabase-auth path; local-auth carries it via claim) ──
ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'partner_admin';

-- profiles carries partner_id exactly as it carries organization_id.
ALTER TABLE profiles ADD COLUMN IF NOT EXISTS partner_id UUID;

-- Branding provenance on the snapshot: {partner_id, logo_hash, brand_color,
-- frozen_at}. Written at approval (or first render for pre-F20 snapshots).
ALTER TABLE report_snapshot ADD COLUMN IF NOT EXISTS branding_applied JSONB;

-- ── partner ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS partner (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT NOT NULL,
    logo_url    TEXT,
    logo_hash   TEXT,                       -- sha256 of the stored logo bytes (branding freeze)
    brand_color TEXT,
    status      TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','suspended')),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── partner_workspace — the bridge: one workspace wraps exactly one client org ──
CREATE TABLE IF NOT EXISTS partner_workspace (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    partner_id    UUID NOT NULL REFERENCES partner(id) ON DELETE CASCADE,
    client_org_id UUID NOT NULL REFERENCES organization(organization_id),
    name          TEXT NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_partner_workspace_partner ON partner_workspace (partner_id);
-- Scope resolution: given a client org, which workspace/partner owns it.
CREATE INDEX IF NOT EXISTS idx_partner_workspace_client ON partner_workspace (client_org_id);

-- ── partner_api_key — HASH ONLY, never plaintext ─────────────
CREATE TABLE IF NOT EXISTS partner_api_key (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    partner_id   UUID NOT NULL REFERENCES partner(id) ON DELETE CASCADE,
    key_hash     TEXT NOT NULL,             -- sha256 of the plaintext key (shown once)
    key_last4    TEXT,                       -- last 4 chars for masked display
    label        TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_used_at TIMESTAMPTZ,
    revoked_at   TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_partner_api_key_partner ON partner_api_key (partner_id);
-- Fast hash lookup for feed auth (only non-revoked keys are valid).
CREATE INDEX IF NOT EXISTS idx_partner_api_key_hash ON partner_api_key (key_hash) WHERE revoked_at IS NULL;

-- ── feed_access_log — every served white-label feed call ─────
CREATE TABLE IF NOT EXISTS feed_access_log (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    partner_id UUID REFERENCES partner(id),
    api_key_id UUID REFERENCES partner_api_key(id),
    endpoint   TEXT NOT NULL,
    at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    row_count  INT NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_feed_access_log_partner ON feed_access_log (partner_id, at DESC);
