# Change Report — F02 FTC Enforcement Connector

**Branch:** `F02-ftc-enforcement` · **Date:** 2026-07-23 · **Merge:** NOT merged

## What shipped
`FTCConnector` (family `ftc`) on the F02 connector framework — scrapes the FTC Legal
Library cases-proceedings listing filtered to privacy/data-security topics (plus a
press-release RSS for incremental updates) and writes `enforcement_record` rows +
per-PDF `source_record` rows. Registered in `registry.CONNECTORS`; run via
`scripts/ingest/run_ftc.py` (`--dry-run` / `--limit N` / `--full` / `--incremental`).

- **Politeness & robots compliance.** Honest `User-Agent` identifying Visentix.
  robots.txt is fetched **with that UA via httpx** (FTC's CDN 403s urllib's default
  UA, which would make `RobotFileParser` disallow-all) and its **Crawl-delay: 5** is
  honored (≥5s between every request). The old `ingest_enforcement.py` FTC scraper
  used `?items_per_page=50` URLs — those are **Disallowed** by FTC robots.txt; this
  connector paginates with `?page=N` + `search_api_fulltext` only.
- **Per-case capture.** Title, respondent/company name(s), FTC Matter/File Number,
  civil action number (if any), action date, the FTC's own topic tags, penalty (if
  stated), remedy excerpt, and document-PDF links. Parsing scopes to the
  `article.node--type-case` region(s) — a case renders as *two* such articles (one
  carries matter/tags/date, another the documents) and the page `<h1>` sits outside
  them, so fields are read across all case articles (which also keeps sidebar/blog
  **date-noise** out). Reuses the baseline `ingest_enforcement.extract_penalty`
  (AC-G5 reuse).
- **PDFs.** Each linked PDF is downloaded (polite) into
  `raw-artifacts/ftc/{YYYY}/{MM}/{sha256}.pdf` and gets its own `source_record`
  (`source_type='enforcement'`, tier 1), deduped by content hash.
- **enforcement_record.** Upserts on `enforcement_id` (uuid5 of the case URL) → re-runs
  add no duplicates. `issue_tags` = the FTC's own topic tags **VERBATIM** — they are
  **NOT** mapped to Visentix domains here; `domains`/`violation_types`/`laws_cited`
  are left NULL. Target org resolved via `organization_alias`/`organization.name`
  exact-normalized match (reuses `entity_resolution`); on a match `organization_id`
  is set and `resolution_status='resolved'`, else NULL + `'unresolved'`.
- **Regulator seed.** Ensures the FTC `regulator` row exists (it already did → no-op).
  **Never** writes `priority_weights`/`enforcement_frequency_weight` (computed later
  by a versioned job — left untouched).
- **Incremental mode.** RSS-driven (`--incremental`): reads the consumer-protection
  press-release feed, extracts referenced case-proceeding links, processes those.
- **Full-crawl resume.** `--full` paginates and persists the last crawled page to
  `logs/ftc_crawl_cursor.json`; the next `--full` resumes from the following page
  (override with `--start-page`).
- **No obligations.** This connector creates **zero** `obligation` rows — order-derived
  obligations need expert review (TODO referenced in code: F02 v2).

## Verdict-language containment (AGENTS.md Hard Rule 1)
FTC case text WILL contain "violation"/"violated" etc. Those are confined to **RAW
source fields** (`summary`, `issue_tags`, `target_company`/`entity_name`, `remedy`,
`official_url`). Every **derived/structured** field the connector writes
(`source_type`, `regulator_id`, `jurisdiction`, `matter_number`,
`civil_action_number`, `resolution_status`) is asserted banned-term-free via the
existing `guardrail` service — see the containment test.

## Schema / DB changes (additive, idempotent, applied + recorded to live)
- **0026** — `ftc_topic_domain_map`: an **EMPTY, expert-owned scaffold** crosswalk
  from FTC topic tags → Visentix domains. **Deliberately unpopulated — requires
  expert population before any FTC topic feeds domain logic.** Also adds
  `enforcement_record.matter_number` / `civil_action_number`.
- **0027** — `enforcement_record.organization_id` + `resolution_status` (the table
  had nowhere to record entity resolution).

## Tests — `tests/test_ftc_connector.py` (11; fake fetcher + fake writer + typed fake backend; committed fixture `tests/fixtures/ftc_case_sample.html`)
Golden-file parse (title, respondents, matter="2223002", civil action, **date scoped
past a 2019 sidebar-noise date**, penalty $2.25M, verbatim tags, absolute PDF links) ·
listing + RSS link extraction (excludes non-case sections) · full run writes
enforcement + both PDFs + resolves org · unresolved-when-no-match · **pagination
crawls-until-empty** · **pagination resume from start_page** · **idempotent re-run**
(unchanged case ⇒ 0 new) · **PDF raw-storage path** convention + `source_type='enforcement'`
source_record · **verdict-language containment** (raw `summary` keeps "violated";
derived fields banned-term-free) · connector registered. Migration-manifest tests
updated for 0026/0027.

**Full suite: 699 passed, 15 skipped, 0 failed.**

## Live runs
- **`--dry-run --limit 50`** (fetch + parse, no writes) — scanned the newest 50 cases;
  **6** carried an actual privacy/data-security topic tag (the other ~44 only mention
  "privacy" in full text). `outcome=ok`, 0 writes.
- **Limited live `--limit 50`** — `outcome=ok, enforcement_record written=6, PDFs
  stored=36, orgs resolved=1 (Amazon.com), 0 errors`. Cases: RentGrow ($2.25M),
  Amazon.com ($2.25M), Kochava, Illuminate Education, Twitter, + one more. Verified in
  live: 42 `source_record` (family `ftc`, `source_type='enforcement'`); tags stored
  VERBATIM; `ftc_topic_domain_map` still **0 rows**; FTC regulator weight fields
  **unchanged** (`ensure_regulator` no-op'd — the row pre-existed).
  - **Merge, not duplicate:** the connector's `enforcement_id` (uuid5 of the case URL)
    matches the baseline `ingest_enforcement.py` derivation, so re-scraping a case
    **enriches** the existing row (adds matter_number / civil_action_number / verbatim
    issue_tags / resolution) instead of inserting a duplicate — the intended migration.
- **STOPPED before the full historical crawl**, per instruction. Resume with
  `python scripts/ingest/run_ftc.py --full` (starts at page 0; cursor persisted).

## Needs human
- **Populate `ftc_topic_domain_map`** (empty scaffold): the FTC-topic → Visentix-domain
  crosswalk is expert-owned; until filled, FTC tags feed nothing downstream.
- **Order-derived obligations**: not created here (F02 v2 expert review).
- **Retire the FTC branch of `ingest_enforcement.py`** from any schedule so the family
  isn't ingested twice (spec §2 "duplicate/parallel ingestion is a defect"). The
  shared `extract_penalty` is reused; the old robots-noncompliant FTC crawl should not
  parallel-run.
