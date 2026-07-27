-- Migration 0034: decompose-v2 noise filter provenance (F01)
-- ADDITIVE ONLY. Idempotent.
--
-- The decomposer now flags nav/heading/metadata/list-fragment clauses as noise
-- (deterministic rule, DECISION-NEEDED.md Part 1 / F01). Noise clauses are KEPT
-- for lineage but excluded from classification counts, scoring inputs, and the
-- presence-count profile dimensions (PGMS/DSI/AIGMS). These columns record that.
--
-- `is_noise` defaults false so every EXISTING clause is correctly treated as
-- substantive (it was never filtered). `privacy_notice.decompose_version` marks
-- which assessments were produced by the noise-filtering decomposer; NULL means
-- an older assessment that must stay untouched (Rule 4).

ALTER TABLE disclosure_clause
    ADD COLUMN IF NOT EXISTS is_noise     BOOLEAN NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS noise_reason TEXT;

ALTER TABLE privacy_notice
    ADD COLUMN IF NOT EXISTS decompose_version TEXT;

-- Fast "substantive clauses only" reads (scoring/profiling filter is_noise=false).
CREATE INDEX IF NOT EXISTS idx_disclosure_clause_is_noise
    ON disclosure_clause (is_noise) WHERE is_noise = false;
