# Change Report — F02 Princeton-Leuven Curated Import

**Branch:** `F02-princeton-import` · **Date:** 2026-07-23 · **Merge:** NOT merged

## What shipped
`PrincetonConnector` (family `princeton_leuven`) on the F02 framework — a BATCH
importer over LOCAL per-sector CSVs (`domain,category,last_updated,policy_text`) from
`PRINCETON_EXTRACT_DIR`. Registered in `registry.CONNECTORS`; run via
`scripts/ingest/run_princeton.py` (`--dry-run` / `--limit N` / full).

Per CSV row:
- **`source_record`** (`source_type='dataset'`, reliability_tier=2 in `notes`)
  capturing the dataset name + snapshot id (`= last_updated`, e.g. "2019B") and
  **truthful freshness** (see below). Raw policy text stored under
  `raw-artifacts/princeton_leuven/…`.
- **Org resolution:** existing org via `organization_alias` (domain) or
  `organization.domain`; no match → a **benchmark-only** organization (`tenant_id
  NULL`, `name=domain`, **`origin='princeton_leuven'`**) + a domain alias carrying the
  dataset `source_record_id`.
- **`privacy_notice`** (`notice_type='dataset'`, `effective_date`=snapshot date)
  linked to that org. The notice text is decomposed + classified by the EXISTING
  pipeline function `intake.decompose.decompose()` — the same code path customer
  intake uses (`assessments.py` calls the identical function) — **not forked or
  modified**; the resulting `notice_section`/`disclosure_clause` rows are persisted
  with the same payload shape as the intake router.

## Freshness honesty (CQS gating)
The `corpus_quality` table does not exist in live, so freshness is recorded on
`source_record`: `freshness_weight` **decays linearly to 0 over 5 years**, so a 2019
snapshot in 2026 lands at **0.0**, and `privacy_notice.effective_date` is the real
~2019 date. This lets the existing CQS gating (F02 §9, CQS < 75) exclude these from
**ACTIVE** benchmark populations. **This importer writes NO `benchmark_membership`
rows** — cohort building stays with the F03 job (asserted in tests, static +
behavioral).

## Dedupe + idempotency
Natural key = `{domain}::{sha256(policy_text)}`, so the framework **skips** any row
whose (domain, policy-text hash) already has a source_record: duplicate texts for a
domain collapse, distinct texts for a domain are kept, and re-loading the same
snapshot adds **zero** new source_records / notices. Malformed rows (missing
domain/text) are counted + flagged (partial run), never silently dropped.

## Framework additions (backward-compatible)
- `RawItem.source_record_extra` — dataset connectors add truthful
  `freshness_weight`/`notes`/`effective_date`/`update_date` to the `source_record`.
- (from the prior state-AG task) `RawItem.extraction_confidence`, `Connector.raw_folder`.

## Schema
- **0028** — `organization.origin` (nullable text, e.g. `'princeton_leuven'`) — applied
  + recorded to live.

## Licensing guard
`app/services/ingestion/connectors/README.md` (new) states the corpus's **research-use
licensing must be verified before any commercial benchmark or publication use**;
current use is **internal training/evaluation pending that verdict** (an open
decision — expert/legal). The importer's no-`benchmark_membership` behavior enforces
this technically until the verdict lands.

## Tests — `tests/test_princeton_connector.py` (9; committed fixture `princeton_sample.csv`, 5 rows across sectors)
Golden CSV import (5 notices, `source_type='dataset'`, freshness 0.0, tier-2 notes,
sector spread) · freshness-truthful · **org-resolution vs benchmark-only creation** ·
**dedupe** (same domain+text collapses; distinct text kept) · **idempotent re-run**
(0 new) · **no-`benchmark_membership`-writes** (static + behavioral) · malformed rows
flagged-not-dropped · connector registered. `FakePrincetonWriter` in the test module.

**Full suite: 722 passed, 15 skipped, 0 failed.**

## Live run — BLOCKED ON INPUT (per engineer, 2026-07-23)
The per-sector CSVs do **not exist yet** — the engineer is generating them locally
from the privacy-policy-sector-extract project and will set `PRINCETON_EXTRACT_DIR`
when ready. Per their instruction, the live pilot/import is **deferred**: connector
code + fixture-based tests are landed and green; nothing was run against live for this
family. When the CSVs arrive: `run_princeton.py --dry-run`, then `--limit 200`
(per-sector + clause counts + confidence distribution), STOP for go-ahead, then full
import.

## Needs human
- **Provide the per-sector CSVs** at `PRINCETON_EXTRACT_DIR` (healthcare, fintech,
  retail, education, entertainment) so the `--limit 200` pilot can run.
- **Research-use licensing verdict** (expert/legal) before any commercial/benchmark/
  publication use — see connectors/README.md.
