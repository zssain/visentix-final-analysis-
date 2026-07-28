-- Migration 0036: gold_label — human gold-standard labels for the F17 eval harness
-- ADDITIVE ONLY. Idempotent.
--
-- Holds ONLY human-authored gold labels for the evaluation gold set (F17). The
-- harness pre-fills NOTHING: `labeler` is NOT NULL, so a label can never be
-- written without a human attributed to it. gold_domain uses the category_v2
-- vocabulary (8 legacy domain slugs + 'other') so classifier accuracy is an
-- apples-to-apples comparison against disclosure_clause.category_v2.

CREATE TABLE IF NOT EXISTS gold_label (
    label_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clause_id        UUID NOT NULL REFERENCES disclosure_clause(clause_id),
    labeler          TEXT NOT NULL,                 -- human attribution; never NULL
    labeled_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    gold_domain      TEXT,                          -- one of the 9 category_v2 slugs
    verdict          TEXT,                          -- correct / incorrect / ambiguous
    note             TEXT,
    gold_set_version TEXT NOT NULL DEFAULT 'v1',
    UNIQUE (clause_id, labeler, gold_set_version)   -- one label per labeler per clause per set
);

ALTER TABLE gold_label DROP CONSTRAINT IF EXISTS gold_label_gold_domain_check;
ALTER TABLE gold_label
    ADD CONSTRAINT gold_label_gold_domain_check
    CHECK (gold_domain IS NULL OR gold_domain IN (
        'consumer_rights', 'data_sharing', 'tracking_cookies', 'cross_border',
        'sensitive_data', 'retention', 'children_teens', 'ai_automated_decisions', 'other'));

ALTER TABLE gold_label DROP CONSTRAINT IF EXISTS gold_label_verdict_check;
ALTER TABLE gold_label
    ADD CONSTRAINT gold_label_verdict_check
    CHECK (verdict IS NULL OR verdict IN ('correct', 'incorrect', 'ambiguous'));

CREATE INDEX IF NOT EXISTS idx_gold_label_clause ON gold_label (clause_id);
