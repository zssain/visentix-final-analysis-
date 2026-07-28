-- Migration 0040: F21 — Quarterly Global Privacy Intelligence Report (Deliverable 4).
-- ADDITIVE ONLY. Idempotent.
--
-- Baseline quarterly publication: a frozen snapshot + one row per computed
-- Service-4 metric. Approved snapshots are IMMUTABLE — enforced BOTH by a
-- service-layer guard (services/quarterly.py) AND the Postgres trigger below
-- (our most public artifact's immutability must not depend on every future
-- code path remembering the rule).

-- ── quarterly_snapshot ───────────────────────────────────────
CREATE TABLE IF NOT EXISTS quarterly_snapshot (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    quarter              TEXT NOT NULL,                    -- '2026-Q3'
    status               TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','approved')),
    frozen_at            TIMESTAMPTZ,
    corpus_version       TEXT,
    formula_versions     JSONB,
    population_criteria  JSONB,
    gate_result          JSONB,                            -- {passed:bool, violations:[...]} (anonymization gate)
    approved_by          UUID,                             -- lineage: who approved (expert-review permission)
    approved_at          TIMESTAMPTZ,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- At most ONE approved snapshot per quarter (drafts may be rebuilt).
CREATE UNIQUE INDEX IF NOT EXISTS uq_quarterly_snapshot_approved
    ON quarterly_snapshot (quarter) WHERE status = 'approved';
CREATE INDEX IF NOT EXISTS idx_quarterly_snapshot_quarter ON quarterly_snapshot (quarter, created_at DESC);

-- ── quarterly_metric ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS quarterly_metric (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    snapshot_id        UUID NOT NULL REFERENCES quarterly_snapshot(id) ON DELETE CASCADE,
    metric_id          TEXT NOT NULL,                      -- 'S4-001' …
    value              NUMERIC,
    value_label        TEXT,
    population_n       INT,
    suppressed         BOOLEAN NOT NULL DEFAULT false,
    suppression_reason TEXT,
    formula_citation   TEXT,                               -- Catalog row ref (reference/derived-catalog-S4.md)
    computed_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_quarterly_metric_snapshot ON quarterly_metric (snapshot_id);

-- ── Immutability trigger (DIR-010 / Hard Rule 6) ─────────────
-- Once a snapshot is approved, neither it nor its metric rows may be updated
-- or deleted. The draft→approved transition itself is allowed (OLD.status is
-- 'draft' at that point). Belt-and-suspenders alongside the service guard.
CREATE OR REPLACE FUNCTION reject_if_quarterly_approved() RETURNS trigger AS $$
BEGIN
    IF TG_TABLE_NAME = 'quarterly_snapshot' THEN
        IF OLD.status = 'approved' THEN
            RAISE EXCEPTION 'quarterly_snapshot % is approved and immutable (DIR-010)', OLD.id;
        END IF;
    ELSE  -- quarterly_metric: block if its parent snapshot is approved
        IF EXISTS (SELECT 1 FROM quarterly_snapshot s
                   WHERE s.id = OLD.snapshot_id AND s.status = 'approved') THEN
            RAISE EXCEPTION 'quarterly_metric % belongs to an approved snapshot and is immutable (DIR-010)', OLD.id;
        END IF;
    END IF;
    RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER trg_quarterly_snapshot_immutable
    BEFORE UPDATE OR DELETE ON quarterly_snapshot
    FOR EACH ROW EXECUTE FUNCTION reject_if_quarterly_approved();

CREATE OR REPLACE TRIGGER trg_quarterly_metric_immutable
    BEFORE UPDATE OR DELETE ON quarterly_metric
    FOR EACH ROW EXECUTE FUNCTION reject_if_quarterly_approved();
