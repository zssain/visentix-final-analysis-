# F09 — Admin Console

**Status:** shipped UI (gate mode + batch trigger simulated, M-13/M-14) · **Release:** R1 · **Depends on:** F02, F06, schema.md (`platform_setting`)

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
- `GET/POST /api/admin/gate-mode` (new) — POST audited.
- `POST /api/admin/trigger-assessment` — real implementation; returns job_id; `GET /api/admin/jobs/:id`.
- `GET /api/admin/health`.

## Acceptance criteria
- AC-1 Gate-mode change persists across restart and is enforced by F05/F06 immediately.
- AC-2 Batch trigger runs the real pipeline; UI shows real job status (simulation code deleted).
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
- 2026-07-16: Added Behavior & states, Mocks, and Changelog sections for template conformance; no behavioral change.
