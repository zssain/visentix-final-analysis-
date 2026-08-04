# Visentix Remediation — FINAL REPORT

**Date:** 2026-08-04 · **Author:** Claude (engineer) · **Source of findings:** `Visentix-Codebase-Review-Report-v1.0.pdf` (36-finding register). Per-phase detail: `docs/remediation/00-BASELINE.md`, `REMEDIATION-MATRIX.md`, `PHASE1-DONE.md`, `PHASE2-DONE.md`, `PHASE3A-INTAKE-FILTERS-DONE.md`, `PHASE3-DONE.md`, `PHASE4-DONE.md`.

---

## A. Executive summary

The remediation closed the one **Critical** finding and the load-bearing **High** findings that made the product's own promises untrue, plus the medium/low integrity, reliability, security-hardening and tech-debt tier. Concretely:

- **The live cross-tenant leak (SEC-001) is closed** and converted into a *closed bug class* by a centralized org-scoping chokepoint (`app/services/tenancy.py`) + a permanent cross-tenant contract test; a full backend sweep found no other leak.
- **Four unenforced "Ten Rules" promises are now real:** the banned-term guardrail runs on the actual report path (GRD-001), the lineage receipt reports the true guardrail status instead of a hardcoded "passed" (GRD-002), the contraction bypass is closed (GRD-003), the SME workbench persists real decisions (FUNC-001), and no fabricated VCI is rendered (DATA-003).
- **The product thesis got its highest-value slice:** industry + jurisdiction are captured at intake and **behaviourally proven to change the score** (ARCH-001A), retiring the manual DB pre-step; a scope-preview was added (ARCH-001B step 6).
- **Reliability/integrity:** async intake with server-state progress + idempotency (QA-011), a stale-job reaper so monitoring can't silently stop (BACK-001), IP-pinned SSRF (SEC-002/004), deterministic population version + canonical content hash (DATA-001/002), replay-safe alerts (BACK-002), retry+degraded LLM path (AI-002), taxonomy-aware classifier prompt (AI-004), authenticated PDF download (FE-001).
- **Hardening/debt:** rate limiting (SEC-005), branding sanitization (SEC-006), HMAC partner keys (SEC-009), typed bodies (SEC-010), webhook SSRF closure (SEC-011), narrowed excepts (BACK-003), corrective RLS-policy migration (SEC-008), FK + uuid-shape migrations (DATA-004/DB-002), dead-code removal (MAINT-001), documented governed limits (AI-003, DB-001, F14-001).

**Major architecture changes:** a centralized tenancy chokepoint; an async intake job/progress subsystem (`assessment_job`); IP-pinning SSRF transport; a versioned org-profile refresh so captured config reaches the score; canonical (volatile-stripped) content hashing.

**Honest suitability verdict — CONTROLLED SINGLE-TENANT PILOT.** SEC-001 is closed with a regression contract test, so a supervised single-tenant pilot is defensible. It is **not yet multi-tenant GA**: the durable fix for the isolation *class* (SEC-003 full RLS under a per-request user JWT) is deferred, and several correctness/accuracy guarantees (EVAL-001 measured accuracy; DATA-004 VALIDATE; migrations 0043–0047 applied to prod) are BLOCKED on external actions. This verdict is based only on verified test results, not aspiration.

---

## B. Baseline

- **Start:** branch `main` @ `8c4ed92`. **End:** same branch, **working tree only — no branches, no commits** (owner instruction).
  - ⚠️ **Standing-rule conflict:** this conflicts with `AGENTS.md` §1.4 ("Branch … Never commit directly to main") and §1.7. Recorded in `logs/decision-log.md` (2026-08-04) and every `*-DONE.md`. **To reconcile:** retro-branch the working-tree diff into per-phase PRs carrying the finding IDs, or formally waive §1.4 for this window.
- **Initial test status (`00-BASELINE.md`):** backend `910 passed, 3 failed, 15 skipped`; frontend `75 tests` pass. The 3 backend failures were pre-existing/environmental (live-Supabase PostgREST 500 statement-timeout + low embedding coverage).
- **Final test status:** backend `1058 passed, 5 failed, 15 skipped`; frontend `94 tests` pass (tsc + build clean). +148 backend passing. The 5 failures = the 3 environmental ones + 2 migration-ledger tests that fail *only* because migrations 0043–0047 are registered but not applied to prod (owner chose Leave-BLOCKED-EXTERNAL). No unexplained new red; no code regression.

---

## C. Finding-by-finding (all 36 + MAINT-001)

Legend: RC = root cause confirmed. Evidence = test file / command.

### Critical
- **SEC-001** — `/findings/` cross-tenant IDOR. RC ✓ (no org filter; service-role bypasses RLS). Files: `findings.py`, `tenancy.py`(new). Impl: customer scoped via `customer_org_scope`, no-org→empty. Tests: `tests/test_org_isolation.py` (14). **FIXED (TESTED).**

### High
- **GRD-002** — lineage falsely reported guardrail "passed". RC ✓. Files: `report/explain.py`, `ExplainPanel.tsx`. Impl: default→`not_recorded`, honest 3-state badge, provenance conditional. Tests: `tests/test_explain.py`. **FIXED.**
- **GRD-003** — apostrophe/contraction bypass. RC ✓ (verified by execution). Files: `guardrail.py`. Impl: removed single-quote alternation. Tests: `tests/test_guardrail.py` (3 bypass fixtures + [source:] still exempt). **FIXED.**
- **GRD-001** — guardrail never ran on report path. RC ✓. Files: `reports.py`, `report/assembly.py`. Impl: `_enforce_snapshot_prose` over all snapshot-bound prose, fails closed, records result in Section-11. Tests: `tests/test_guardrail_report_path.py` (6). **FIXED.**
- **FUNC-001** — SME workbench fabricated + dead submit. RC ✓. Files: `web/src/pages/sme/ReviewQueue.tsx`. Impl: driven off real `/review/queue`, Confirm/Edit/Dismiss + Submit POST to `review.py`, honest absence for non-exposed metrics. Tests: `ReviewQueue.test.tsx` (6) + backend role rejection. **FIXED.**
- **SEC-003** — service-role bypasses RLS (systemic). RC ✓. Files: `tenancy.py`, contract test. Impl: centralized chokepoint + contract test (minimum path); sweep found no other leak. **PARTIALLY FIXED** — full RLS-under-user-JWT deferred (documented).
- **SEC-002** — SSRF DNS-rebinding TOCTOU. RC ✓. Files: `ssrf.py`, `extract.py`. Impl: `resolve_and_validate` + pinned httpx transport (SNI/cert on hostname). Tests: `tests/test_ssrf.py` (29). **FIXED.**
- **BACK-001** — jobs hang `running` forever. RC ✓. Files: `jobs/framework.py`, `admin.py`, `main.py`. Impl: age-bounded `is_running` + `reap_stale_runs` + startup reaper + `/admin/status` count. Tests: `tests/test_jobs_reaper.py` (4). **FIXED.**
- **EVAL-001** — accuracy unmeasured; F17 never run. RC ✓. Impl: harness verified present; runbook documented. **BLOCKED — EXTERNAL** (SME gold labels + live DB/GPU; harness fabricates nothing).
- **ARCH-001** — config not captured → generic reports. RC ✓. Files: `intake_options.py`(new), `config_routes.py`(new), `assessments.py`, `live_scoring.py`, `Intake.tsx`, migration 0044. Impl (ARCH-001A): industry+jurisdiction captured, validated, threaded, forced versioned re-profile; **behavioural tests prove a changed filter changes the score**. ARCH-001B: scope-preview shipped; data-practice declaration/competitors deferred (non-consumed). Tests: `tests/test_arch001a_intake_filters.py` (11) + `Intake.test.tsx` (2). **PARTIALLY FIXED (thin slice TESTED).**
- **FIND-001** — enforcement lineage dead on findings. RC ✓. **BLOCKED — SME APPROVAL (GOVERNED):** `DECISION-NEEDED.md` parks it; code unchanged; exact approval + spec-update path flagged in `logs/decision-log.md`.

### Medium
- **SEC-004** — SSRF port/IPv6 gaps. **FIXED** (port allowlist {80,443}, ULA/mapped-v6 rejected; `tests/test_ssrf.py`).
- **SEC-005** — rate limiting only on login. **FIXED** (`ratelimit.py`; assessments/bulk/pdf throttled; `tests/test_sec005_ratelimit.py` (8)).
- **SEC-006** — partner branding injection. **FIXED** (strict hex/rgb + https/SSRF logo allowlist; `tests/test_sec006_branding.py` (19)).
- **SEC-007** — live secrets on disk + weak DB pw. RC ✓ (hygiene verified, env-driven). **BLOCKED — EXTERNAL (rotation).**
- **CRED-001** — seeded cred hashes in git history. RC ✓ (untracked+ignored since `015ff8e`; hashes remain in history). **PARTIALLY FIXED · rotation BLOCKED — EXTERNAL.**
- **SEC-008** — notice-table RLS policy ledger drift. **IMPLEMENTED** (corrective migration 0046 + `tests/test_sec008_rls_policies.py` (4)); live verify + apply BLOCKED-EXTERNAL.
- **DATA-001** — `population_version = time()`. **FIXED** (canonical hash identity; `tests/test_data001_population_version.py` (6)).
- **DATA-002** — content_hash includes volatile fields. **FIXED** (canonicalized; `tests/test_data002_content_hash.py` (4) + reproducibility/determinism tests still pass).
- **DATA-003** — hardcoded VCI 75. **FIXED** (real VCI or honest absence; `web/src/test/vci_absence.test.tsx` (7)).
- **DATA-004** — missing org FKs / nullable owners. **IMPLEMENTED** (migration 0045 FKs `NOT VALID`, data-safe, + orphan-audit); VALIDATE/NOT NULL BLOCKED-EXTERNAL (post live audit).
- **AI-002** — 5xx not retried → silent downgrade. **FIXED** (retry 429/5xx only; honest `degraded` flag; `tests/test_llm_retry_taxonomy.py` (10)).
- **AI-004** — classifier prompt under-specifies taxonomy. **FIXED** (taxonomy-injected, versioned prompt; no accuracy claim).
- **BACK-002** — duplicate alerts on crash. **FIXED** (hash-first + `(notice_id,new_hash)` dedupe; `tests/test_back002_idempotent_alerts.py` (3)).
- **FE-001** — PDF download can't send JWT. **FIXED** (authenticated blob; `web/src/test/report_page_download.test.tsx` (4)).
- **QA-011** — synchronous intake, no progress. **FIXED (IMPLEMENTED)** (async 202 + status + polling + idempotency; `tests/test_intake_async.py` (7); migration 0043 prod apply BLOCKED-EXTERNAL).

### Low / debt
- **SEC-009** — unsalted SHA-256 partner keys → **FIXED** (HMAC+pepper, legacy-compatible; `tests/test_sec009_010.py` (9)); rotation to HMAC = external re-issue.
- **SEC-010** — untyped dict bodies → **FIXED** (typed Pydantic models).
- **SEC-011** — webhook/logo SSRF sink → **FIXED** (validate at save + IP-pin at send; `tests/test_sec011_webhook_ssrf.py` (13)).
- **BACK-003** — bare/silent excepts → **FIXED** (narrowed + logged in reports/explain/live_scoring).
- **AI-003** — presence-proxy scoring depth → **DOCUMENTED** (governed; Phase-5 spec item; `INTELLIGENCE-QUALITY.md`).
- **F14-001** — F-014 denominator pre-review → **FIXED (labeled)** (`review_stage:"pre_review"` in lineage).
- **DB-001** — migration numbering collisions → **DOCUMENTED** (numbering rule + aliases in the apply manifest; no renames on a deployed DB).
- **DB-002** — assessment_id text vs uuid → **IMPLEMENTED** (CHECK-uuid `NOT VALID` migration 0047; text→uuid conversion staged BLOCKED-EXTERNAL).
- **MAINT-001** — dead code → **RESOLVED** (deleted `NewAssessment.tsx` + `onedrive.py`; cleaned `web/.env`; gate green).
- *(Scan-surfaced, outside the 36, Low)* **GS-001/GS-002** → **DEFERRED** (F-004→VCI wiring tied to FIND-001; placeholder-confidence backfill coverage — noted).

**Every matrix row has a terminal status; none remain CONFIRMED/NOT STARTED.**

---

## D. QA-001…QA-014

| QA | Status after remediation |
|---|---|
| QA-001 org profile capture | **PARTIAL** — industry+jurisdiction captured (ARCH-001A); size/practices deferred (non-consumed) |
| QA-002 industry selection | **RESOLVED** |
| QA-003 state/legal scope | **RESOLVED** |
| QA-004 data-category config | Unchanged — engine DETECTS from notice; declaration deferred (would be non-consumed) |
| QA-005 data-practice config | Unchanged — DETECTED, not declared |
| QA-006 benchmark selection | **PARTIAL** — auto-built + now disclosed pre-run in the scope-preview |
| QA-007 use-case/report-mode | OPEN — tied to QA-013 (deferred) |
| QA-008 scope preview | **RESOLVED** — scope-preview (ARCH-001B step 6) |
| QA-009 PDF output | **RESOLVED** (still works) + authenticated download (FE-001) |
| QA-010 processing flow | **RESOLVED** (still works) — now async (QA-011) |
| QA-011 progress/timeout/retry | **RESOLVED** — async polling + elapsed + retry |
| QA-012 processing disclosure | **RESOLVED** — honest intake disclosure |
| QA-013 audience/template modes | **DEFERRED (documented)** — no decorative button; needs backend register narrative |
| QA-014 config drives output | **PARTIAL** — proven for industry/jurisdiction (behavioural tests); full data-practice declaration deferred |

QA-009 and QA-010 were re-checked and remain resolved after the async refactor (the synchronous path is preserved for the partner/internal caller; `test_intake_async.py` + existing intake tests pass).

---

## E. Ten Rules scorecard (evidence-based)

| Rule | Verdict | Evidence |
|---|---|---|
| 1. No legal verdicts | **HOLDS** | `guardrail.enforce` now on the real report path (GRD-001) + contraction bypass closed (GRD-003). `test_guardrail_report_path.py`, `test_guardrail.py` |
| 2. No score without a receipt | **HOLDS** | Lineage shows real guardrail status, `not_recorded` never a fake pass (GRD-002). `test_explain.py` |
| 3. Honest confidence | **HOLDS** | No fabricated VCI; real value or honest absence (DATA-003). `vci_absence.test.tsx` |
| 4. Delivered reports never change | **HOLDS** | Canonical content hash (DATA-002) + deterministic population version (DATA-001); reproducibility/determinism tests pass |
| 5. A human expert stands between machine and client | **HOLDS** | SME workbench persists real decisions (FUNC-001); customer rejected from SME routes. `ReviewQueue.test.tsx` + role tests |
| 6. Fair comparisons only | **PARTIAL** | Cohort gating intact; industry now captured so industry-matching can fire (ARCH-001A) — but full profile still thin |
| 7. Other people's data treated better than expected | **HOLDS (app-layer) / PARTIAL (defense-in-depth)** | SEC-001 closed + cross-tenant contract test; RLS-under-JWT backstop (SEC-003 full) deferred. `test_org_isolation.py` |
| 8. AI assists; doesn't decide | **HOLDS** | Unchanged; AI-002/004 keep classification honest (degraded flag), no LLM-authored numbers |
| 9. Speak the reader's language | **HOLDS** | Honest-absence states; plain-language intake disclosure (QA-012) |
| 10. Specs before code; docs match reality | **HOLDS (this pass)** | Docs updated to reality (§N); governed items routed to SME not silently changed (FIND-001) |

---

## F. Security

- **Tenant isolation:** SEC-001 closed; centralized `customer_org_scope`; permanent cross-tenant contract test; sweep found no other leak. Runtime still uses the service-role key — the app-layer chokepoint + test is the guarantee until **SEC-003 full RLS** (deferred).
- **SSRF:** resolve-once + IP-pinned fetch (SEC-002), port allowlist + IPv6 ULA/mapped-v6 rejection (SEC-004), webhook sink validated at save + pinned at send (SEC-011).
- **Rate limiting:** assessments/bulk/PDF throttled, per-user keying, trusted-proxy gate (SEC-005); multi-replica shared store flagged.
- **Credentials:** hygiene verified + env-driven; HMAC partner keys (SEC-009); **rotation of live secrets + seeded accounts + partner keys = BLOCKED-EXTERNAL** (SEC-007/CRED-001).
- **Branding/validation:** strict color/logo sanitization (SEC-006); typed request bodies (SEC-010).

---

## G. Database

- **New migrations (all additive/idempotent, introspected against the committed schema first; prod apply BLOCKED-EXTERNAL):** `0043` assessment_job (async intake), `0044` organization.industry_source, `0045` org/notice FKs (`NOT VALID`, data-safe), `0046` re-apply notice RLS policies (SEC-008 drift), `0047` assessment_id uuid-shape CHECK (`NOT VALID`).
- **Workflow:** async intake job/progress; versioned org-profile refresh (new `profile_version`, never overwrite).
- **id normalization:** DB-002 staged (CHECK now; `text→uuid`+FK after a live audit).
- **DB-001:** numbering/order rule + historical aliases documented in the apply manifest; applied files never renamed (checksum ledger).

---

## H. AI / model

- **Prompt (AI-004):** classifier prompt now injects taxonomy definitions from `config/clause_taxonomy.json`, versioned `classify-taxonomy-v2`, structured-output validation preserved.
- **Retry/fallback (AI-002):** retry 429/5xx only; keyword fallback returns an honest `degraded` flag + zeroed confidence (no more fake 0.5).
- **VCI:** no fabricated defaults (DATA-003).
- **Eval status (EVAL-001):** harness present; **accuracy NOT measured** — gold set unlabelled (0/200); **no accuracy number is claimed anywhere.** Embedding coverage ~11.5% (recorded), backfill runnable but not run. Both BLOCKED-EXTERNAL with a documented runbook.
- **AI-003:** presence-proxy depth documented; element-level scoring is a Phase-5 spec item.

---

## I. Frontend

- New intake filters (industry single-select + state multi-select) + honest-degradation note + scope-preview + processing disclosure.
- Async progress view: stage + elapsed + safe retry; refresh-recoverable (server state).
- SME workbench wired to real data + real submit; honest absence for non-exposed metrics.
- Authenticated PDF download; honest-absence VCI everywhere; guardrail badge three-state.
- Removed: dead `NewAssessment.tsx`. (Mock policy: no new mocks introduced; the masked v1 surfaces are unchanged.)

---

## J. Test results (verbatim)

```
# Backend
./.venv/bin/python -m pytest -q
→ 5 failed, 1058 passed, 15 skipped in 215.87s   (exit 1)
   FAILED tests/test_embeddings.py::test_disclosure_clause_embedding_dim        (environmental — live-DB)
   FAILED tests/test_embeddings.py::test_nn_search_returns_results              (environmental — live-DB)
   FAILED tests/test_schema_p1.py::test_corpus_tables_nonempty[disclosure_clause] (environmental — live-DB)
   FAILED tests/test_f02_ingestion_foundation.py::test_apply_now_order_and_step_a_first          (migrations 0043–0047 not applied to prod)
   FAILED tests/test_f02_ingestion_foundation.py::test_schema_migrations_rows_match_file_checksums (migrations 0043–0047 not applied to prod)

# Frontend
cd web && npm ci   → exit 0
npx tsc --noEmit   → exit 0
npx vitest run     → Test Files 11 passed (11) · Tests 94 passed (94)
npm run build      → exit 0
```
**vs baseline (`910/3/15`, web 75):** +148 backend passing, +19 frontend tests. The 3 environmental failures are pre-existing (live-Supabase timeout); the 2 migration-ledger failures are new-but-expected and go green the instant migrations 0043–0047 are applied to prod. No unexplained new red; no code regression.

### End-to-end journeys — verification status (honest)
A **live browser run of the four journeys against the deployed stack was NOT performed** — it requires the deployed API + live Supabase with migrations 0043–0047 applied + the RunPod model, which is BLOCKED-EXTERNAL (see §K.1). Each journey is instead verified at the **integration-test level** (the honest substitute), step-by-step:
- **Customer** (login → configure industry+jurisdiction → async submit → progress → report → PDF): `test_arch001a_intake_filters.py` (config **changes the score** — the ARCH-001 proof), `test_intake_async.py` (202 + status stages + idempotency), `report_page_download.test.tsx` (authenticated PDF), `Intake.test.tsx` (filters + scope-preview). Live async progress needs 0043 applied.
- **SME** (queue → open real item → Confirm/Edit/Dismiss → submit → persist → gate): `ReviewQueue.test.tsx` (real item drives panel; Confirm/Submit POST) + backend `review.py` role tests.
- **Admin** (status → job health → stale-run visibility): `test_jobs_reaper.py` + `/admin/status` `stale_job_runs`; admin not blocked by ownership check (`test_org_isolation.py::test_admin_not_blocked_by_ownership_check`).
- **Cross-tenant attack** (customer A uses B's ids on every tenant-scoped route → no leak): `test_org_isolation.py` (14 — org A vs B scoped/empty/platform-wide + by-ID 403 + SME-route rejection).
**Recommended before pilot go-live:** run the four journeys manually once against the deployed stack after applying 0043–0047 (the `/verify` or `/run` skills, or a scripted smoke).

---

## K. External actions still required (BLOCKED — nothing falsely marked complete)

1. **Apply migrations 0043–0047 to the live DB** — *reason:* prod-DB mutation (owner chose Leave-BLOCKED). *Steps:* `cd <repo> && PYTHONPATH=. ./.venv/bin/python -m scripts.db.apply_and_record`. *Verify:* `select to_regclass('public.assessment_job');` non-null; `select count(*) from schema_migrations where filename like '004%';` = 5; the 2 `test_f02` tests then pass. Makes async intake / industry_source / FKs / RLS policies / uuid-checks live.
2. **SEC-008 live RLS verify** — *after apply:* run the `pg_policies` query in `tests/test_sec008_rls_policies.py::LIVE_VERIFY_QUERY` → expect 3 rows.
3. **DATA-004 finalize** — *Steps:* run `scripts/db/audit_data004_orphans.sql`; repair/quarantine offenders; `VALIDATE CONSTRAINT` + tighten `NOT NULL` on scored rows.
4. **DB-002 finalize** — after a uuid audit, the staged `text→uuid`+FK conversion (destructive, maintenance window) per `0047`'s header.
5. **SEC-007 / CRED-001 credential rotation** — DB password, service-role key, JWT secret, Tailscale key, the 3 seeded accounts; optional git-history purge. Exact steps in `PHASE1-DONE.md` §BLOCKED. *Verify:* old creds rejected; `select … where role='customer' and organization_id is null` = 0.
6. **SEC-009 partner-key rotation** — re-issue keys so they store as HMAC (legacy sha256 still verifies until then).
7. **EVAL-001** — label the 200-clause gold set → run F17 → publish accuracy/VCI calibration; run the embedding backfill. Runbook in `PHASE2-DONE.md` §BLOCKED. *Verify:* `SELECT count(*) FROM gold_label WHERE gold_domain IS NOT NULL` > 0.
8. **FIND-001 (governed)** — SME ruling, then implement via the `spec-update` workflow.
9. **SEC-003 full RLS** — route customer reads via the anon key + user JWT (its own reviewed change).

---

## L. Remaining risks (stated plainly)

- **Multi-tenant defense-in-depth:** until SEC-003 full RLS lands, isolation rests on the app-layer chokepoint + contract test (no DB backstop at runtime). Adequate for a supervised single-tenant pilot; **not** for open multi-tenant GA.
- **Accuracy is unmeasured (EVAL-001):** the platform is reproducible and honest, but per-domain classification accuracy is not yet measured — no number is claimed. Depth is presence-proxy (AI-003).
- **Migrations not yet applied:** async intake / FKs / RLS policies / industry_source are code-complete but inert in prod until 0043–0047 are applied.
- **Credentials not rotated** (SEC-007/CRED-001) — blast radius unchanged until the external rotation runs.
- **Governed items unchanged** (FIND-001, QA-013, AI-003 depth) — awaiting SME/product/spec decisions; not silently altered.

---

## M. Files changed (important; one-line purpose)

**New backend:** `app/services/tenancy.py` (org-scope chokepoint) · `app/services/intake/jobs.py` (async job state) · `app/services/intake_options.py` (intake vocab) · `app/routers/config_routes.py` (`/config/intake-options`) · `app/services/ratelimit.py` (limiter).
**Changed backend:** `findings.py` (SEC-001) · `guardrail.py` (GRD-003) · `report/explain.py` (GRD-002) · `reports.py`+`report/assembly.py` (GRD-001, DATA-002, SEC-005, BACK-003) · `assessments.py` (QA-011 async, ARCH-001A) · `live_scoring.py` (versioned refresh, BACK-003) · `jobs/framework.py`+`main.py`+`admin.py` (BACK-001) · `intake/ssrf.py`+`intake/extract.py` (SEC-002/004) · `benchmark/population.py` (DATA-001) · `llm.py` (AI-002/004) · `jobs/monitor_notices.py` (BACK-002) · `report/renderer.py` (SEC-006) · `services/partner.py`+`routers/partner.py`+`quarterly.py`+`eval.py` (SEC-009/010) · `notifications.py`+`alerts.py` (SEC-011) · `pipeline.py` (F14-001) · `routers/explain.py` (BACK-003) · `config.py`+`.env.example` (flags/pepper).
**New migrations:** `0043`–`0047` + `scripts/db/audit_data004_orphans.sql`; `apply_and_record.py` (manifest + DB-001 doc).
**Frontend:** `Intake.tsx`+`intake.css` (QA-011/012, ARCH-001A/B) · `sme/ReviewQueue.tsx` (FUNC-001) · `ReportPage.tsx` (FE-001) · `report/ExplainPanel.tsx` (GRD-002) · `report/sections/RegulatorExposure.tsx`+`FindingsTable.tsx`+`components/{ScoreCell,LineageDrawer,AdvisorNote}.tsx` (DATA-003). Deleted `NewAssessment.tsx`. **Deleted:** `app/services/onedrive.py`.
**Tests:** 14 new backend files + extended org-isolation/guardrail/explain; 4 new web test files.

---

## N. Documentation changes

- `AGENTS.md` — §3 SSRF second-pass + new **§3a** standing rules (tenancy chokepoint + contract-test requirement, no fabricated trust defaults, guardrail-on-all-prose, async intake lifecycle, SME persistence). *(Non-generated region; GENERATED sections unchanged — no spec-source change was needed for these standing rules.)*
- `RLS-AUDIT.md` — §7 remediation update (SEC-001/003/008/011).
- `docs/DEMO_RUNBOOK.md` — removed the manual "set industry in the DB before intake" step (ARCH-001A replaces it).
- `INTELLIGENCE-QUALITY.md` — AI-003 presence-proxy limitation note.
- `logs/decision-log.md` — no-branch conflict, FIND-001/QA-013 governance, remediation-complete summary.
- `docs/remediation/` — `00-BASELINE.md`, `REMEDIATION-MATRIX.md`, `PHASE{1,2,3,3A,4}-DONE.md`, this `FINAL-REPORT.md`.
- **Flagged for follow-up (not updated this pass):** `README.md`, the hand-maintained feature checklist, `00-plan/mock-tracker.md` — these under-report the build per the review's own note; recommend a dedicated docs pass (no behaviour depends on them).

---

*No fabricated test, accuracy, security, or deployment numbers appear in this report. Externally-blocked items are documented with exact steps and verification commands; nothing blocked is marked complete.*
