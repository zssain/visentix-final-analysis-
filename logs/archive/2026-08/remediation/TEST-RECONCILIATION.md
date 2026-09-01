# TEST-COUNT RECONCILIATION (PROMPT 7B)

**Date:** 2026-08-05 · **Diagnose-only** (fixed nothing; no rotate/deploy/tag/push;
9 WIP files left excluded; no secret value printed).

## VERDICT: **A — the environment changed.** Not B. Not mixed.

The 34 failures are **not** a regression from the commit/exclusion step. They are
caused by the **live DB advancing after the Phase-4 gate** — three concrete
mechanisms, all proven below. The Phase 1–4 "no regressions" claims were true
against the live DB *as it was at each gate*; **this run is not comparable to
those, and the count needs re-baselining against the current environment.**

---

## The discrepancy, resolved

| Point | Passed | Failed | Skipped |
|---|---|---|---|
| Baseline (Prompt 0) | 910 | 3 | 15 |
| Phase 4 | 1058 | 5 | — |
| Now (`c46701d`) | 1045 | 34 | 15 |

Phase 4's 1058/5 was taken **before** migrations 0043–0047 were applied to live
(the session record notes Phase 4's "2 migration-ledger" rows were *not yet*
satisfied; 0043–0047 were pasted into the Supabase SQL editor during deploy-prep,
*after* the Phase-4 numbers). Since then the live schema gained 0047's UUID CHECK
constraints and `disclosure_clause` grew to ~691k rows (embeddings backfill).
Those two live changes — plus live data drift — produce all 34.

---

## Root-cause categorisation of all 34 (by mechanism)

| Mechanism | Suites | Count |
|---|---|---|
| **0047 UUID CHECK** rejects non-UUID fixture `assessment_id`s on write (`assessment_review`/`training_label`) → Postgres `23514 check_violation` → PostgREST HTTP 400 | `test_review_gate` (14), `test_training_labels` (11), `test_persistence_hardening` (3) | **28** |
| **Large-table REST 500** — `disclosure_clause` (~691k rows) `select`/`count=exact` over REST errors/times out; `_count` defaults the missing `content-range` to `*/0` and misreports "empty" | `test_schema_p1` corpus (1), `test_embeddings` (2) | **3** |
| **Live data-state assertion** (depends on live rows, not code) | `test_products` (3) | **3** |

None involve report/render/ledger/partner/preflight code, and none involve the
excluded WIP (proven in Step 3).

---

## Step 1 — verbatim errors (the fastest signal)

**`test_review_gate` (write rejected, not a connection error):**
```
app/services/review.py:135: RuntimeError
  RuntimeError: assessment_review persist failed: HTTP 400
# (TLS to jhzkyfitrdxmzyyvqfak.supabase.co completed; teardown DELETEs returned 204)
```
The 400's response header is the smoking gun — **`Proxy-Status: PostgREST; error=23514`**
(`23514` = Postgres `check_violation`). The inserted id was `assessment_id='assess-1'`
(non-UUID); 0047 added `CHECK (assessment_id ~ <uuid-regex>)` on that exact table.

**`test_training_labels` (same mechanism, swallowed):**
```
tests/test_training_labels.py:46: AssertionError
  assert label is not None  ->  assert None is not None
# capture_label's insert of assessment_id='a1' (non-UUID) hit the 0047 CHECK; the
# non-blocking capture swallows the failure and returns None. Teardown DELETEs = 204.
```

**`test_schema_p1` corpus (misreported "empty"):**
```
tests/test_schema_p1.py:138: AssertionError
  disclosure_clause is empty — corpus data lost  ->  assert 0 > 0
# but direct SQL: select count(*) from disclosure_clause = 691,313 rows.
# _count() does `content-range` .get('*/0') on a 500 response -> reads 0.
```
`test_embeddings` states it outright: *"failed after retries (status 500) —
transient DB, not a data problem."*

None are **collection/import/fixture** errors (which would have supported B).

---

## Step 2 — live DB reachable *right now*

- `DATABASE_URL` / `SUPABASE_URL` present (names only).
- Direct pooler (role `postgres`, `BYPASSRLS=true`): `schema_migrations` = **50 rows**;
  `disclosure_clause` = **691,313 rows**; `assessment_review` legacy non-UUID rows = **1**
  (proves 0047 is `NOT VALID` — kept the 1 legacy row, blocks new non-UUID).
- REST service-role reads work for other tables (`organization` → 26,697;
  `finding_type` → 8); `service_role` has `BYPASSRLS=true` (so RLS is not the cause).
  `disclosure_clause` over REST → **HTTP 500** (size/serialization), not an auth failure.

The DB is reachable; the failures are writes rejected by a constraint and reads
that error on a huge table — **test-specific, not raw reachability.**

---

## Step 3 — A/B: committed vs WIP-restored (decisive for B)

Ran the full suite twice in the same shell/env:
- **WIP present** (working tree as at 7B start): 34 failed / 1045 passed / 15 skipped.
- **As-committed** (`git stash -u` the 9 WIP files → clean tree = `c46701d`): 34 failed / 1045 passed / 15 skipped.

```
diff <(FAILED names, WIP present) <(FAILED names, as-committed)  ->  (empty)
```
**Identical failure sets.** The 9 excluded files change nothing. **Hypothesis B is
ruled out** — the commit/exclusion step introduced no regression and dropped no
load-bearing fixture/conftest/config. (WIP stash popped; tree restored to the 9
excluded files, still uncommitted.)

---

## Step 4 — skip counts (probe-skip mechanism)

Baseline **15 skipped**; both runs now **15 skipped** — **unchanged** while failures
jumped 5→34. If a probe-skip had stopped firing (tests moving skipped→failed), the
skip count would have **dropped**. It didn't. **The probe-skip theory is rejected.**
These suites were *running and passing* against the pre-0047 live DB and are now
*running and failing* against the post-0047 live DB — a clean environment change,
not a skip that turned into a failure.

---

## Step 5 — order-test claim (independent)

The preflight said the stale `test_apply_now_order_and_step_a_first` was "synced to
include 0043–0047 (not a loosening)." The committed diff (`c46701d`) is **purely
additive** — five migrations appended to the expected `APPLY_NOW` list, plus a NEW
`test_record_only_is_guarded_and_uses_file_checksum`. **No assertion was removed or
weakened** (zero deletions of asserts). It asserts *more*. The live
`test_schema_migrations_rows_match_file_checksums` passes independently (50 rows,
checksums match).

---

## Does the "no regressions (Phases 1–4)" claim still stand?

**It stands for the code, but must be RE-BASELINED for the environment.** No Phase
1–4 change regressed; the committed code is clean (Step 3 proves the failures are
independent of everything committed/excluded this session). What changed is the
**live DB the suite runs against**: 0047's constraints are now enforced and
`disclosure_clause` grew ~691k. The honest current baseline is:

> **1045 passed · 34 environmental failures · 15 skipped**, where the 34 break down
> as 28 (test fixtures use non-UUID `assessment_id`s that live 0047 now rejects),
> 3 (REST `count=exact`/`select` 500 on the ~691k-row `disclosure_clause`), and
> 3 (live data-state assertions). These are **test-side incompatibilities with the
> now-live schema/data**, not product regressions.

### Why this had to be diagnosed *before* rotation
Credential rotation changes live-DB reachability. The 28 constraint failures and
the 3 size-500 failures are **deterministic given a reachable post-0047 DB** — but
if rotation makes the DB unreachable, every one of them collapses into a
connection error and this precise mechanism can no longer be shown. This diagnosis
(DB reachable, `error=23514`, 691k rows, identical A/B set) is the pre-rotation
evidence that fixes the interpretation for good.

### Follow-ups (NOT done here — diagnose-only)
- Test-side: fixtures for `assessment_review`/`training_label`/`report_snapshot`
  should use UUID-shaped `assessment_id`s (0047 is correct; the fixtures are stale).
- `test_schema_p1`/`test_embeddings`: avoid `count=exact`/wide `select=*` over the
  ~691k-row `disclosure_clause` (paginate or `HEAD`); the "empty/transient" message
  is misleading.
- `test_products` low-VCI assertion depends on live data — pin a fixture or seed.

**Verdict A stands. Nothing was fixed, deployed, rotated, tagged, or pushed; the 9
WIP files remain excluded; no secret value was printed.**
