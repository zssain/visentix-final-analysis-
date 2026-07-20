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

These are the scripts that actually exist in this directory (verified 2026-07-20). The earlier eCFR/EUR-Lex/FTC entries were consolidated into `ingest_legal_refs.py` and `ingest_enforcement.py`.

| Script | Target Table(s) | Source | Run Command |
|--------|-----------------|--------|-------------|
| `ingest_enforcement.py` | `enforcement_record` | [FTC Cases & Proceedings](https://www.ftc.gov/legal-library/browse/cases-proceedings) (scrape) + [CourtListener](https://www.courtlistener.com/api/) (API, `COURTLISTENER_TOKEN`) | `PYTHONPATH=. python scripts/ingest/ingest_enforcement.py` |
| `ingest_legal_refs.py` | `legal_reference`, `finding_legal_reference` | eCFR (COPPA/HIPAA/GLBA), EUR-Lex + gdpr-info (GDPR), state legislature sites | `PYTHONPATH=. python scripts/ingest/ingest_legal_refs.py` |
| `ingest_state_laws.py` | `obligation`, `legal_reference` | [OpenStates API](https://v3.openstates.org/docs) (`OPENSTATES_API_KEY`) + hardcoded state bill URLs | `PYTHONPATH=. python scripts/ingest/ingest_state_laws.py` |
| `embed_enforcement_new.py` | `enforcement_record.embedding` | Local `all-MiniLM-L6-v2` (no external fetch); backfills rows where `embedding IS NULL` | `PYTHONPATH=. python scripts/ingest/embed_enforcement_new.py` |
| `update_findings.py` | `finding_type`, `finding_legal_reference` | DB-only: replaces STUB finding content, links findings to legal refs | `PYTHONPATH=. python scripts/ingest/update_findings.py` |

> **F02 v2 note:** these scripts are the current-state baseline. The registry-driven connector framework (F02 v2) must **reuse** their parsing logic and migrate them onto the shared run-logging / raw-store path — not parallel-run against them.

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
