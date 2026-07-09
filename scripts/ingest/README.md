# Ingest Scripts

Each script pulls data from a free, public source into the Visentix Supabase
database. All scripts share `_common.py` for Supabase access, upsert logic,
and ingestion-run audit tracking.

## Prerequisites

```bash
# From repo root, activate the venv
source .venv/bin/activate
```

## Scripts

| Script | Target Table(s) | Source | Run Command |
|--------|-----------------|--------|-------------|
| `ingest_ecfr.py` | `legal_reference`, `finding_legal_reference` | [eCFR API](https://www.ecfr.gov/developer/documentation/api/v1) (US federal regulations) | `PYTHONPATH=. python scripts/ingest/ingest_ecfr.py` |
| `ingest_eurlex.py` | `legal_reference`, `finding_legal_reference` | [EUR-Lex SPARQL](https://eur-lex.europa.eu/content/help/data-reuse/sparql-endpoint.html) (EU directives/regulations) | `PYTHONPATH=. python scripts/ingest/ingest_eurlex.py` |
| `ingest_ftc.py` | `enforcement_record` | [FTC Cases & Proceedings](https://www.ftc.gov/legal-library/browse/cases-proceedings) | `PYTHONPATH=. python scripts/ingest/ingest_ftc.py` |
| `ingest_state_laws.py` | `legal_reference` | [OpenStates API](https://v3.openstates.org/docs) (US state privacy bills) | `PYTHONPATH=. python scripts/ingest/ingest_state_laws.py` |
| `ingest_enforcement.py` | `enforcement_record` | [CourtListener](https://www.courtlistener.com/api/) / public regulator feeds | `PYTHONPATH=. python scripts/ingest/ingest_enforcement.py` |

## Shared module

`_common.py` provides:
- `URL`, `H` — Supabase REST endpoint and service-role headers
- `sha256_text(s)` — content hashing for dedup
- `upsert(table, rows, on_conflict)` — idempotent POST with retry
- `start_run(source_name, run_type)` / `finish_run(run_id, ...)` — audit trail
- `clean_html(html)` — HTML to plain text

## Safety

- All upserts use `ON CONFLICT DO NOTHING` or `resolution=merge-duplicates`
- Every run is tracked in `ingestion_run` for auditability
- Scripts log counts and IDs only, never full legal text bodies
- Use `--dry-run` flag (where supported) to preview without writing
