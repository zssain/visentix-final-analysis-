-- Migration 0031: formula_version.description (Phase 5 / M-10)
-- ADDITIVE ONLY. Idempotent.
--
-- schema.md §L66 declares formula_version with a plain-English `description` column
-- ("powers lineage drawer"), but the live table only has the math `definition`. The
-- lineage drawer (DDR-005) must show a plain-English description with NO math notation.
-- This adds the column; content is populated by scripts/seed_formula_descriptions.py
-- (sourced strictly from 01-foundation/intelligence-logic.md §7, guardrail-safe).

ALTER TABLE formula_version ADD COLUMN IF NOT EXISTS description TEXT;
