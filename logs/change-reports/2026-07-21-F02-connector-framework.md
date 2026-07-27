# Change Report — F02 Connector Framework

**Branch:** `F02-ingestion-foundation` · **Date:** 2026-07-21 · **Merge:** NOT merged

## Goal
A reusable, testable connector framework under `app/services/ingestion/` implementing the F02 v2 lifecycle (`fetch → hash → raw-store → skip/new/version → parse → normalize → upsert`). No source-specific logic beyond a fake test connector.

## Design — ports & adapters (testable without live DB)
The per-item lifecycle depends on a `Backend` **port**, so it runs against Supabase in prod and an in-memory fake in tests. This is why the framework tests are fast, deterministic, and don't pollute live tables.

- **`base.py`** — `RawItem` (bytes + content-type + source_url + natural_key); `Connector` ABC (`fetch`/`parse`/`upsert` + `family`/`source_type`/`parser_version`); `Backend` ABC; pure helpers `sha256_bytes`, `ext_for_content_type`, `derive_source_id`, `raw_artifact_path`; and **`process_item`** — the lifecycle:
  1. sha256 the bytes.
  2. resolve `source_record` by natural key (deterministic `source_id = family:sha256(family::natural_key)[:24]`).
  3. **unchanged** (latest `source_version.hash` == content hash) → **SKIP**; **new** → new `source_record` + `source_version#1`; **changed** → new `source_version#N`.
  4. **parse first, then persist** — a parse failure leaves *no* partial state (raw/source_record only written after a successful parse), so a failed item is retry-safe, never stranded.
  5. raw bytes stored at `raw-artifacts/{family}/{YYYY}/{MM}/{sha256}.{ext}` (never overwrite; existing object → reused).
  6. every normalized record carries `source_record_id`, `capture_date`, `extraction_confidence`, `parser_version_id`.
- **`backend.py`** — `SupabaseBackend` (PostgREST + Storage, service-role). Raw upload uses `x-upsert: false` → existing objects are never overwritten (409/Duplicate → "reused"). `parser_version` registered idempotently on first use (`on_conflict=family,version`).
- **`runner.py`** — `run()`: opens an `ingestion_run`, retries transient HTTP on `fetch()` (max 3, exp backoff), applies the global politeness delay (`settings.ingestion_politeness_seconds`) between items, isolates per-item exceptions into an error list (one item failing ⇒ **partial**, never aborts), writes `finished_at` + `outcome` + counts (seen/new/changed/skipped). A total fetch failure ⇒ **failed** run, recorded.
- **`registry.py`** — `CONNECTORS` family→class dispatch, `load_enabled_sources()`, `run_one_by_family()`. No real connectors registered yet (they land per-family later); an unknown family raises a clear error.
- **`run.py`** — CLI `python -m app.services.ingestion.run --family hhs_ocr [--dry-run]`. `--dry-run` does fetch + hash + diff counts and writes nothing (no `ingestion_run`, no `parser_version`, no raw, no source rows).

## Schema
- **Migration 0024** creates `source_version` (documented in schema.md §2.2 but never applied) — the change-detection history. Applied live via `apply_and_record.py`, recorded in `schema_migrations` (25 rows). Server-side RLS only.

## Config
- `ingestion_politeness_seconds` (default `0.0`) added to `Settings`.

## Security posture
Never logs document text — only lengths + hashes. Never prints env/secrets. The framework makes no network calls itself (connectors fetch only from their `source_registry` config URLs). Fetched bytes are treated as untrusted — never eval/exec'd; connectors parse defensively.

## Tests — `tests/test_ingestion_framework.py` (fake backend + fake connector)
1. **idempotent re-run** → 0 new, all skipped; no duplicate records/versions.
2. **changed content** → 1 changed + a new `source_version` (2 versions, distinct hashes; source_record not duplicated).
3. **per-item failure** → `partial` outcome, the failing item recorded as an error, the other items fully ingested (their upserted records present), run persisted as partial.
4. **dry-run writes nothing** → diff counted (new=2) but backend completely empty.
5. **raw path convention** → object key matches `raw-artifacts/{family}/{YYYY}/{MM}/{sha256}.{ext}`.
Plus: pure-helper path/ext test and a lineage assertion (every parsed record carries the 4 required fields).

## Full suite
**644 passed, 15 skipped, 0 failed.**

Two `test_f02_ingestion_foundation.py` assertions needed updating (not regressions in the framework):
- `test_apply_now_order_and_step_a_first` — appended `0024_source_version.sql` to the expected `APPLY_NOW`.
- `test_schema_migrations_rows_match_file_checksums` — the **live DB is shared across feature branches**, so its `schema_migrations` ledger also holds `0022`/`0023` (applied from the F06/F04 work) whose files aren't on this branch; the test now checks *this branch's* tracked migrations against the ledger (matching checksums) and ignores sibling-branch rows, rather than requiring every ledger row's file to exist here.

## Notes
- No real per-family connectors are registered yet (out of scope) — the CLI reports a clear "No connector registered for family 'X'" until they land. The fake connector lives only in the test.
- `SupabaseBackend` read paths smoke-tested against live (source_version reachable); the framework's behavior is proven via the fake backend so tests stay fast and don't write to live.
