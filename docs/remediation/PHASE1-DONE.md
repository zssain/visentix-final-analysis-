# PHASE 1 — Critical Security & Trust — Completion Record

**Date:** 2026-08-04 · **Commit before:** `8c4ed92` · **Commit after:** working tree, **no commits / no branch** per owner instruction.
**Standing-rule conflict (repeated per Prompt-0 rule 3):** working directly on `main`'s tree with no branch/commit conflicts with `AGENTS.md` §1.4 ("Branch … Never commit directly to main") and §1.7. Logged in `logs/decision-log.md` (2026-08-04). Human to reconcile before shipping.

## Findings addressed

| ID | Root cause confirmed | Files changed | What changed | Tests added | Test result (actual) | Status |
|---|---|---|---|---|---|---|
| SEC-001 | Yes — `list_findings` had no org filter; service role bypasses RLS | `app/routers/findings.py`, `app/services/tenancy.py` (new) | Customer requests now scoped to `user.organization_id` via `customer_org_scope`; no-org customer → `[]` (never a platform-wide read). sme/admin unchanged (platform-wide). | `tests/test_org_isolation.py`: cross-tenant contract (org A/B, scoped/empty/platform-wide) | see gate below | **TESTED** |
| SEC-003 (min) | Yes — isolation was per-endpoint, no chokepoint | `app/services/tenancy.py` (new), `app/routers/findings.py` (list + dashboard_stats routed through it) | Single `customer_org_scope()` helper both routes now pass through; documented as load-bearing until Phase-2 RLS. Backend sweep found **no other leaks** of this class. | contract test above exercises the helper | see gate below | **PARTIALLY FIXED** (min path done; full RLS = Phase 2) |
| GRD-002 | Yes — `exec_meta.get("guardrail","passed")` fail-open default + provenance asserting a check that never ran | `app/services/report/explain.py`, `web/src/report/ExplainPanel.tsx` | Default → `not_recorded`; new `_guardrail_provenance()` only claims a pass when `status=="passed"`, else "Guardrail status was not recorded for this snapshot". Frontend badge: passed→green, not_recorded/absent→neutral gray (never red-fail, never green-pass). No historical backfill. | `tests/test_explain.py`: absent metadata never renders passed; empty bundle not "passed" | see gate below | **TESTED** |
| GRD-003 | Yes — `'[^']*'` alternation exempted spans between contraction apostrophes (verified by execution in Prompt 0) | `app/services/guardrail.py` | Removed the single-quote alternation from `QUOTE_PATTERN`; exemption now rests on `[source:…]` tags + double/smart quotes (matches business-logic.md §2 "quoted, tagged, attributed"). | `tests/test_guardrail.py`: 3 bypass fixtures → caught; `[source:…]` excerpt with apostrophes → still exempt; replaced the misleading single-quote test | see gate below | **TESTED** |
| SEC-007 | Yes — plaintext live secrets in on-disk `.env` | (no code change needed) | Verified hygiene: `.env`/`.env.*`/`local_users.json` gitignored; secrets are already **env-driven** via pydantic `BaseSettings(env_file=".env")` (`app/config.py`), so prod can point the env source at Azure secret mounts/a vault with no code change. `db/migrations/0011_local_users.sql` is tracked but **schema-only** (CREATE TABLE `password_hash`/`salt` columns, **no INSERT of credentials** — verified). Rotation itself is external (below). | n/a (verification, not code) | verified | **BLOCKED — EXTERNAL (rotation)**; code-side prep complete |
| CRED-001 | Yes — `local_users.json` PBKDF2 hashes (null-org accounts) committed in `a54c598`, still in history | (no code change) | Confirmed file is now untracked+gitignored since `015ff8e`; hashes remain in git history. **Null-org tenancy ambiguity is now contained in code**: a customer with no org gets empty results / 403 on every tenant-scoped route (SEC-001 fix + the sweep's three mechanisms), never another org's data. DB-level `NOT NULL`/FK guard cross-refs **DATA-004 (Phase 3)**. | covered by no-org customer contract test | verified (code-side) | **PARTIALLY FIXED · rotation BLOCKED — EXTERNAL** |

## Tests run (verbatim commands + real counts)

```
# targeted, during development (all passed):
./.venv/bin/python -m pytest tests/test_guardrail.py -q          → 36 passed
./.venv/bin/python -m pytest tests/test_explain.py tests/test_guardrail.py -q → 58 passed, 3 skipped
./.venv/bin/python -m pytest tests/test_org_isolation.py -q      → 14 passed (was 7 pre-phase)

# frontend gate (I edited ExplainPanel.tsx):
cd web && npx tsc --noEmit    → TSC_EXIT=0
cd web && npx vitest run       → Test Files 7 passed (7) · Tests 75 passed (75)  [unchanged from baseline]

# full backend gate:
./.venv/bin/python -m pytest -q → 2 failed, 925 passed, 15 skipped in 245.53s (exit 1)
```

### Full-suite comparison to `00-BASELINE.md`
- **Baseline:** `910 passed, 3 failed, 15 skipped` — the 3 failures pre-existing/environmental (`test_embeddings::test_disclosure_clause_embedding_dim`, `test_embeddings::test_nn_search_returns_results`, `test_schema_p1[disclosure_clause]`; live-Supabase PostgREST 500 statement-timeout `error=57014` + low embedding coverage).
- **Phase 1:** `925 passed, 2 failed, 15 skipped`.
  - **Passes +15** (910 → 925): the new tests — org-isolation 7→14 (+7), explain +2, guardrail net +5 (removed the 1 misleading single-quote test, added 6 fixtures incl. the 4 parametrized bypass cases). All new tests pass.
  - **Failures −1** (3 → 2): the 2 remaining failures — `test_embeddings::test_nn_search_returns_results` and `test_schema_p1::test_corpus_tables_nonempty[disclosure_clause]` — are a **strict subset of the baseline's environmental failures** (same live-DB PostgREST 500 statement-timeout; assertion text: *"transient DB, not a data problem"*). The third baseline failure (`test_disclosure_clause_embedding_dim`) even passed this run. **No new failures; no regression attributable to Phase-1 changes.**
  - Skips unchanged at 15 (CI-skipped live-DB/GPU suites).

## New/changed migrations (additive? idempotent?)
**None.** Phase 1 is application-code + tests only. No schema changes. (The null-org DB constraint is deferred to DATA-004 in Phase 3, additive.)

## BLOCKED — EXTERNAL ACTION REQUIRED
Rotation cannot be done from code and MUST NOT be faked. Each: reason · steps · verification.

1. **SEC-007 — Rotate the database password.** *Reason:* live weak-ish DB password sits in `.env` `DATABASE_URL`. *Steps:* Supabase dashboard → Project Settings → Database → **Reset database password** (strong random). Update `DATABASE_URL` + `DATABASE_POOLER_URL` in the prod secret store (Azure Container Apps secrets) and the local `.env`; redeploy. *Verify:* `GET /health` returns `model_status/db ok`; a scoped read (e.g. `/assessments/`) succeeds; old password rejected.
2. **SEC-007 — Rotate the Supabase service-role key (+ JWT secret if chosen).** *Reason:* live service-role key in `.env`. *Steps:* Supabase dashboard → API → roll `service_role` key; update `SUPABASE_SERVICE_ROLE_KEY` (and `SUPABASE_JWT_SECRET` if rotating) in prod secrets + `.env`; redeploy. *Verify:* an authenticated request still works; a request with the old key is rejected. ⚠️ Rotating the JWT secret invalidates existing tokens → users must re-login.
3. **SEC-007 — Scope/expire the Tailscale auth key.** *Reason:* reusable `TAILSCALE_AUTHKEY` in `.env`. *Steps:* Tailscale admin → Settings → Keys → revoke the reusable key; issue an **ephemeral, expiring, tagged** key; update `TAILSCALE_AUTHKEY` in the pod secret; re-auth the pod. *Verify:* Azure→pod `/api/chat` returns 200 over the tailnet (per `logs/decision-log.md` topology).
4. **CRED-001 — Rotate the three seeded accounts + confirm no null-org customer in prod.** *Reason:* `admin@/sme@/customer@visentix.com` hashes are in git history and were null-org. *Steps:* run `python scripts/setup_local_auth.py` to set new strong passwords (writes gitignored `local_users.json`) and/or update the live `local_users` table; then confirm no null-org customer exists — SQL: `select email from local_users where role='customer' and organization_id is null;` (and the `profiles` table). *Verify:* login with new creds works; old creds rejected; query returns 0 rows.
5. **CRED-001 — (Flagged, NOT executed) git-history purge.** The old `local_users.json` PBKDF2 hashes remain in commit `a54c598`. *Option:* `git filter-repo` (or BFG) to purge the blob, then force-push and have all clones re-clone. Given the hashes are PBKDF2 (not plaintext) and the accounts will be rotated per (4), weigh necessity vs. disruption before doing this. Not done here.

## AGENTS.md / spec / doc changes
- No spec edits required — GRD-003 fix makes the guardrail **match** `business-logic.md` §2 (excerpts exempt only when tagged/attributed); no behavior spec change, so no version bump.
- `logs/decision-log.md`: no-branch/no-commit conflict entry (added Prompt 0).
- `docs/remediation/REMEDIATION-MATRIX.md`: Status column updated in place for SEC-001, SEC-003, GRD-002, GRD-003, SEC-007, CRED-001.

## Regressions introduced & fixed
- **None introduced** (pending full-gate confirmation below). The ExplainPanel edit keeps `guardrail:"passed"` rendering as green "Guardrail: passed" (existing web test `Explain.test.tsx` still passes: 75/75). Existing explain tests still pass because their `SAMPLE_NARRATIVE_META` sets `guardrail:"passed"`.
- Guardrail stricter direction (fail-closed): removing the single-quote exemption can only *catch more*, never miss more — safe. The only test relying on single-quote exemption was the misleading one, now rewritten to assert the correct (caught) behavior.

## Notes for the next prompt (Phase 2)
- **GRD-001** (wire `guardrail.enforce()` into `reports._assemble_from_live`) must land in Phase 2 **now that GRD-003 is fixed** — routing prose through a filter that still bypassed contractions would have shipped a known hole. When GRD-001 lands, populate `exec_meta["guardrail"]` from the real `enforce()` result so the GRD-002 receipt reports fact instead of `not_recorded`.
- **SEC-003 full**: either route customer reads via anon key + user JWT (RLS fires), or expand `customer_org_scope` adoption + add each new route to `CAPTURE_ROUTES` in the contract test. The helper + `CAPTURE_ROUTES` list is the seam to build on.
- Also Phase 2 per report: FUNC-001 (SME workbench), BACK-001 (stale-job reaper), SEC-002+SEC-004 (SSRF IP-pin + port allowlist + `validate_url` unit test), EVAL-001 (gold labels/F17 — process, likely BLOCKED), QA-011 (async intake).
- Backend sweep artifact: no cross-tenant leaks beyond SEC-001; customer-reachable surface is narrow (findings, assessments, reports, explain, monitoring, notifications, formulas + public quarterly/health/login).
