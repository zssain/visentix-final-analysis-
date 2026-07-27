# Change Report — F02 SEC EDGAR Bulk Import

**Branch:** `F02-edgar-import` · **Date:** 2026-07-23 · **Merge:** NOT merged

## What shipped
`EdgarBulkConnector` (family `sec_edgar`) on the F02 connector framework — a **batch importer, not a crawler**. It reads the LOCAL bulk download at `EDGAR_BULK_PATH` (`submissions/` metadata per company) and creates/enriches `organization` rows + `organization_alias` rows. Registered in `registry.CONNECTORS`; runnable via the dedicated driver `scripts/ingest/run_edgar.py` (`--limit N` pilot / `--full` / `--dry-run` / `--industries`) or the generic `python -m app.services.ingestion.run --family sec_edgar --limit N`.

- **Local-first.** Reads `submissions/CIK##########.json` on disk. The ONLY permitted network call is fetching `company_tickers.json` (the ticker roster) if it is absent from the bulk — cached into the bulk dir on first fetch. If that fetch fails, it falls back to scanning the local `submissions/` directory (ticker-bearing companies only). SEC's CDN requires a real-contact `User-Agent` (generic UAs get 403); set accordingly.
- **Additive enrichment — never overwrites.** Entity resolution order: `cik` alias → `ticker` alias → `domain` alias → existing `organization.domain` (normalized) → `slug`. On a match, only **currently-NULL** enrichable columns (`domain`, `public_company_flag`, `size_metadata`, `revenue_metadata`) are filled; `name`/`industry`/`industry_id`/`slug` are never touched. On no match, a new `organization` is created (`industry='unknown'` — the NOT-NULL placeholder; unique `slug`; `entity_type='peer'`; `public_company_flag=true`).
- **Authoritative aliases (match_confidence 1.0)** for `cik` (10-digit), each `ticker`, current + former `legal_name`, and `domain` (normalized: lowercase, no scheme/www/port/path). Idempotent via the live `UNIQUE(alias_type, value)` — `ON CONFLICT DO NOTHING`. (SEC's `website` field is blank for ~all filers, so `domain` aliases are rare in practice — recorded honestly, not synthesized.)
- **SIC → industry is a DRAFT, and is NOT applied to organizations.** `config/sic_industry_map.json` (source of truth) + seed table `sic_industry_map` (migration 0025) cover retail, software/SaaS, healthcare, financial services, education, entertainment as ranges IND-01…IND-06, **every row `mapped_by='draft'`**. The importer records the draft suggestion only as an *input* in `size_metadata.sic_industry_draft`; it leaves `organization.industry_id` NULL. **⚠️ THE MAPPING REQUIRES EXPERT APPROVAL before it feeds profiling (F03).**
- **Size/sophistication inputs only** (no scores computed, nothing in `organization_intelligence_profile` touched): `size_metadata` = `{sic, sic_description, filer_category, entity_type_sec, state_of_incorporation, exchanges, employee_count?, sic_industry_draft}`; `revenue_metadata` only if revenue is present in the bulk (it isn't in submissions metadata — left NULL). Profiling stays owned by the existing deterministic profiler.
- **Lifecycle & lineage.** Each company = one `RawItem` → raw-store the submissions JSON at `raw-artifacts/sec_edgar/{YYYY}/{MM}/{sha256}.json`, one `source_record` (`source_type='corporate_filing'`), one `source_version`, one `ingestion_run`. Idempotent: an unchanged submissions JSON hashes the same → item SKIPPED → 0 new rows. Scope is flag-driven (`--industries`, default = all mapped) with `--limit` for the pilot.

Security posture: local JSON is untrusted (`json.loads` only, never eval/exec); logs carry counts/keys, never record text or secrets.

## Schema / config / DB changes
- **New migration `0025_sic_industry_map.sql`** (additive, idempotent) — creates + seeds the DRAFT `sic_industry_map` table; added to `apply_and_record.APPLY_NOW` and **applied + recorded to live** (`schema_migrations`, checksum `42088b41e479…`). `mapped_by` is preserved on re-seed so an expert's `approved` flag survives.
- **New config `config/sic_industry_map.json`** — the draft crosswalk (13 SIC ranges → IND-01…IND-06), loudly marked draft/expert-gated.
- `app/config.py`: added `edgar_bulk_path` setting; `.env`/`.env.example` carry `EDGAR_BULK_PATH`.
- `.gitignore`: `/SEC EDGAR/` (the ~15 GB bulk) is ignored — never committed.
- No existing table/column altered. `organization`/`organization_intelligence_profile` scoring columns untouched.

## Tests — `tests/test_edgar_connector.py` (21 tests; fake backend + `FakeOrgStore`, both live-type-checked; committed golden fixture `tests/fixtures/edgar_sample_submissions.json`)
Golden-file parse (field/alias mapping, draft-not-applied) · full run creates org + 5 aliases with lineage · **no-overwrite** (existing name/industry/industry_id survive re-import; NULLs additively filled) · industry never touched when already set · **alias uniqueness** (`UNIQUE(alias_type,value)`) · **domain normalization** (10 cases incl. `world.com` not stripped, ports/paths/userinfo) · slug/cik helpers · **idempotent re-run** (0 new orgs/aliases) · industry scoping filters unmapped SIC · explicit industry subset · draft-map load · connector registered. `tests/ingestion_fakes.py` gains `FakeOrgStore`; migration-manifest tests updated for 0025.

**Full suite: 680 passed, 15 skipped, 0 failed.**

## Live runs (real writes)
- **Pilot `--limit 500`** — `outcome=ok, seen=500, orgs_created=500, orgs_enriched=0, errors=0`. Aliases: 500 `cik` + 700 `ticker` + 889 `legal_name` = **2089**, all `match_confidence=1.0`; **0** orgs got `industry_id` (draft not applied); 500 `source_record` `corporate_filing`; 1 `ingestion_run`. Pre-existing peers (PayPal/Stripe/Block) unchanged. Per-industry: IND-01 50 / IND-02 99 / IND-03 118 / IND-04 220 / IND-06 13.
- **Full run `--full`** (all 6 mapped industries) — `outcome=ok, seen=3326 new orgs, errors=0`. Combined with the pilot: **3,826 unique companies imported**, **15,476 aliases** (3,826 `cik` + 4,894 `ticker` + 6,756 `legal_name`), 3,826 `corporate_filing` source_records, 2 `ingestion_run` rows. Per-industry (roster-row scope): IND-01 307 / IND-02 697 / IND-03 1329 / IND-04 2781 / IND-05 57 / IND-06 147.
  - **Reconciliation:** `company_tickers.json` has one row *per ticker*, so multi-share-class filers (e.g. Alphabet GOOGL+GOOG → one CIK) appear as duplicate-CIK roster rows. In-scope roster rows = 5,318 → **3,826 unique CIKs**. The 1,992 framework SKIPs = 500 pilot re-runs + 1,492 duplicate-CIK rows ⇒ **0 duplicate orgs** created (idempotency working as designed). `domain` aliases: 0 (SEC's `website` field is blank for these filers). **industry_id set: 0** (draft map not applied). Pre-existing peers untouched.
  - _Data note:_ SEC's `category` field occasionally carries an HTML fragment (e.g. `"<br>Emerging growth company"`); captured verbatim into `size_metadata.filer_category` as a raw input — not transformed by the importer.

## Acceptance criteria (AC-SEC_EDGAR)
✅ `source_record` rows `source_type='corporate_filing'`; ✅ `organization_alias` of type `{cik, ticker}` (and `legal_name`, `domain`) with `match_confidence`; ✅ no existing `organization.name` overwritten (verified pre/post). ✅ AC-G4 run logging (one `ingestion_run`, `parser_version_id` set); ✅ idempotency (unchanged JSON ⇒ 0 new rows).

## Needs human
**Expert approval of the DRAFT SIC→industry map** (`sic_industry_map`, all rows `mapped_by='draft'`) before it may set `organization.industry_id` or feed profiling/benchmark cohorting. Until then industry_id stays NULL and the draft suggestion lives only in `size_metadata.sic_industry_draft`.
