-- Migration 0020: schema_migrations governance table (schema.md v1.3 §5.2)
-- ADDITIVE ONLY. Idempotent (CREATE TABLE IF NOT EXISTS).
--
-- The migration-tracking ledger whose absence caused the 0014/0017 drift
-- (see logs/audits/2026-07-data-layer-audit.md). New governance rule:
--   "No migration is considered applied unless a row exists here."
--
-- Rows are written by scripts/db/apply_and_record.py (which computes the raw
-- SHA-256 of each migration file). Backfill of already-applied historical
-- migrations and recording of newly-applied ones is done by that runner —
-- NOT embedded here, to avoid a file-checksums-itself circular reference.

CREATE TABLE IF NOT EXISTS schema_migrations (
    filename    TEXT PRIMARY KEY,
    checksum    TEXT NOT NULL,          -- hex SHA-256 of the migration file bytes
    applied_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Internal governance table: never exposed to the browser (anon) client.
-- service_role bypasses RLS; anon/authenticated are denied entirely.
ALTER TABLE schema_migrations ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON schema_migrations FROM anon, authenticated;
