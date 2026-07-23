-- Migration 0022: Persistence hardening for review/training state (F06)
-- ADDITIVE ONLY. Idempotent (CREATE ... IF NOT EXISTS / CREATE OR REPLACE).
--
-- Moves what review.py / training.py held in module memory into the DB as the
-- authoritative store: gate mode -> platform_setting; review state ->
-- assessment_review; VCI analyst queue -> review_queue_item. training_label
-- already exists (0008) and holds the label shape unchanged. Adds the
-- approve_and_freeze() function so approval + snapshot freeze commit atomically.
--
-- RLS: all new tables are server-side only (service_role bypasses RLS;
-- anon/authenticated denied) — never exposed to the browser (AGENTS.md §3).

CREATE EXTENSION IF NOT EXISTS pgcrypto;   -- digest() for content_hash

-- ============================================================
-- 1. platform_setting — key/value config (schema.md §2.1). Holds gate_mode.
-- ============================================================
CREATE TABLE IF NOT EXISTS platform_setting (
    key         TEXT PRIMARY KEY,
    value       TEXT,
    updated_by  TEXT,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- NOTE (OD-08): gate_mode values use the CURRENT code enum
-- (strict / instant_draft / client_reviews). The canonical enum vs the spec's
-- instant_draft/expert_review is still OPEN (OD-08) — do NOT rename here.

-- ============================================================
-- 2. assessment_review — per-assessment review state (was review.py `_reviews`)
--    finding_reviews jsonb mirrors the in-memory {finding_id -> {action,...}} map.
-- ============================================================
CREATE TABLE IF NOT EXISTS assessment_review (
    assessment_id   TEXT PRIMARY KEY,
    status          TEXT NOT NULL DEFAULT 'draft'
                        CHECK (status IN ('draft', 'in_review', 'approved')),
    finding_reviews JSONB NOT NULL DEFAULT '{}'::jsonb,
    approved_by     TEXT,
    approved_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- 3. review_queue_item — VCI analyst-review queue
--    (was review.py `_low_vci_objects` + `_analyst_cleared`, merged via `cleared`)
-- ============================================================
CREATE TABLE IF NOT EXISTS review_queue_item (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    assessment_id TEXT NOT NULL,
    object_type   TEXT NOT NULL,
    vci_score     FLOAT8,
    score         FLOAT8,
    is_definitive BOOLEAN,
    needs_review  BOOLEAN NOT NULL DEFAULT true,
    cleared       BOOLEAN NOT NULL DEFAULT false,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    cleared_at    TIMESTAMPTZ,
    CONSTRAINT review_queue_item_assessment_object_key UNIQUE (assessment_id, object_type)
);
CREATE INDEX IF NOT EXISTS idx_review_queue_item_assessment ON review_queue_item(assessment_id);

-- ============================================================
-- 4. report_snapshot.assessment_id — link a snapshot to its assessment so
--    approve_and_freeze can find the snapshot to freeze (additive; schema.md
--    §2.8 already documents assessment_id on report_snapshot).
-- ============================================================
ALTER TABLE report_snapshot ADD COLUMN IF NOT EXISTS assessment_id TEXT;
CREATE INDEX IF NOT EXISTS idx_report_snapshot_assessment ON report_snapshot(assessment_id);

-- ============================================================
-- 5. approve_and_freeze() — approval + snapshot freeze in ONE transaction.
--    A PostgREST RPC call runs the whole function body in a single transaction:
--    if the freeze RAISEs, the approval upsert rolls back too (never half-approved).
-- ============================================================
CREATE OR REPLACE FUNCTION approve_and_freeze(
    p_assessment_id TEXT,
    p_approver      TEXT,
    p_snapshot_id   UUID DEFAULT NULL
) RETURNS VOID AS $$
BEGIN
    -- (1) approval state
    INSERT INTO assessment_review (assessment_id, status, approved_by, approved_at, updated_at)
    VALUES (p_assessment_id, 'approved', p_approver, now(), now())
    ON CONFLICT (assessment_id) DO UPDATE
        SET status = 'approved', approved_by = EXCLUDED.approved_by,
            approved_at = EXCLUDED.approved_at, updated_at = now();

    -- (2) freeze the snapshot (only when one is supplied). A missing snapshot
    -- RAISEs, rolling back the approval above — the atomicity kill-test.
    IF p_snapshot_id IS NOT NULL THEN
        UPDATE report_snapshot
            SET rendered_report = payload,
                content_hash    = encode(digest(payload::text, 'sha256'), 'hex'),
                report_version  = COALESCE(report_version, 1)
            WHERE snapshot_id = p_snapshot_id;
        IF NOT FOUND THEN
            RAISE EXCEPTION 'approve_and_freeze: report_snapshot % not found', p_snapshot_id;
        END IF;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- 6. RLS + grants — server-side only
-- ============================================================
ALTER TABLE platform_setting  ENABLE ROW LEVEL SECURITY;
ALTER TABLE assessment_review ENABLE ROW LEVEL SECURITY;
ALTER TABLE review_queue_item ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON platform_setting  FROM anon, authenticated;
REVOKE ALL ON assessment_review FROM anon, authenticated;
REVOKE ALL ON review_queue_item FROM anon, authenticated;
REVOKE ALL ON FUNCTION approve_and_freeze(TEXT, TEXT, UUID) FROM anon, authenticated;
