-- Migration 0024: source_version table (F02 connector framework)
-- ADDITIVE ONLY. Idempotent.
--
-- schema.md §2.2 documents source_version (change-detection history) but it was
-- never applied to live. The connector framework writes a new source_version row
-- whenever a monitored source's content hash changes. Server-side only.

CREATE TABLE IF NOT EXISTS source_version (
    version_id   TEXT PRIMARY KEY,
    source_id    TEXT NOT NULL REFERENCES source_record(source_id),
    hash         TEXT NOT NULL,               -- sha256 of the captured bytes
    captured_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    diff_summary TEXT
);

CREATE INDEX IF NOT EXISTS idx_source_version_source ON source_version(source_id);
CREATE INDEX IF NOT EXISTS idx_source_version_captured ON source_version(source_id, captured_at DESC);

ALTER TABLE source_version ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON source_version FROM anon, authenticated;
