-- Migration 0025: sic_industry_map DRAFT seed table (F02 EDGAR import)
-- ADDITIVE ONLY. Idempotent.
--
-- A crosswalk from SEC SIC codes -> Visentix industry_id (IND-xx). Authored as a
-- DRAFT by the EDGAR importer work; EVERY row carries mapped_by='draft'.
--
-- ⚠️ EXPERT APPROVAL REQUIRED. The sec_edgar importer does NOT write these
-- industry_id values onto organization.industry_id. Nothing here feeds profiling
-- (F03) or benchmark cohorting until an expert reviews each range and re-marks it
-- mapped_by='approved'. Draft rows must never be silently applied.
--
-- Row semantics: each row covers the inclusive 4-digit SIC range [sic_low, sic_high].
-- The map's source of truth is config/sic_industry_map.json (kept in sync); this
-- table exists so the draft is reviewable/queryable in the database. Server-side only.

CREATE TABLE IF NOT EXISTS sic_industry_map (
    map_id        TEXT PRIMARY KEY,             -- deterministic: 'sic:{sic_low}-{sic_high}'
    sic_low       TEXT NOT NULL,                -- inclusive 4-digit SIC range start
    sic_high      TEXT NOT NULL,                -- inclusive 4-digit SIC range end
    industry_id   TEXT NOT NULL,                -- IND-xx (see db/migrations/0014 comment)
    industry_name TEXT NOT NULL,
    mapped_by     TEXT NOT NULL DEFAULT 'draft' -- 'draft' until expert-approved
                    CHECK (mapped_by IN ('draft', 'approved')),
    notes         TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_sic_industry_map_industry ON sic_industry_map(industry_id);

-- Seed the DRAFT ranges (idempotent upsert on the deterministic map_id).
INSERT INTO sic_industry_map (map_id, sic_low, sic_high, industry_id, industry_name, mapped_by, notes) VALUES
  ('sic:5200-5999', '5200', '5999', 'IND-01', 'Retail & Consumer',           'draft', 'SIC 52-59 retail trade.'),
  ('sic:7370-7379', '7370', '7379', 'IND-02', 'Software & SaaS',             'draft', 'SIC 7370-7379 computer programming / prepackaged software / data processing.'),
  ('sic:2833-2836', '2833', '2836', 'IND-03', 'Healthcare & Life Sciences',  'draft', 'SIC 2833-2836 pharmaceutical & biological products.'),
  ('sic:3826-3826', '3826', '3826', 'IND-03', 'Healthcare & Life Sciences',  'draft', 'SIC 3826 laboratory analytical instruments.'),
  ('sic:3841-3845', '3841', '3845', 'IND-03', 'Healthcare & Life Sciences',  'draft', 'SIC 3841-3845 surgical/medical/electromedical instruments.'),
  ('sic:8000-8099', '8000', '8099', 'IND-03', 'Healthcare & Life Sciences',  'draft', 'SIC 80 health services.'),
  ('sic:6000-6199', '6000', '6199', 'IND-04', 'Financial Services',          'draft', 'SIC 6000-6199 credit institutions.'),
  ('sic:6200-6299', '6200', '6299', 'IND-04', 'Financial Services',          'draft', 'SIC 6200-6299 security & commodity brokers.'),
  ('sic:6300-6411', '6300', '6411', 'IND-04', 'Financial Services',          'draft', 'SIC 6300-6411 insurance carriers/agents.'),
  ('sic:6700-6799', '6700', '6799', 'IND-04', 'Financial Services',          'draft', 'SIC 6700-6799 holding & investment offices.'),
  ('sic:8200-8299', '8200', '8299', 'IND-05', 'Education',                   'draft', 'SIC 8200-8299 educational services.'),
  ('sic:2700-2799', '2700', '2799', 'IND-06', 'Entertainment & Media',       'draft', 'SIC 2700-2799 publishing (media).'),
  ('sic:7800-7999', '7800', '7999', 'IND-06', 'Entertainment & Media',       'draft', 'SIC 7800-7999 motion pictures, amusement & recreation.')
ON CONFLICT (map_id) DO UPDATE SET
  sic_low = EXCLUDED.sic_low, sic_high = EXCLUDED.sic_high,
  industry_id = EXCLUDED.industry_id, industry_name = EXCLUDED.industry_name,
  notes = EXCLUDED.notes;   -- NOTE: mapped_by is intentionally NOT overwritten, so an
                            -- expert's 'approved' flag survives a re-seed.

ALTER TABLE sic_industry_map ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON sic_industry_map FROM anon, authenticated;
