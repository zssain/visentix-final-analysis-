# F09 — Admin Console

**Status:** shipped (gate mode + batch trigger real; M-13/M-14 Replaced 2026-07-27) · **Release:** R1 · **Depends on:** F02, F06, schema.md (`platform_setting`, `ingestion_run`)

## Purpose
Internal operations surface: platform gate-mode control, batch assessment triggering, system health, training-label stats, corpus/source oversight (grows with F02).

## Users & entry points
Admin role · `/admin`. No provenance ribbon (not a snapshot surface); no trust mark (DDR-007).

## Behavior
1. **Gate mode:** read/write global `instant_draft` vs `expert_review` (persisted in `platform_setting`, audited: who/when).
2. **Batch assessment trigger:** kick off pipeline runs for a set of orgs/notices; job status feedback (queued → running → done/failed with counts) — replaces the `not_implemented` stub.
3. **Health:** existing `/api/admin/health` incl. training_stats (feeds F06 counters), LLM/embedding service status, DB checks.
4. (R2) Source registry management and ingest triggers (see F02).

## API contracts
- `GET/POST /review/gate-mode` — **actual path** (`platform_setting`-backed, `app/services/review.py`). ⚠️ Differs from the originally-planned `/api/admin/gate-mode`: gate mode lives on the review service, not admin. POST is admin-only.
- `POST /admin/trigger-assessment` — real batch (`app/services/reassessment.py`); returns `{run_id, requested, scored, failed, outcome, notices[]}`. The `run_id` is an `ingestion_run` row (the audit trail). There is **no** separate `GET /admin/jobs/:id`; the batch runs synchronously and returns its per-notice result set. `records-new`/`skipped` land on the `ingestion_run` row.
- `GET /admin/training-stats`, `GET /health`.

## Acceptance criteria
- AC-1 Gate-mode change persists across restart (via `platform_setting`) and is enforced by F05/F06 immediately.
- AC-2 Batch trigger runs the real pipeline (reconstructs each notice's decomposition from stored rows → `score_and_persist`) and returns real per-notice outcomes; the Console shows the run summary (simulation/placeholder deleted).
- AC-3 All admin routes reject non-admin JWTs.

## Behavior & states
- **Loading:** batch-job list and gate-mode state fetch with skeletons.
- **Empty:** no assessments run yet → plain "no batch jobs" state.
- **Error:** route or permission failure shows a plain-language error, never a stack trace.
- **Non-admin:** a non-admin JWT is blocked/redirected (AC-3). Admin is not a snapshot surface — no provenance ribbon, no "Intelligence, not legal advice" mark (DDR-007).
- **Gate-mode toggle:** optimistic UI reconciles to the persisted `platform_setting` value (M-13).

## Mocks
See [`00-plan/mock-tracker.md`](../00-plan/mock-tracker.md): **M-13** (Global Gate Mode simulated locally) and **M-14** (Trigger Batch Assessment simulated).

## Test gate
Role-enforcement tests, gate-mode persistence + enforcement integration test, job lifecycle test.

## Changelog
- 2026-07-27 (engineering closeout): **M-13 + M-14 Replaced.** Gate mode: `Console.tsx` GETs/POSTs the real `/review/gate-mode` (optimistic + rollback on failure). Batch trigger: `POST /admin/trigger-assessment` replaced the `not_implemented` stub with a real synchronous batch over an org's stored notices (`app/services/reassessment.py`, run_id = `ingestion_run` row); Console "System Operations" button wired. API-contract + AC section trued to the actual paths/shape (gate-mode is `/review/gate-mode`, not `/api/admin/gate-mode`; no separate `/jobs/:id`). Tests in `tests/test_reassessment.py`.
- 2026-07-16: Added Behavior & states, Mocks, and Changelog sections for template conformance; no behavioral change.
