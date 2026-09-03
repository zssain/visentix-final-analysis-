# F26 — Firm RBAC & Audit Log

**Status:** shipped — audit-only phase (2026-09-03)
**Release:** R2
**Owner:** Product + Engineer
**Depends on:** F10, schema.md §2.1/§2.8

## Purpose
Record who used Visentix, when, and which resource they acted on, without retaining request content. This phase supplies durable per-user history for the internal demo. Firm-specific owner/member/viewer authority is deliberately deferred until the account model is approved; all current demo identities remain ordinary customer users.

## Users & entry points
Every authenticated API user produces audit events. `GET /account/audit` returns only the caller's own events within the caller's organization. Platform admins may inspect the backend table operationally; a cross-user firm-admin view does not ship before firm roles exist.

## Data
New additive `audit_event(id uuid pk, organization_id uuid not null, user_id uuid not null, action text, resource_type text, resource_id text null, at timestamptz, request_id uuid, expires_at timestamptz)`. It is append-only, RLS-enabled, and denied to `anon`/`authenticated`; the API uses the existing service boundary. `expires_at = at + 12 months` records the retention obligation. A physical purge is a separately approved ops action because standing data rules prohibit an agent from adding or executing destructive operations.

## API contracts
- `GET /account/audit?limit=…&before=…` — authenticated; customer output is filtered by both `organization_id` and `user_id`; returns metadata only, newest first.

## Behavior & states
Audit middleware records one event after each authenticated request. It reads the authenticated identity set by the existing F10 dependency, stores the matched route template rather than query values, and never delays or fails the response if the audit write fails. Unauthenticated requests produce no row. Empty history returns an empty list, not fabricated activity.

## Guardrails & confidence
Never store a request/response body, submitted notice text, URL query string, authorization header, password, token, cookie, or upstream error body. Audit data is collected for accountability only; behavioral learning is a purpose change and cannot ship until the privacy notice, governance trigger, and subprocessor posture are re-approved.

## Mocks
none

## Acceptance criteria
- AC-1 Each request whose F10 dependency authenticates a user schedules exactly one audit row containing only user/org, action, route resource metadata, request id and timestamps.
- AC-2 Unauthenticated requests create no row; audit storage failure never changes the application response.
- AC-3 `/account/audit` filters by both the caller's organization and user id. A no-org customer receives an empty list without a platform-wide query.
- AC-4 Tests assert that bodies, notice text, credentials, tokens, cookies, query strings, and raw URLs cannot enter the insert payload.
- AC-5 Every row carries a 12-month `expires_at`; physical expiry remains visibly tracked until separately authorized.

## Test gate
`tests/test_audit_log.py`, `tests/test_org_isolation.py`, F10 auth tests, full pytest and frontend suites.

## Open questions
- Firm owner/member/viewer role vocabulary and who may read organization-wide history are deferred with the plan/account model.
- Physical deletion at `expires_at` requires an explicitly authorized retention operation under AGENTS.md §2.

## Changelog
- 0.2 (2026-09-03): Shipped append-only metadata capture, caller-and-organization-scoped history, 12-month expiry metadata, RLS/revoked direct grants, and non-fatal audit writes. Firm-role hierarchy and physical retention processing remain deferred exactly as scoped.
- 0.1 (2026-09-03): Owner approved durable auditing and saving action history. Scoped phase 1 to content-free request metadata and caller-only reads; firm roles and audit-based learning remain deferred.
