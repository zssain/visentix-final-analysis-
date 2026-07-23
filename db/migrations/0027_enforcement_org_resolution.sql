-- Migration 0027: enforcement_record entity resolution columns (F02 FTC)
-- ADDITIVE ONLY. Idempotent.
--
-- The FTC connector resolves each action's target company to an organization via
-- organization_alias (exact/normalized) where possible, else leaves it unresolved.
-- enforcement_record had nowhere to record that link, so add:
--   organization_id   — resolved org (NULL when unmatched)
--   resolution_status — 'resolved' | 'unresolved' (mirrors security_event)

ALTER TABLE enforcement_record
    ADD COLUMN IF NOT EXISTS organization_id   UUID,
    ADD COLUMN IF NOT EXISTS resolution_status TEXT NOT NULL DEFAULT 'unresolved';
