# Change Report — HHS OCR JSF CSV-Export Fetch (live ingest working)

**Branch:** `F02-hhs-ocr-jsf` (off `F02-hhs-ocr`) · **Date:** 2026-07-23 · **Merge:** NOT merged

## Goal
The OCR portal has no static CSV URL — its **"Export as CSV" is a public JSF form POST**. Implement that export as the `hhs_ocr` fetch strategy, hand the CSV to the existing parse path, and ingest live.

## What changed
**`HHSOCRConnector.fetch()` now drives the public JSF export** (`connectors/hhs_ocr.py`), every dynamic token extracted fresh each run:
1. GET the report front page → `ocrForm` action + `ViewState` + the **"View HIPAA Breach Reports"** jsfcljs command.
2. POST it → the results page → `ViewState` + the **CSV-export** command (the anchor wrapping the `alt="CSV"` icon, distinct from Excel/PDF/XML).
3. POST the CSV command → the `text/csv` attachment.

Extraction helpers are module-level and unit-tested: `jsf_viewstate`, `jsf_form_action`, `jsf_command_by_label`, `jsf_csv_export_command`.

**Fragility is loud, not clever** (as instructed): if any token/command is missing, or the final response isn't CSV, `fetch()` raises with a precise message → the run ends `outcome=failed` with a non-secret `error_summary`. There is **no HTML-table-scraping fallback**.

**Parser adapted to the real export structure.** The live CSV has 9 positional columns and — a PrimeFaces quirk — the *Name of Covered Entity* and *Business Associate* headers render as broken `javax.faces.component.UIPanel@…` strings. So `_resolve_columns` takes **Name positionally (column 0)** and the rest **by header name**, and **raises loudly** if a required named column is missing or column 0 is a known named field (structure changed → refuse to guess).

Everything else is unchanged from the Prompt-4 connector: row-level idempotency (`event_id = uuid5(natural key)`, `ON CONFLICT DO NOTHING`), malformed rows kept at `extraction_confidence<1.0` with the raw row in `description`, `organization_id` NULL / `resolution_status='unresolved'`, and **never writes `enforcement_record`**.

### Framework fixes (both surfaced by the live run / real data)
- **`source_record.version_id` is INTEGER**, not text — `process_item` was setting it to `"{source_id}#1"` (the FakeBackend didn't type-check, so tests were green but live 400'd). Now the source_record gets integer version `1`; the `source_id#N` text id stays on `source_version` (its own PK). *This was a latent framework bug the fixture masked.*
- **dry-run now parses** (read-only) so a batch connector reports real **row** counts, still writing nothing.
- `ingestion_run.parser_version_id` is now recorded.

## Tests
`tests/test_hhs_ocr_connector.py` (fixtures updated to the real 9-column export; added `hhs_ocr_front.html` / `hhs_ocr_report.html`):
- **golden JSF extraction** — ViewState, form actions, the View command, and the CSV (not Excel) export command; **loud-fail** cases when the form changes (helpers return None) and when the CSV column structure changes (`parse` raises).
- golden CSV parse (real structure, quoted-comma field), malformed handling, idempotent re-run, changed-CSV→5-new, zero enforcement writes, registration.
No network / no live DB in tests (fake backend + fake event writer + saved HTML/CSV fixtures).

## Real run (live, official public data)
| | |
|---|---|
| `--dry-run` | fetched via JSF export, **parsed 709 rows, 0 malformed**, `outcome=ok`, wrote nothing |
| **live** | **run_id `ea963e2d-5d44-41a9-8f4a-c5dba08df799`**, `outcome=ok` |
| rows ingested | **707 security_event rows** (709 parsed − 2 natural-key duplicates skipped) |
| malformed | **0** (this export had no malformed rows) |
| raw artifact | `raw-artifacts/hhs_ocr/2026/07/102916220e0fd5fb7b3b745424c28b35ac68efb470710cd49d6daf10cd649d3a.csv` (91,522 bytes) |
| source_record | `hhs_ocr:dfac74c999bc9804d251c3c1` (`source_type='security'`, `version_id=1`) + 1 `source_version` |
| enforcement_record | **649, unchanged** (zero writes) |

Sample ingested (real): *Conduent Business Services LLC* (62,224,658 individuals), *Aflac Incorporated* (13,924,906) — `organization_id` NULL, `resolution_status='unresolved'`.

**Note:** the first live attempt failed on the `version_id` bug *after* storing its raw artifact, leaving one orphan CSV (`…989bbeae….csv`, real OCR data, no source_record). Per AGENTS.md the `raw-artifacts` bucket is never deleted from, so it remains; it will be reused (not duplicated) if that exact content recurs.

## Full suite
**653 passed, 15 skipped, 0 failed** (+3 new tests: JSF extraction, loud-fail-on-form-change, loud-fail-on-column-change).

## Needs human
None blocking. Optional: a scheduled cadence for `hhs_ocr` (registry `cadence=weekly`) once a scheduler exists; and an entity-resolution pass (Prompt 5) to populate `security_event.organization_id`.
