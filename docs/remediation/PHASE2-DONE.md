# PHASE 2 — Core Guarantees Made Real — Completion Record

**Date:** 2026-08-04 · **Commit before:** `8c4ed92` · **Commit after:** working tree, **no commits / no branch** per owner instruction.
**Standing-rule conflict (repeated per Prompt-0 rule 3):** no-branch/no-commit conflicts with `AGENTS.md` §1.4/§1.7 — logged in `logs/decision-log.md` (2026-08-04); human to reconcile before shipping.

## Findings addressed

| ID | Root cause confirmed | Files changed | What changed | Tests added | Test result | Status |
|---|---|---|---|---|---|---|
| GRD-001 | Yes — guardrail never ran on the report path; prose built inline in reports.py | `app/routers/reports.py`, `app/services/report/assembly.py` | New `_enforce_snapshot_prose()` runs the ONE canonical `guardrail.enforce()` over every generated string entering a snapshot (exec summary, takeaways, each recommendation title + `body_template`), **fails closed** on a banned term, and records the real result into Section-11 lineage (`{"status":"passed","strings_checked":N}` or `not_recorded`). Source/peer clause text is NOT enforced (cited evidence, exempt per spec). | `tests/test_guardrail_report_path.py` (6): clean passes; banned term in body_template / exec / a contraction takeaway all fail closed; lineage records result / defaults not_recorded | 6 passed | **TESTED** |
| GRD-002 (integration) | — | (Phase 1 fix) | GRD-001 now feeds a REAL guardrail result into snapshot lineage, so the honest receipt reports fact instead of `not_recorded` once a snapshot is built. | (Phase-1 tests) | **TESTED** |
| FUNC-001 | Yes — center panel hardcoded, Submit/Clear dead | `web/src/pages/sme/ReviewQueue.tsx` (rewritten), `web/src/test/ReviewQueue.test.tsx` (new) | Deleted every literal (`C-118`, `SH-002`, `PLACEHOLDER_CLAUSE`, `72.4`, `81%`, `74th`). Panel driven by the selected `/review/queue` item: findings from `GET /findings/` (filtered by notice_id, sme/admin platform view), clause text from `GET /assessments/{id}/clauses`, codex titles from `/findings/codex`. Confirm/Edit/Dismiss capture the advisor note and POST `/review/finding/{aid}/{fid}`; **Submit Review** now POSTs `/review/{aid}/approve` (double-submit guarded); **Clear** clears the unsaved decision. Metrics not exposed per-finding by any endpoint (Exposure/VCI/percentile) render **honest absence ("—")**, never filler. | web: `ReviewQueue.test.tsx` (6) — real finding renders, no fabricated literals, Confirm + Submit POST correctly; backend: `test_org_isolation.py` — customer role → 403 on all SME review routes | web 81/81; backend role tests pass | **TESTED** |
| QA-011 | Yes — synchronous intake exceeds browser/proxy timeouts | `app/routers/assessments.py`, `app/services/intake/jobs.py` (new), `db/migrations/0043_assessment_job.sql` (new), `web/src/pages/customer/Intake.tsx` | New async layer, **non-breaking**: `POST /assessments/async` creates an `assessment_job` (server state), returns **202 + job handle**, runs the pipeline in a background task with per-stage updates (`fetching→extracting→segmenting→classifying→scoring→complete/failed`); `GET /assessments/{id}/status` returns stage/status (org-ownership enforced) so a **browser refresh recovers progress**. **Idempotency key** dedupes double-submit/retry → no duplicate assessment. Sync `POST /assessments/` kept intact (partner path + QA-010 preserved). Frontend polls with bounded backoff, shows stage + elapsed + safe retry, routes onward on complete. | `tests/test_intake_async.py` (7): 202 + job handle; requires input; idempotent replay (no dup); runner records stages + completes; failed extraction → failed; status returns progress; 404 + cross-org 403 | 7 passed | **IMPLEMENTED** (prod migration 0043 apply = BLOCKED-EXTERNAL) |
| BACK-001 | Yes — `running` treated as liveness forever; no reaper | `app/services/jobs/framework.py`, `app/routers/admin.py`, `app/main.py` | `is_running` now counts only rows started within a per-job max runtime; `reap_stale_runs()` marks orphaned `running` rows `failed`; `execute`/`trigger_background` reap before the guard (self-healing); startup reaper in the lifespan; `stale_job_runs` surfaced on `/admin/status`. | `tests/test_jobs_reaper.py` (4): stale excluded from is_running; reaper marks failed; job not blocked by orphan; stale count | 4 passed | **TESTED** |
| SEC-002 | Yes — validated IP ≠ connected IP (re-resolve) | `app/services/intake/ssrf.py`, `app/services/intake/extract.py` | `resolve_and_validate()` resolves once, validates every address, returns a pinned IP; the fetch uses a custom httpx network backend (`_PinnedResolverBackend`) that dials the pinned IP while TLS SNI + cert verification stay on the hostname — closing the DNS-rebinding TOCTOU. Per-redirect re-validation preserved (and now re-pins each hop). | `tests/test_ssrf.py` (29, shared w/ SEC-004) incl. pinned-backend dials IP, redirect-to-private rejected | 29 passed | **TESTED** |
| SEC-004 | Yes — no port allowlist; IPv6 gaps | `app/services/intake/ssrf.py` | Port allowlist `{80,443}`; reject IPv4-mapped IPv6 + IPv6 ULA (fc00::/7) + multicast/unspecified explicitly; hostname normalization (lower/strip-dot/IDNA). `validate_url` (used by discover/connectors) inherits the hardening. | (in `test_ssrf.py`) blocked IPs/ports/mapped-v6/ULA, round-robin rebinding rejected, valid HTTPS passes | 29 passed | **TESTED** |
| EVAL-001 | Yes — 0/200 gold labels; harness never run | (no code change; investigated + runbook) | Verified the F17 harness, gold-set migration, and round-trip endpoints all exist; the 200-clause gold set is **unlabelled** (FILL columns blank) and the harness correctly returns "awaiting SME labels" — it fabricates nothing. Exact labelling + run runbook and embedding-backfill runbook documented (below). | n/a (measurement gated on SME labels) | — | **BLOCKED — EXTERNAL** (F17 accuracy: SME labels; backfill: long GPU/CPU compute) |
| SEC-003 (full) | Yes — service-role bypasses RLS | (deferred; Phase-1 backstop stands) | Architectural DB-client split (`get_user_db(jwt)` under RLS) **deferred** — see below. Phase-1 `customer_org_scope` + the cross-tenant contract test remain the interim backstop; the backend sweep found no leaks beyond SEC-001. | (Phase-1 contract test) | — | **PARTIALLY FIXED** (min path holds; full RLS deferred) |

## Tests run (verbatim commands + real counts)
```
# targeted (during dev, all green):
pytest tests/test_jobs_reaper.py           → 4 passed
pytest tests/test_ssrf.py                  → 29 passed
pytest tests/test_guardrail_report_path.py → 6 passed
pytest tests/test_intake_async.py          → 7 passed
pytest tests/test_org_isolation.py tests/test_jobs_reaper.py tests/test_ssrf.py \
       tests/test_guardrail_report_path.py tests/test_intake_async.py \
       tests/test_guardrail.py tests/test_explain.py → 122 passed, 3 skipped
pytest tests/ -k "intake or extract or discover or connector" → 162 passed (SSRF-refactor regression check)

# frontend gate:
cd web && npx tsc --noEmit   → TSC_EXIT=0
cd web && npx vitest run     → Test Files 8 passed (8) · Tests 81 passed (81)   [75 baseline + 6 FUNC-001]
cd web && npm run build      → BUILD_EXIT=0

# full backend gate:
./.venv/bin/python -m pytest -q → 4 failed, 973 passed, 15 skipped in 246.83s (exit 1)
```

### Full-suite comparison to `00-BASELINE.md`
- **Baseline:** `910 passed, 3 failed, 15 skipped` (3 failures pre-existing/environmental — live-Supabase PostgREST 500 statement-timeout + low embedding coverage).
- **Phase 1:** `925 passed, 2 failed, 15 skipped`.
- **Phase 2:** `973 passed, 4 failed, 15 skipped` (+63 passing vs baseline). New tests added this phase: SSRF 29, async intake 7, guardrail-report-path 6, jobs-reaper 4, org-isolation +9 (FUNC-001 role + no-org + contract). The 4 failures decompose as 2 environmental + 2 migration-pending-external (below).
- **Failure accounting (every red explained):**
  - **Pre-existing / environmental (same class as baseline):** `test_embeddings::test_disclosure_clause_embedding_dim`, `test_embeddings::test_nn_search_returns_results`, `test_schema_p1::test_corpus_tables_nonempty[disclosure_clause]` — live-Supabase PostgREST 500 statement-timeout (`error=57014`) + low embedding coverage. These vary run-to-run (Phase 1 saw 2 of the 3).
  - **New, but EXPECTED and EXTERNAL (owner chose "Leave BLOCKED-EXTERNAL"):** `test_f02_ingestion_foundation::test_schema_migrations_rows_match_file_checksums` and `::test_apply_now_order_and_step_a_first`. These live-DB ledger tests compare `APPLY_NOW` against the applied `schema_migrations` ledger; migration **0043 is registered but deliberately not applied to prod**, so they fail with "0043 applied but not recorded". They go green the moment 0043 is applied (BLOCKED item 1). This is NOT a code defect and NOT a weakened test — it is the honest "migration prepared, prod-apply pending" state.
  - **No other new failures.** `test_schema_migrations_manifest_partitions_all_files` was momentarily red (0043 unregistered) and is now green (0043 added to `APPLY_NOW` in `scripts/db/apply_and_record.py`).

## New/changed migrations
- **`db/migrations/0043_assessment_job.sql`** — NEW. **Additive** (one new table), **idempotent** (`IF NOT EXISTS`), **RLS-on + anon/authenticated revoked** (matches 0042). No changes to existing tables. Registered in `scripts/db/apply_and_record.py` `APPLY_NOW`. **NOT applied to prod** (owner: Leave BLOCKED-EXTERNAL) — see BLOCKED item 1; two live-DB ledger tests fail until it is applied.

## BLOCKED — EXTERNAL ACTION REQUIRED
1. **QA-011 — apply migration 0043 to the live DB.** *Reason:* the async-intake feature needs the `assessment_job` table; applying to prod is an external DB step. *Steps:* `cd <repo> && PYTHONPATH=. ./.venv/bin/python -m scripts.db.apply_and_record` (idempotent; records checksum in `schema_migrations`). *Verify:* `select to_regclass('public.assessment_job');` returns non-null AND `select count(*) from schema_migrations where filename='0043_assessment_job.sql';` = 1. Applying it also turns the two live-DB ledger tests (`test_schema_migrations_rows_match_file_checksums`, `test_apply_now_order_and_step_a_first`) green. Until applied, `/assessments/async` + `/status` return honest errors (never fabricated success); the synchronous `POST /assessments/` path is unaffected.
2. **EVAL-001 (a) — F17 accuracy.** BLOCKED on SME labels (0/200). *Steps:* `GET /eval/gold-set/export.csv` (sme/admin JWT) → SME fills `gold_domain(FILL)` in `logs/eval/gold_set_v1.csv` → `POST /eval/gold-set/import.csv` → `PYTHONPATH=. python scripts/eval/classifier_eval.py` → `PYTHONPATH=. python scripts/eval/report.py`. *Verify (before trusting any number):* `SELECT count(*) FROM gold_label WHERE gold_domain IS NOT NULL AND gold_set_version='v1';` must be > 0. Runnable now WITHOUT labels: `pytest tests/test_f17_eval.py tests/test_f17_score_validity.py`.
3. **EVAL-001 (b) — embedding backfill (~11.5% → full).** Runnable (CPU/MPS ok, GPU 5–20× faster) but a long compute job over the live corpus — NOT triggered unprompted. *Steps:* `PYTHONPATH=. python scripts/embed_backfill.py --estimate` then `--tranche all` (idempotent, resumable via checkpoint). *Verify:* `PYTHONPATH=. python -c "from scripts.embed_backfill import coverage; e,n=coverage('disclosure_clause'); print(f'{e}/{n} ({e/n*100:.1f}%)')"`. (Unblocks Part-B `clause_obligation` at ≥95%.)
4. **SEC-007 / CRED-001 rotations** — still external (see PHASE1-DONE.md §BLOCKED). Unchanged this phase.

## AGENTS.md / spec / doc changes
- No spec/behavior version bumps required. GRD-001/003 make the guardrail *match* `business-logic.md` §2.
- `docs/remediation/REMEDIATION-MATRIX.md` — Status updated in place for GRD-001, FUNC-001, QA-011, BACK-001, SEC-002, SEC-004.

## SEC-003 (architectural) — explicit deferral
The full `get_user_db(jwt)` / `get_service_db()` / `get_admin_db()` split (customer reads under the user JWT so RLS fires) is **deferred to a dedicated follow-up** — it is a broad, high-risk migration touching every customer-facing query and is best done as its own reviewed change, not squeezed into this phase alongside five other fixes. **Interim backstop (holds):** the Phase-1 `app/services/tenancy.py::customer_org_scope` helper + the cross-tenant contract test in `tests/test_org_isolation.py` (with the `CAPTURE_ROUTES` seam), plus the Phase-1 sweep confirming no cross-tenant leaks beyond SEC-001. **Migrated onto the helper:** `GET /findings/` + `/findings/dashboard-stats`. **Pending migration to a real user-JWT/RLS path:** all other customer-reachable routes (assessments list, reports/{id}, explain, monitoring, notifications) — today safe via per-route org filters / ownership checks (verified by the sweep), but not yet behind RLS.

## Regressions introduced & fixed
- SSRF refactor: re-ran all intake/extract/connector tests → 162 passed, no regression. The fetch now injects a pinning transport but is test-injectable (MockTransport) and preserves per-redirect re-validation.
- GRD-001: `_assemble_from_live` now enforces the guardrail; authored `recommendation_library` templates are clean, so normal report builds pass. A poisoned template now (correctly) fails the build closed.
- `run_assessment_intake` gained an optional `on_stage` callback (default None) — synchronous callers (partner route, existing tests) behave identically.
- Full-suite result: `973 passed, 4 failed, 15 skipped`. The 4 failures = 2 environmental live-DB (variance) + 2 migration-0043-pending-external (owner chose Leave BLOCKED). No unexplained regression; +63 passing vs the 910 baseline.

## Notes for the next prompt (Phase 3)
- Apply migration 0043 (above) to make async intake live.
- SEC-003 full is the biggest remaining architectural item — treat as its own prompt.
- ARCH-001 (config-capture intake) is the Phase-3 headline; the new async intake + `assessment_job` give it a natural place to add captured org profile/jurisdiction fields.
- DATA-001/002/003, FE-001, AI-002/004, SEC-005/006/008, BACK-002, DATA-004, FIND-001 remain per the roadmap.
