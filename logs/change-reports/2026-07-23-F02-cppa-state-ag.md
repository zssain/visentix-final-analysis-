# Change Report — F02 CPPA + State AG Connectors

**Branch:** `F02-state-enforcement` · **Date:** 2026-07-23 · **Merge:** NOT merged

## What shipped
Two regulator-enforcement connectors on the F02 framework, sharing a new
`connectors/_enforcement.py` (generic Supabase writer + deterministic
enforcement/privacy keyword classification + verdict-containment contract). Both
reuse the FTC connector's `PoliteFetcher` (robots-aware) and `entity_resolution`.

### A. `CPPAConnector` (family `cppa`)
- **Primary source** `https://privacy.ca.gov/about-us/newsroom/` (Divi/WordPress:
  `article.et_pb_post`, `h2.entry-title>a`, `span.published`, category in the article
  class). Plus **ONE archival pass** of the legacy `cppa.ca.gov/announcements/`
  (guarded by `archive_only` in registry config; `--archive-pass` forces the one-time
  historical pass).
- **Routing:** ENFORCEMENT-relevant items (settlements, fines, decisions, subpoena
  actions, sweeps) → an `enforcement_record` (regulator `CPPA`) + any order/decision
  PDF stored as a tier-1 `source_record`. Non-enforcement news (appointments,
  advisories, legislation) → the page is a `source_record` ONLY
  (`source_type='regulator_announcement'`), no enforcement_record.
- **Classification is TITLE-based** — CPPA's site nav carries an "Enforcement" menu
  link, so full-page body text false-fires; CPPA headlines state the action plainly.
  `issue_tags` = CPPA's own post categories, VERBATIM. Penalty via the reused
  `extract_penalty`.

### B. `StateAGConnector` (family `state_ag`, folder `ag_actions`)
- **One config-driven class, N sites.** Site list in `source_registry.config.sites`:
  `{state, url, parser_hint, verified}`. `parser_hint` selects the parser; all hints
  currently route to a generic press-release parser (title/date/link/body) with a
  dispatch table ready for per-site overrides.
- **Honest confidence:** `extraction_confidence` = **1.0** for structured markup
  (`<article>`+`<time>`), **0.6** for heuristic (dated headline links). Low-confidence
  items are **stored + flagged** (run warning → partial), never dropped or promoted.
- **Routing:** only items matching BOTH a privacy signal AND an enforcement signal
  become `enforcement_record` candidates (regulator `{STATE}-AG`); everything else is
  `source_record` only.
- **Per-site failure isolation:** one broken site → skipped with a warning (partial
  run); the others still succeed.

## Framework additions (backward-compatible)
- `Connector.raw_folder` — a family may store raw bytes under a different folder than
  its registry name (schema §2 family↔folder: `state_ag` → `ag_actions`).
- `RawItem.extraction_confidence` — per-item honest confidence flows into the
  `source_record` (heterogeneous AG parses); `None` → the connector default.

## Guardrails
- **Verdict-language containment:** regulator source text may contain "violation"
  etc., but ONLY inside RAW source fields (`summary`, `issue_tags`,
  `target_company`, `remedy`). Every derived field is asserted banned-term-free
  (guardrail containment tests for both connectors).
- **Regulator weights untouched:** `ensure_regulator`/`ensure_regulator_for` create a
  row only if absent and never write priority/topic-weight fields.
- **No obligation rows.** Enforcement upserts on `enforcement_id` (idempotent).
  Org resolution is exact/normalized only (reuses `entity_resolution`).

## Registry / seed
- `cppa` config: added `archive_url` + `archive_only=true` (steady state; the
  historical pass is one-time).
- `state_ag` config: seeded the engineer-confirmed **16-site list**
  (CA,TX,CT,CO,NY,WA,IL,MA,NJ,VA,OR,MN,FL,NH,DE,MD), `enabled=false`. CA/TX/CT/CO URLs
  are verified; the other 12 need per-site parser validation before enabling.

## Tests — 14 new (fixtures: 1 CPPA listing + 2 CPPA details, 2 AG list pages)
`tests/test_cppa_connector.py` (7): listing/detail golden parse, PDF extraction,
enforcement-vs-announcement routing + counts, idempotent re-run, verdict containment.
`tests/test_state_ag_connector.py` (7): structured vs heuristic confidence,
privacy-enforcement routing, low-confidence flagged-not-dropped, **per-site failure
isolation**, idempotency, verdict containment + `raw_folder`.
`tests/ingestion_fakes.py` gains `FakeEnforcementWriter`.

**Full suite: 713 passed, 15 skipped, 0 failed.**

## Live runs
- **CPPA `--dry-run`** — 10 newsroom pages; title-based routing correctly split
  enforcement (e.g. GM $12.75M settlement) from announcements (audits, legislation).
- **CPPA `--archive-pass` (real):** `outcome=ok, enforcement_record written=3,
  announcement-only source_records=7, order PDFs stored=2, 0 errors`. Enforcement:
  GM privacy settlement ($12.75M), Ford opt-out fine ($1.1M), youth-sports-media fine
  ($1.1M). Verified in live: 10 `source_record` family `cppa` (`regulator_announcement`)
  + 2 (`enforcement`, PDFs at `raw-artifacts/cppa/2026/07/{sha}.pdf`); CPPA regulator
  weights untouched; 3 new embeddings backfilled. The legacy `cppa.ca.gov/announcements`
  archival pass returned no parseable items (page defunct/redirect) — handled gracefully.
  (Company names were not extractable from these AG-partnership headlines → resolution
  unresolved; honest.)
- **State AG:** NOT run — stays disabled until the final site list is confirmed.

## Needs human
- **Validate + enable the state-AG sites.** All 16 confirmed sites are seeded but
  `enabled=false`. CA/TX/CT/CO URLs are verified; the other 12 (NY/WA/IL/MA/NJ/VA/OR/
  MN/FL/NH/DE/MD) need a per-site parse check (and likely real overrides for
  `ct_year_subpages`/`massgov_list`/`legacy_asp`) before flipping `enabled=true`.
- **AG breach-notification routing (AC-STATE_AG):** breach *notices* should route to
  `security_event` (not enforcement_record). This connector routes privacy-enforcement
  → enforcement_record and everything else → source_record only (per task); dedicated
  breach→security_event routing is a follow-up.
- **Per-site parser overrides:** all `parser_hint`s use the generic parser today;
  `ct_year_subpages`/`massgov_list`/`legacy_asp` will likely need real overrides once
  enabled (heterogeneous quality expected).
