-- Migration 0029: crawl_target table (F02 open-web notice crawler)
-- ADDITIVE ONLY. Idempotent.
--
-- A work-list of company domains whose CURRENT privacy notice the open_web crawler
-- should find + capture. Seeded from EDGAR mapped-industry orgs and Princeton-resolved
-- orgs. status carries the honest outcome of the last crawl attempt (never fabricated,
-- never silently skipped); content_hash powers change-detection for re-crawls (the
-- same mechanism that later drives monitoring). Server-side only.

CREATE TABLE IF NOT EXISTS crawl_target (
    target_id        TEXT PRIMARY KEY,               -- deterministic: 'ct:{domain}'
    organization_id  UUID REFERENCES organization(organization_id),  -- resolved org (nullable)
    domain           TEXT NOT NULL,                  -- normalized (lowercase, no scheme/www)
    sector           TEXT,
    priority         INTEGER NOT NULL DEFAULT 100,   -- lower = crawled sooner
    status           TEXT NOT NULL DEFAULT 'pending' -- pending|captured|unchanged|no_notice|blocked|consent_wall|error
                       CHECK (status IN ('pending','captured','unchanged','no_notice',
                                         'blocked','consent_wall','error')),
    status_reason    TEXT,                           -- honest reason for a non-captured outcome
    content_hash     TEXT,                           -- sha256 of last captured notice (change detection)
    notice_url       TEXT,                           -- the privacy-notice URL actually captured
    last_crawled_at  TIMESTAMPTZ,
    added_by         TEXT,                           -- seed source, e.g. 'seed:edgar' / 'seed:princeton'
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS crawl_target_domain_key ON crawl_target(domain);
CREATE INDEX IF NOT EXISTS idx_crawl_target_status ON crawl_target(status);
CREATE INDEX IF NOT EXISTS idx_crawl_target_sector ON crawl_target(sector);

ALTER TABLE crawl_target ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON crawl_target FROM anon, authenticated;
