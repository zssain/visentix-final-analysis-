# F23 — Internal Third-Party Assessment Workspace

**Status:** shipped backend; live demo-profile activation blocked by Supabase gateway HTTP 402 (2026-09-03) · **Release:** demo/internal validation only · **Depends on:** F01, F04, F05, F10

## Purpose

Let the named Visentix internal demo users assess public notices belonging to different companies without treating those companies as the users' tenant, changing an existing customer organization, or exposing the resulting drafts outside the private demo workspace.

This release is intentionally narrower than a customer-facing third-party assessment product. Publication, notifications to assessed companies, disputes or appeals, scheduled monitoring, benchmark admission, plan limits, and customer self-service registration remain out of scope.

## Ownership model

- `profiles.organization_id` remains the authenticated user's workspace anchor. The seven approved demo profiles all point to one private `Visentix Demo` organization.
- Each submitted company is represented by a new organization row with `origin = internal_demo_target`. A demo submission must never resolve to or mutate an existing organization row, even when its domain matches one.
- `workspace_target` is the explicit ownership edge from the demo workspace to the assessed target. It records who registered the target and the normalized public domain used for that registration.
- New assessment/result rows carry nullable `workspace_organization_id`. For internal-demo assessments this is the Visentix Demo id while `organization_id` is the assessed target id.
- Legacy rows remain untouched. Read scoping includes either an exact `workspace_organization_id` match or, only when that column is NULL, the legacy `organization_id` match.
- Every customer query still derives the caller's workspace from `customer_org_scope()`; no customer path becomes platform-wide.

## Data

Migration `0052_f23_internal_demo_workspace.sql` is additive and creates/adds:

- `workspace_target(workspace_target_id, workspace_organization_id, target_organization_id, normalized_domain, registered_by, created_at)` with a unique workspace/domain edge, RLS enabled, and grants revoked from `anon` and `authenticated`.
- `profiles.third_party_assessment_enabled boolean NULL`; NULL is treated as false. Only the seven approved internal demo profiles receive true.
- Nullable `workspace_organization_id` on `privacy_notice`, `risk_finding`, `derived_data_item`, `report_snapshot`, `assessment_job`, and `assessment_intake_scope`, plus indexes used by workspace-scoped reads.

No existing row is backfilled or updated by the migration.

## Intake behavior

1. A normal customer follows the existing behavior: workspace and assessed organization are the same.
2. A customer with `third_party_assessment_enabled = true` may provide a public HTTP(S) URL and organization name. The URL still passes the existing pinned-IP intake validation.
3. The server normalizes the hostname and looks up `workspace_target` by the caller's workspace and normalized domain.
4. If no mapping exists, the server creates a new isolated `internal_demo_target` organization and the mapping. It does not reuse an existing corpus/customer organization and does not add the target to a benchmark population.
5. Profiling/scoring use the target organization. Ownership, listing, report access, saved history, and audit access use the workspace organization.
6. Demo-target notices have monitoring disabled and are excluded from quarterly/global intelligence output.

Text/upload intake cannot create a new third-party target in this release because it lacks a verified hostname. It continues to assess the caller's own organization.

## API behavior

- Existing assessment and report response shapes remain compatible. Responses may additionally include `target_organization_id` and `workspace_organization_id`.
- A demo user can list/read only rows owned by the Visentix Demo workspace.
- A non-demo customer cannot activate third-party mode by sending a target id or workspace id in a request; both ids are server-derived.
- SME/admin behavior remains platform-wide under the existing role rules.

## Acceptance criteria

- AC-1 Submitting a new public company URL from an enabled demo profile creates/reuses a target only inside that workspace and never updates an existing organization matched by name/domain.
- AC-2 Persisted notice, findings, derived values, snapshot, job, and intake-scope rows retain both target and workspace ownership where applicable.
- AC-3 Two demo users in the same workspace can see the same saved demo history; a customer in another workspace sees none of it.
- AC-4 A customer without the capability follows the legacy own-organization path even if it submits a URL for another domain.
- AC-5 No demo target enters benchmark membership, quarterly output, or continuous monitoring.
- AC-6 Workspace and target ids supplied by the client are ignored; authorization is derived from the authenticated profile and server-side mapping.
- AC-7 Existing rows are unchanged and remain readable through the documented legacy fallback.

## Test gate

`pytest -q tests/test_internal_demo_workspace.py tests/test_org_isolation.py tests/test_assessments_api.py tests/test_reports_api.py` plus the full backend and frontend suites.

## Changelog

- 2026-09-03: Shipped the additive workspace/target schema and server-derived ownership path across intake, scoring, history, findings, reports and explain routes. Demo targets are isolated from existing organizations, monitoring, benchmarks and quarterly output. Live profile activation awaits restoration of Supabase Auth/REST access; direct database migrations are already applied.
- 2026-09-03: Owner selected Option 1: a private Visentix Demo workspace whose seven normal users may assess separate target companies for internal engine validation. Plans/quotas, external publication, disputes, monitoring, and infrastructure changes are deferred.
