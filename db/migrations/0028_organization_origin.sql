-- Migration 0028: organization.origin (F02 Princeton-Leuven import)
-- ADDITIVE ONLY. Idempotent.
--
-- Benchmark-only organizations created from an external research corpus (e.g. the
-- Princeton-Leuven privacy-policy dataset) are flagged with their provenance so
-- downstream jobs can tell curated-corpus peers apart from customer/EDGAR orgs.
-- NULL for all pre-existing rows.

ALTER TABLE organization
    ADD COLUMN IF NOT EXISTS origin TEXT;   -- e.g. 'princeton_leuven' (NULL = not corpus-derived)
