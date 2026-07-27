# F02 — Corpus Ingestion & Source Monitoring Pipelines

**Status:** partial — customer intake shipped; registry-driven connector framework proposed (v2) · **Spec version:** 2 · **Release:** R2 · **Depends on:** F01, schema.md §2.2/2.5/2.9, business-logic.md §7, intelligence-logic.md §11

## Purpose
Build and maintain the benchmark corpus and regulator/enforcement/security knowledge that all four products depend on: registry-driven crawls of peer notices and public sources, weekly enforcement ingestion, breach-report capture, state-law catalog updates, hash-based change detection, and versioned source records with reliability scoring.

## Data
Writes: `source_registry`, `ingestion_run`, `parser_version`, `source_record`, `source_version`, `corpus_quality`, `enforcement_record`, `litigation_event`, `obligation`, `state_law_weight`, `monitoring_event`, `security_event`, `organization_alias`, and (for notice-bearing sources) `privacy_notice` / `notice_section` / `disclosure_clause` via the F01 intake pipeline. Reads: `source_registry` (living config, not code). Raw bytes: `raw-artifacts` storage bucket.

---

## Current state (baseline — what already ships)

**Customer intake (shipped, F01).** URL/PDF/text upload → SSRF-validated fetch → extraction → decomposition into clauses. Unchanged by this spec.

**Four existing ingestion scripts (the current-state baseline).** These already populate the corpus and are the parsing logic the connector framework must **reuse, not replace**:

| Script | External source | Populates |
|---|---|---|
| `scripts/batch_assess.py` | Live peer privacy-policy URLs, run through the F01 pipeline | `organization`, `privacy_notice`, `notice_section`, `disclosure_clause` (+ downstream) |
| `scripts/ingest/ingest_enforcement.py` | FTC cases (scrape) + CourtListener API | `enforcement_record` |
| `scripts/ingest/ingest_legal_refs.py` | eCFR, EUR-Lex/gdpr-info, state legislature sites | `legal_reference`, `finding_legal_reference` |
| `scripts/ingest/ingest_state_laws.py` | OpenStates API + state bill URLs | `obligation`, `legal_reference` |

**Migration onto the framework (requirement, not a rewrite):** each connector below MUST call the existing script's parsing/normalization functions rather than re-implementing them, and the scripts must be moved onto the connector framework (single run-logging + raw-store path), **not** left to parallel-run against it. Duplicate/parallel ingestion of the same family is a defect.

## Prerequisites (Phase-1, must land before connector runs)
1. **Apply migration 0014** (organization + organization_intelligence_profile enrichment/tier columns) to live — authored but not applied (schema.md §5.1). Entity resolution and profiling depend on it.
2. **Apply migration 0017** (report_snapshot `rendered_report` / `content_hash` / versioning) to live — **CRITICAL**: Hard Rule 6 immutable-snapshot reproducibility is not physically backed until this lands (schema.md §5.1).
3. **Create `schema_migrations`** and backfill it for already-applied migrations, then adopt the rule: no migration counts as applied without a row there (schema.md §5.2).

Authorization to apply 0014 and 0017 to live is requested as a Phase-1 step — see open-decisions.md / approval summary "Needs human."

---

## Behavior (v2)

### 1. Source registry contract
`source_registry` (schema §2.9) is the single configurable list of source families. Each row: `family`, `display_name`, `base_url`, `cadence` (manual/daily/weekly/monthly), `reliability_tier` (1–3), `parser_type`, `enabled`, `config` (jsonb). Connectors read the registry at run time — **families are data, never hardcoded**. Disabling a family (`enabled=false`) stops its crawl without a code change. Cadences mirror the SLA targets in business-logic §7.

### 2. Family taxonomy (absorb existing, then extend)
The `raw-artifacts` bucket **already** organizes bytes by family folder. v2 **adopts these existing folders as the canonical family taxonomy** and extends them; it never renames or moves existing objects.

- **Existing families (in use today):** `ag_actions`, `cfpb`, `cppa`, `frameworks`, `ftc`, `litigation`, `notices`, `state_laws`.
- **New families added by v2:** `hhs_ocr`, `sec_edgar`, `princeton_leuven`, `open_web`.

⚠️ **OPEN QUESTION (OD-07-adjacent, engineer):** `source_registry.family` enum values (`sec_edgar, hhs_ocr, ftc, cppa, state_ag, princeton_leuven, open_web`) do not map 1:1 to the folders — `state_ag` vs folder `ag_actions`, and folders `cfpb`/`frameworks`/`litigation`/`notices` have no enum value yet. Reconcile the enum with the folder set before the first connector run; do not silently pick a mapping.

### 3. Connector lifecycle (every connector, every run)
`fetch → hash → raw-store → parse → normalize → upsert`:
1. **fetch** — pull the source per `base_url`/`config`; SSRF rules from AGENTS.md §3 apply to any URL fetch.
2. **hash** — compute `content_sha256` over the fetched bytes.
3. **raw-store** — write the raw bytes to `raw-artifacts/{family}/{YYYY}/{MM}/{content_sha256}.{ext}` (see §4). Applies to **new objects only**.
4. **parse** — run the family parser (reusing the baseline script's logic); record `parser_version_id`.
5. **normalize** — map to canonical rows (`source_record` + the family's target table).
6. **upsert** — write with conflict keys so re-runs are idempotent (§5).

### 4. Raw-artifact path convention
New raw objects are stored at:
```
raw-artifacts/{family}/{YYYY}/{MM}/{content_sha256}.{ext}
```
`{YYYY}`/`{MM}` = capture year/month; `{content_sha256}` = the §3 hash; `{ext}` = source format (html/pdf/json/txt). **Existing objects are never moved or renamed to fit this convention** — it governs new writes only (AGENTS.md §2: the bucket is read-only for existing files).

### 5. Idempotency rule
Re-ingesting a source whose **content hash is unchanged produces ZERO new rows** — no new `source_record`, no new `source_version`, no new raw object (the `content_sha256` path already exists). The run is still logged (§7) with `records_new = 0`.

### 6. Change detection
When a monitored source's content hash **differs** from its latest stored hash: create a new `source_version` (schema §2.2), run a section-level diff, tag changed sections by disclosure domain, and set the Material Change Indicator when a regulator-sensitive category changed. A hash diff is the **only** trigger for a new version.

### 7. Run logging
Every connector execution writes one `ingestion_run` row (schema §2.9): `registry_id`, `started_at`/`finished_at`, `outcome` (ok/partial/failed), `records_seen/new/changed/skipped`, `error_summary`, `parser_version_id`. Logs record counts and IDs only — **never** full source text or secrets (AGENTS.md §3). No run may write corpus rows without a corresponding `ingestion_run` row.

### 8. Failure & retry behavior
Transient (network/5xx) failures retry with backoff (bounded attempts); on final failure the run is closed `outcome=failed` with a non-secret `error_summary`, and **no partial-but-unlogged writes** are left behind. Ambiguous/failed extractions are routed to review, never silently included (extraction confidence recorded per capture). A failed run must be safe to re-run (idempotency, §5).

### 9. Quality gating & tiering
Compute F-001 Source Reliability and CQS; **CQS < 75** excludes a source from active `benchmark_membership` (retained for trend history / routed to review). Tier 1 authoritative / Tier 2 legal-dispute / Tier 3 contextual, with the minimum metadata sets from VICBNF §3.2. (No formula weights are introduced or changed by this spec.)

### 10. Downstream triggers (unchanged, per intelligence-logic §11)
Enforcement ingest → F-004 recalc queue; law change → obligation/weight update; notice change → rescore affected customer assessments + emit `monitoring_event`. ⚠️ **`security_event` is explicitly OUT of this chain:** breach reports do **not** feed F-004 or any enforcement formula (schema §2.9 rationale; OD-06).

## API contracts
- `POST /api/admin/sources` — CRUD on `source_registry` (admin).
- `POST /api/admin/ingest/run` — manual trigger per family (admin).
- Internal queue/scheduler (cron or worker) — implementation free, but every run logs `registry_id`, hash, outcome to `ingestion_run`.

## Guardrails & confidence
Extraction confidence recorded per capture; ambiguous/failed extractions routed to review. US-only Phase 1; non-US sources tagged future-state only. Security/breach language stays register-appropriate (AGENTS.md Hard Rule 9) and never uses legal-verdict vocabulary (Hard Rule 1).

---

## Acceptance criteria

### General (all connectors)
- **AC-G1 (idempotency):** Running any connector twice with unchanged upstream content creates zero new `source_record`/`source_version`/raw objects; both runs appear in `ingestion_run`, the second with `records_new = 0`. *(Check: row counts before/after + two run rows.)*
- **AC-G2 (change detection):** Changing one monitored source's content yields exactly one new `source_version` with a domain-tagged diff and (for notice sources) a `monitoring_event`. *(Check: `source_version` count +1, diff row present.)*
- **AC-G3 (raw path):** Every new raw object matches `raw-artifacts/{family}/{YYYY}/{MM}/{sha256}.{ext}`; no pre-existing object was moved or renamed. *(Check: storage listing + object names vs `content_sha256`.)*
- **AC-G4 (run logging):** No corpus row is written by a connector without a matching `ingestion_run` row carrying `registry_id` and `parser_version_id`. *(Check: join written rows' run to `ingestion_run`.)*
- **AC-G5 (reuse):** Each connector invokes the corresponding baseline script's parser rather than a re-implementation, and the baseline script no longer runs in parallel for that family. *(Check: connector imports/calls the shared parser; scheduler has one entry per family.)*

### Per-source
- **AC-HHS_OCR:** A run against the HHS OCR breach portal writes one `security_event` per parsed breach (with `source_record_id` set, `resolution_status='unresolved'` default, `individuals_affected` populated when present) and writes **zero** rows to `enforcement_record`. *(Check: `security_event` count = parsed breaches in `ingestion_run.records_seen`; `enforcement_record` unchanged.)*
- **AC-SEC_EDGAR:** A run against SEC EDGAR writes `source_record` rows with `source_type='corporate_filing'` and creates/updates `organization_alias` rows of `alias_type` in {cik, ticker} with a `match_confidence`, without overwriting any existing `organization.name`. *(Check: alias rows present; org names unchanged pre/post.)*
- **AC-FTC:** A run against FTC cases writes `enforcement_record` rows with `source_type` set and `verified` populated, upserting on the enforcement key so re-runs add no duplicates; reuses `ingest_enforcement.py` parsing. *(Check: duplicate re-run adds 0 rows; parser is the shared one.)*
- **AC-CPPA:** A run against CPPA materials writes `source_record` (family `cppa`, appropriate `source_type`) and raw bytes under `raw-artifacts/cppa/...`; CQS < 75 items are excluded from `benchmark_membership`. *(Check: raw path prefix; excluded item absent from membership.)*
- **AC-STATE_AG:** A run against a state AG source writes to its resolved family folder and records the family–folder mapping decided in §2's OPEN QUESTION; AG breach-notification content routes to `security_event` (not `enforcement_record`). *(Check: folder used matches the decided mapping; breach rows in `security_event`.)*
- **AC-PRINCETON_LEUVEN:** A bulk load of the Princeton-Leuven policy dataset writes `source_record` rows with `source_type='dataset'` and feeds notices through the F01 pipeline into `privacy_notice`/`notice_section`/`disclosure_clause`; a second load of the same dataset snapshot adds zero new source records. *(Check: `source_type='dataset'` rows present; re-load `records_new=0`.)*
- **AC-OPEN_WEB:** An open-web peer-notice crawl reuses `batch_assess.py` intake, tags captured notices to family `open_web` raw storage, and resolves each captured org to an existing `organization` via `organization_alias` (domain) or creates a new peer org — never overwriting an existing org's canonical fields. *(Check: alias/domain match logged; existing org fields unchanged.)*

## Test gate
Change-detection unit tests (hash, diff, material-change flag); idempotency test (unchanged hash ⇒ 0 new rows); CQS gating test (provably excludes <75 from `benchmark_membership`); trigger-matrix integration test; run-logging test (no write without an `ingestion_run` row); `security_event`-never-touches-`enforcement_record` test (OD-06 guard).

## Changelog
- 2026-07-20: **v2 — ingestion architecture.** Added source-registry contract, connector lifecycle (fetch→hash→raw-store→parse→normalize→upsert), idempotency + change-detection rules, `raw-artifacts/{family}/{YYYY}/{MM}/{sha256}.{ext}` path convention (new objects only), run logging, failure/retry behavior, and per-source ACs (hhs_ocr, sec_edgar, ftc, cppa, state_ag, princeton_leuven, open_web). Documented the four existing scripts as the baseline connectors must reuse. Added Phase-1 prerequisites (apply migrations 0014 + 0017, create `schema_migrations`). Recorded `security_event` separation as OD-06 and the family/folder reconciliation as an OPEN QUESTION. Depends on schema.md v1.3 §2.9. No formula, weight, or scoring change. Source: engineer + `logs/audits/2026-07-data-layer-audit.md`.
- 2026-07-16: Added Changelog section for template conformance; no behavioral change.
