-- Migration 0008: Phase 7 — Training label table for SME correction capture
-- Additive only. Idempotent.

CREATE TABLE IF NOT EXISTS training_label (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    assessment_id   TEXT NOT NULL,
    finding_id      TEXT NOT NULL,
    original        JSONB,
    corrected       JSONB,
    action          TEXT NOT NULL,
    field           TEXT NOT NULL DEFAULT 'finding',
    sme_user_id     TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_training_label_assessment
    ON training_label(assessment_id);
CREATE INDEX IF NOT EXISTS idx_training_label_action
    ON training_label(action);
CREATE INDEX IF NOT EXISTS idx_training_label_created
    ON training_label(created_at);
