# Change Report — F02 Open-Web Notice Crawler

**Branch:** `F02-openweb-crawler` · **Date:** 2026-07-23 · **Merge:** NOT merged

## What shipped
`OpenWebConnector` (family `open_web`, raw folder `notices`) — given a `crawl_target`
work-list, finds and captures each company's CURRENT privacy notice. Registered in
`registry.CONNECTORS`; run via `scripts/ingest/run_openweb.py --sector … --limit …`.

- **Discovery** (`find_privacy_links`, pure/unit-tested): footer/header links matching
  privacy patterns (privacy / privacy policy / privacy notice / `/privacy` /
  `/legal/privacy`) + the intake `PRIVACY_PATHS`; follows **≤2 hops**. Every candidate
  is **SSRF-validated via the reused `intake.ssrf.validate_url`** — not reimplemented.
- **Rendering** is behind a `Renderer` port: `PlaywrightRenderer` (lazy import — module
  imports fine without Playwright) renders JS-only footers; tests inject fixture HTML.
  The rendered page's text still flows through the intake extractor + heuristics.
- **Capture** → framework raw-store (`raw-artifacts/notices/…`) + `source_record`
  (tier 1) + `privacy_notice` via the EXISTING intake path (`intake.decompose.decompose`,
  same as Prompt 8 / Princeton). Org resolved via `organization_alias` (domain) or a new
  **peer** org (`origin='open_web'`, canonical fields never overwritten).
- **Politeness:** robots.txt honored (`DomainPolicy`), **≥1 request / 2s per domain**,
  honest UA, global delay from config; a **hard 4xx is NEVER retried**.
- **Honest outcomes:** every non-capture is recorded on `crawl_target.status` +
  `status_reason` — `no_notice` / `blocked` / `consent_wall` / `error` — never
  fabricated, never silently skipped.
- **Change detection:** unchanged content hash ⇒ `status='unchanged'`, no re-capture
  (the mechanism that later powers monitoring).

## Schema / seed
- **Migration 0029** — `crawl_target` (target_id, organization_id, domain, sector,
  priority, status, status_reason, content_hash, notice_url, last_crawled_at, added_by).
  Applied + recorded to live. **Described first** in a `schema.md` **v1.3.1** changelog
  paragraph + §2.9 table row.
- `scripts/db/seed_crawl_targets.py` builds targets from (a) EDGAR mapped-industry orgs
  and (b) Princeton-resolved orgs that carry a domain; `--sector` / `--limit` flags.

## Tests — `tests/test_openweb_connector.py` (13; committed HTML fixtures)
Link discovery (footer link / nested legal page / no-notice) · consent-wall detection ·
**robots.txt respect** · **per-domain rate-limit spacing** · **hash-skip** (unchanged
⇒ unchanged status, no capture) · **crawl_target status transitions** (captured /
no_notice / blocked / consent_wall) · **hard-4xx-not-retried** · source_record under
the `notices` folder · connector registered.

**Full suite: 735 passed, 15 skipped, 0 failed.**

## Live pilot — FINTECH DEMO (retail blocked; engineer chose A)
The **retail** pilot could not run — **0 retail domains exist** (EDGAR websites blank →
0 domain aliases; Princeton not imported). Per the engineer's decision, the pilot ran
as a **working demo on the 30 available fintech/logistics peer domains** (Playwright +
Chromium installed).

**`--limit 25`:** `outcome=ok, crawled=25, captured=14, no_notice=10, blocked=1,
0 errors.`
- Verified live: 14 `open_web` `privacy_notice` + 14 tier-1 `source_record` (family
  `open_web`, under `raw-artifacts/notices/`); `crawl_target` statuses set (14 captured,
  10 no_notice, 1 blocked, 5 still pending). New `disclosure_clause` embeddings backfilled.
- **Honest failure reasons** (never fabricated): `homepage_Error` ×6, `homepage_http_403`
  ×2, `homepage_TimeoutError` ×1, `robots_disallow` ×1, `no privacy link found` ×1.
- Samples: stripe.com (483 clauses, `/in/privacy`), squareup.com (291), paypal.com
  (13 — the crawler landed on a cookie-preferences sub-page, a thin capture). *Quality
  note:* discovery finds the first privacy-pattern link that passes the heuristic, which
  is occasionally a cookie-prefs/locale page rather than the main policy — an honest
  imperfection to tune (per-site hints / prefer longest policy) before scaling.

**STOPPED for review** before scaling, per instruction.

## Needs human (decision)
- **Retail targets** still need a source: import the Princeton retail CSV (carries retail
  domains) or enrich EDGAR orgs with domains, then re-seed + pilot retail.
- **Tune discovery ranking** (prefer the main policy over cookie-prefs/locale pages)
  before a large-scale crawl.
