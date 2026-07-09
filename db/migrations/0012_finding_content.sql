-- Migration 0012: Add definition column to finding_type for plain-language descriptions.
-- ADDITIVE ONLY. Idempotent.

ALTER TABLE finding_type ADD COLUMN IF NOT EXISTS definition TEXT;
