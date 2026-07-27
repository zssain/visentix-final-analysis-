# Change Report — F02 HHS OCR Breach Connector

**Branch:** `F02-hhs-ocr` (off `F02-ingestion-foundation`) · **Date:** 2026-07-23 · **Merge:** NOT merged

## What shipped
`HHSOCRConnector` (family `hhs_ocr`) on the Prompt-3 framework — `app/services/ingestion/connectors/hhs_ocr.py`, registered in `registry.CONNECTORS`, runnable via `python -m app.services.ingestion.run --family hhs_ocr [--dry-run]`.

- **fetch** — GET the CSV export URL from `source_registry.config.csv_url` (falls back to `base_url`); no API key. Validates the response is actually CSV (content-type or the `Name of Covered Entity` header) and raises a clear error otherwise. One `RawItem` = the whole CSV → **one raw artifact + one source_record per download batch** (`source_type='security'`, tier 1 from the registry).
- **parse** — `csv.DictReader`, maps the 8 OCR columns → `security_event` (Name→entity_name_raw, Covered Entity Type→entity_type, State→state, Individuals Affected→individuals_affected, Breach Submission Date→submission_date, Type of Breach→breach_type, Location of Breached Information→information_location, Web Description→description). `extraction_confidence=1.0` for well-formed rows.
- **row-level idempotency** — `event_id = uuid5(namespace, entity_name_raw|submission_date|breach_type|individuals_affected)`; upsert uses `ON CONFLICT (event_id) DO NOTHING`, so re-running an unchanged CSV inserts 0 and a CSV with 5 new rows inserts exactly 5. (The framework *also* skips the whole item when the CSV hash is unchanged.)
- **malformed rows are never dropped** — a row whose `Individuals Affected`/`Breach Submission Date` won't parse, or with no entity name, is stored with `extraction_confidence=0.5` and the raw row preserved in `description` (`[MALFORMED ROW] {...}`), and counted in the run's `error_summary` (outcome → `partial`).
- **no entity resolution** (Prompt 5) — `organization_id` left NULL, `resolution_status='unresolved'`.
- **never writes `enforcement_record`** — the only write sink is `security_event` (OD-06 / schema §2.9). Asserted statically (no `rest/v1/enforcement_record` in the connector) and behaviorally.

Framework additions (backward-compatible hooks on `base.Connector` / `runner`): `record_counts()` lets a batch connector report **row-level** counts so `ingestion_run.records_seen` = parsed breaches (not the 1 CSV item), and `run_warnings()` folds the malformed-row count into `error_summary` and marks the run `partial`.

Security posture: never logs row text (counts only); no secrets printed; fetched CSV is untrusted (parsed with `csv`, never eval'd).

## Tests — `tests/test_hhs_ocr_connector.py` (fake backend + fake event writer; committed fixture `tests/fixtures/hhs_ocr_sample.csv`, 4 well-formed + 1 malformed)
Golden-file parse (field mapping, quoted-comma field, `records_seen`==security_event count, lineage present) · malformed row not dropped (confidence<1.0, raw preserved, counted) · idempotent re-run (0 new) · changed CSV with 5 new rows → exactly 5 · zero `enforcement_record` writes · connector registered.

## Real run (as requested) — HONEST OUTCOME
The task assumed a GET-able official CSV. **There isn't one:** `https://ocrportal.hhs.gov/ocr/breach/breach_report.jsf` returns `text/html` on GET — the CSV export is a stateful **JSF form POST** (ViewState), not a static URL. Confirmed by probing the live endpoint and the portal HTML.

- **`--dry-run`:** `outcome=failed seen=0` — the connector correctly rejected the HTML as non-CSV.
- **live:** `outcome=failed`, **run_id `02ae37fe-2b0c-4e5d-adbf-1a3c1d215b14`**, `records_seen=0`, **malformed=0**, **raw artifact: none** (fetch fails before raw-store), **security_event unchanged (0 rows)**. The `ingestion_run` records a precise, non-secret `error_summary`.

I did **not** fabricate counts, scrape the JSF ViewState (fragile/workaround, against AGENTS.md §3), or write fixture data to the immutable `raw-artifacts` bucket. The connector is fully proven by the golden-fixture tests; a genuine ingest needs one of:
1. a confirmed **direct GET-able CSV URL** placed in `source_registry.config.csv_url` (the connector then works unchanged), or
2. a follow-up adding a **JSF-export POST** fetch strategy for this family.

**Needs human:** decide (1) vs (2) for live HHS OCR ingestion.

## Full suite
**650 passed, 15 skipped, 0 failed** (+6 new HHS OCR tests over the prior 644).
