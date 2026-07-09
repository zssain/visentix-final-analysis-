-- Migration 0013: Add source_type and verified columns to enforcement_record.
-- Required by ingest_enforcement.py. ADDITIVE ONLY. Idempotent.

ALTER TABLE enforcement_record ADD COLUMN IF NOT EXISTS source_type  TEXT;
ALTER TABLE enforcement_record ADD COLUMN IF NOT EXISTS verified     BOOLEAN DEFAULT false;
