# PHASE 3 — Config Capture, Data Integrity & Product Completeness — Completion Record

**Date:** 2026-08-04 · **Commit before:** `8c4ed92` · **Commit after:** working tree, **no commits / no branch** per owner instruction (conflicts with `AGENTS.md` §1.4/§1.7 — logged in `logs/decision-log.md`).

## Findings addressed
| ID | What changed | Files | Tests | Status |
|---|---|---|---|---|
| ARCH-001A | (Delivered in **Phase 3A** — industry + jurisdiction captured & consumed, manual DB pre-step removed.) | see PHASE3A-INTAKE-FILTERS-DONE.md | 11 backend + 2 web | **TESTED** |
| ARCH-001B | Honest increment: **scope-preview (step 6)** on intake — a live plain-English "Analysis scope" summary (benchmark cohort, state-law exposure, declared-by-you vs detected-from-notice). Only reflects inputs the engine consumes. **Deferred (documented below):** data-practice declaration (engine DETECTS these, doesn't consume declarations), competitor/benchmark-population selection, B2B/B2C/sector (not consumed) — adding them would be saved-and-ignored ("a lie by omission"). | `web/src/pages/customer/Intake.tsx`, `intake.css` | web gate (renders) | **PARTIALLY FIXED** (scope-preview shipped; full wizard deferred as non-consumed) |
| QA-012 | Intake now discloses processing/retention/confidentiality: processed on Visentix infra, **not** sent to third-party AI / **not** used to train third-party models, de-identified aggregate reuse, retention per Privacy Policy (link). Wording matches the owner-approved notice (decision-log 2026-07-28) — no invented legal promises. | `web/src/pages/customer/Intake.tsx` | web gate (renders) | **RESOLVED** |
| QA-013 | **Deferred, not faked.** The snapshot carries no alternative-register narrative (the `ExecutiveSummary.tsx` register tabs are a read-side stub shown only "when alternatives exist"; backend supplies none). A selector would be decorative → per the "no decorative buttons" rule, NOT added; flagged in `logs/decision-log.md` (needs backend per-register narrative + a product/spec decision). | (none — documented) | — | **DEFERRED (documented)** |
| FIND-001 | **Governed — left UNCHANGED.** `DECISION-NEEDED.md` §2.7 parks `enforcement_matches` as an SME decision and ends "STOP — awaiting approval"; no spec resolves it. Behaviour not changed; exact approval + spec-update path flagged in `logs/decision-log.md`. | `logs/decision-log.md` (flag only) | — | **BLOCKED — SME APPROVAL** |
| DATA-001 | `benchmark_population_version` is now a canonical, deterministic identity — SHA-256 of `sorted(member_org_ids)` + cohort key + member profile-versions + corpus version, masked to a stable positive int32 (matches the `report_snapshot.benchmark_population_version` integer column; survives `str()` for the `derived_data_item` text column). Wall-clock removed. | `app/services/benchmark/population.py` | `tests/test_data001_population_version.py` (6) | **TESTED** |
| DATA-002 | `_content_hash` now hashes only meaningful immutable content: a recursive `_canonicalize_for_hash` strips volatile keys (`date`, `generated_date`, `cohort_date`, `snapshot_id`, derived date-bearing prose) and all `_*` runtime metadata before canonical `json.dumps`. Byte-identical scores hash identically across days/snapshots; any content change still changes the hash. **Existing determinism tests preserved.** | `app/routers/reports.py`, `app/services/report/assembly.py` (comments) | `tests/test_data002_content_hash.py` (4) + `test_report_reproducible.py` + `test_pdf_determinism.py` = 14 pass | **TESTED** |
| DATA-003 | Every fabricated VCI/confidence `75` removed (`RegulatorExposure.tsx`, `FindingsTable.tsx`). Real `vci_score`/`confidence` threaded; absent → honest absence ("—"/"Not recorded"), never a number. Supporting components (`ScoreCell`, `LineageDrawer`, `AdvisorNote`) now tolerate `undefined`. `explain.py:62` `>=75` is a real band threshold — correctly left. | web report sections + 3 components | `web/src/test/vci_absence.test.tsx` (7) | **TESTED** |
| DATA-004 | Data-safe additive FK migration: `risk_finding.organization_id`, `.notice_id`, `report_snapshot.organization_id`, `organization_intelligence_profile.organization_id` FKs added **`NOT VALID`** (enforce new rows, never fail on / destroy legacy orphans), idempotent via `pg_constraint` guards. Orphan-audit SQL provided; `VALIDATE`+`NOT NULL` tightening deferred to after a live-data audit. | `db/migrations/0045_org_notice_fks.sql`, `scripts/db/audit_data004_orphans.sql`, `scripts/db/apply_and_record.py` | migration lints; prod apply BLOCKED | **IMPLEMENTED** (prod apply + VALIDATE = BLOCKED-EXTERNAL) |
| AI-002 | `_chat` retry set now catches `httpx.HTTPStatusError` but retries **only 429 + 5xx** (other 4xx re-raised immediately, no backoff burned); existing timeout retries + backoff bounds preserved. Fallback now returns an **honest DEGRADED** result (`{"category":"other","confidence":0.0,"degraded":True}`) instead of the old dishonest `confidence:0.5`, so lineage can tell a keyword fallback from a real AI label. | `app/services/llm.py` | `tests/test_llm_retry_taxonomy.py` (10) + 20 llm tests | **TESTED** |
| AI-004 | Classifier prompt now injects one-line definitions per category from `config/clause_taxonomy.json` (single source of truth, not forked into llm.py), deterministic order, versioned `CLASSIFY_PROMPT_VERSION="classify-taxonomy-v2"`; degrades to bare slugs if config missing. Structured-output validation preserved; **no accuracy claim** (comment defers to F17/EVAL-001). | `app/services/llm.py` | (in the 10 above) | **TESTED** |
| BACK-002 | Alerts made replay-safe: `content_hash` advance issued FIRST and independent of delivery; `(notice_id, new_hash)` dedupe (`_already_alerted`) prevents re-alert on a crash-before-patch replay; each `deliver_for_event` wrapped so a delivery failure is logged (not swallowed) and never blocks the hash advance or aborts the run. | `app/services/jobs/monitor_notices.py` | `tests/test_back002_idempotent_alerts.py` (3) + 19 monitor tests | **TESTED** |
| FE-001 | Bare `<a href>` PDF download replaced with the authenticated-blob pattern (`api.getBlob` → objectURL → click → revoke) from QuarterlyReport/PartnerPortal; loading + honest status-specific errors (403/404/other). | `web/src/pages/ReportPage.tsx` | `web/src/test/report_page_download.test.tsx` (4) | **TESTED** |

## Prior-QA status (QA-001…QA-014) after Phase 3
| QA | Item | Status |
|---|---|---|
| QA-001 | Org profile capture | **PARTIAL** — industry + jurisdiction captured (ARCH-001A); size/practices deferred (non-consumed) |
| QA-002 | Industry selection | **RESOLVED** (3A) |
| QA-003 | State/legal scope | **RESOLVED** (3A) |
| QA-004 | Data-category config | **Unchanged** — engine DETECTS from notice; declaration deferred (would be non-consumed) |
| QA-005 | Data-practice config | **Unchanged** — DETECTED, not declared |
| QA-006 | Benchmark selection/confirmation | **PARTIAL** — auto-built + now disclosed pre-run in the scope-preview |
| QA-007 | Use-case / report-mode | **OPEN** — tied to QA-013 (deferred) |
| QA-008 | Scope preview before processing | **RESOLVED** — scope-preview (ARCH-001B step 6) |
| QA-009 | PDF output | **RESOLVED** (P2) + authenticated download (FE-001) |
| QA-010 | Processing flow | **RESOLVED** (P2 async) |
| QA-011 | Progress/timeout/retry | **RESOLVED** (P2 async polling) |
| QA-012 | Processing disclosure | **RESOLVED** (this phase) |
| QA-013 | Audience/template modes | **DEFERRED (documented)** — no decorative button |
| QA-014 | Config drives output | **PARTIAL** — proven for industry/jurisdiction (ARCH-001A behavioural tests); full data-practice declaration deferred |

## Gate (vs baseline)
```
cd web && npx tsc --noEmit → 0
cd web && npx vitest run    → Test Files 11 passed (11) · Tests 94 passed (94)   [+11 vs Phase 3A's 83: FE-001 4, DATA-003 7]
cd web && npm run build     → 0
./.venv/bin/python -m pytest -q → 4 failed, 1007 passed, 15 skipped in 200.51s (exit 1)
```
### Full backend suite
- **Phase 3A:** `983 passed, 5 failed, 15 skipped`.
- **Phase 3:** `1007 passed, 4 failed, 15 skipped` (+24 passing). New backend tests: DATA-001 (6), DATA-002 (4), BACK-002 (3), AI-002/004 (10). **Failure accounting (all explained; no code regression):** 2 environmental live-DB (`test_embeddings::test_disclosure_clause_embedding_dim`, `test_schema_p1[disclosure_clause]` — PostgREST 500 statement-timeout, variance) + 2 migration-ledger (`test_f02_ingestion_foundation::test_schema_migrations_rows_match_file_checksums`, `::test_apply_now_order_and_step_a_first` — now covering 0043/0044/**0045**, all registered-but-not-applied per the owner's Leave-BLOCKED-EXTERNAL choice; they go green when the migrations are applied).

## Migrations (all additive/idempotent; introspected against the committed live schema first)
- `0045_org_notice_fks.sql` — FKs `NOT VALID` (data-safe). Prod apply = external: `PYTHONPATH=. ./.venv/bin/python -m scripts.db.apply_and_record`; then run `scripts/db/audit_data004_orphans.sql`, repair any offenders, and `VALIDATE CONSTRAINT` + tighten `NOT NULL`. Verify constraints via `pg_constraint`.
- (0043/0044 from earlier phases also pending apply.)

## BLOCKED — EXTERNAL
1. Apply migrations 0043/0044/0045 to the live DB (one `apply_and_record` run) → clears the 2 migration-ledger test reds + makes async intake / industry_source / FKs live.
2. DATA-004 `VALIDATE CONSTRAINT` + `NOT NULL` tightening — after the orphan audit (needs live DB).
3. FIND-001 — SME ruling (see decision-log); implement via spec-update after approval.
4. (Carried) EVAL-001 F17 labels + backfill; SEC-007/CRED-001 rotations.

## Notes for the next prompt (Phase 4)
- SEC-005/006/008, SEC-009/010/011, BACK-003, DB-001/002, MAINT-001, AI-003 remain.
- SEC-003 full RLS still its own item.
- ARCH-001B full wizard + QA-013 audience modes + FIND-001 need product/SME/spec decisions before more code.
