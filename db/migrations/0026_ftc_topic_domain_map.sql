-- Migration 0026: FTC enforcement connector support (F02 v2)
-- ADDITIVE ONLY. Idempotent.
--
-- (a) ftc_topic_domain_map — EMPTY expert-owned scaffold. Crosswalk from the FTC's
--     own topic tags (stored VERBATIM on enforcement_record.issue_tags) to Visentix
--     disclosure domains. Deliberately UNPOPULATED: the FTC-topic → domain mapping
--     is expert-owned and must be filled by a human, not inferred by the connector.
--     Until populated, nothing maps FTC tags to domains. See the F02 change report.
--
-- (b) enforcement_record: add matter_number / civil_action_number — first-class FTC
--     case identifiers the connector captures (the table had nowhere to put them).

CREATE TABLE IF NOT EXISTS ftc_topic_domain_map (
    map_id      TEXT PRIMARY KEY,             -- deterministic slug of the ftc_topic
    ftc_topic   TEXT NOT NULL,                -- the FTC's own topic tag, verbatim
    domain      TEXT,                          -- Visentix disclosure domain (NULL until approved)
    mapped_by   TEXT NOT NULL DEFAULT 'unmapped'
                  CHECK (mapped_by IN ('unmapped', 'draft', 'approved')),
    notes       TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- No seed rows: EXPERT POPULATION REQUIRED before FTC topics feed any domain logic.

ALTER TABLE ftc_topic_domain_map ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON ftc_topic_domain_map FROM anon, authenticated;

-- enforcement_record case identifiers (nullable, additive)
ALTER TABLE enforcement_record
    ADD COLUMN IF NOT EXISTS matter_number        TEXT,   -- FTC Matter/File Number (e.g. "2223002")
    ADD COLUMN IF NOT EXISTS civil_action_number  TEXT;   -- e.g. "1:26-cv-02415" (if in court)
