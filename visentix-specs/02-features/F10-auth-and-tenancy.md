# F10 — Auth, Roles & Multi-Tenancy

**Status:** shipped code; live demo-user provisioning blocked by Supabase gateway HTTP 402 (2026-09-03) · **Release:** R1 hardening / R2 tenancy · **Depends on:** schema.md §2.1

## Purpose
Supabase-managed credentials with application-issued sessions: login, session persistence, role loading (customer / SME / admin, later partner + portfolio roles), role-based routing, and tenant isolation for the GRC/white-label era. Password verification is delegated to Supabase Auth; Visentix stores no password or password hash.

**JWT algorithms (as built, verified in `app/auth.py` / `app/routers/auth.py`):** verification tries **ES256** via Supabase JWKS first, with an **HS256 fallback** on the shared JWT secret; after Supabase verifies the credential, the application-session endpoint issues an **HS256** token (`algorithm="HS256"`). Every authenticated request checks signature + expiry + audience.

## Current state
AuthProvider context + declarative routing (login-redirect bug fixed); profile persisted in localStorage; JWT error details no longer leaked; RLS policies fixed (infinite recursion, NULL `auth.uid()`). The 2026-09-03 cutover removes `local_users.json` from the runtime: `/auth/login` asks Supabase Auth to verify the credential, loads the authoritative `profiles` row, and returns the existing application-session response shape so the frontend contract does not fork. The seven internal demo users are ordinary `customer` profiles in one `Visentix Demo` workspace organization. F23 keeps submitted companies as separate targets and stores the workspace owner on every new result row; the users gain no access to another tenant's saved data.

## R1 hardening (before first paying client)
1. Credentials → Supabase Auth; roles/organization → `profiles`; remove `local_users.json` from the runtime path.
2. Token expiry + refresh/rotation review; logout invalidation strategy.
3. Login rate limiting + lockout; audit log for auth events.
4. RLS re-audit with regression tests (the recursion class of bug must stay covered).
5. Secrets audit (JWT keys in env/secret store only).

## R2 tenancy
- `tenant_id` scoping on all customer data; partner role with client-workspace sub-scoping (white-label); role matrix: viewer / analyst / owner per tenant.
- API keys for the Intelligence APIs (F11) with per-key usage tracking.

## Access-control matrix (current MVP — the enforced baseline)

_Absorbed from the archived SECURITY_MATRIX.md (2026-07-15). Roles: customer / sme / admin. Customer report/PDF access is further governed by the gate mode in business-logic.md §5 (`instant_draft` shows a DRAFT banner; `expert_review` blocks until SME approval)._

| Route | Method | customer | sme | admin | public |
|---|---|---|---|---|---|
| `/health` | GET | — | — | — | ✓ |
| `/assessments/` | GET | ✓ | ✓ | ✓ | — |
| `/assessments/` | POST | ✓ | — | ✓ | — |
| `/findings/` | GET | ✓ | ✓ | ✓ | — |
| `/reports/{id}`, `/reports/{id}/pdf` | GET | ✓ (gate) | ✓ | ✓ | — |
| `/review/queue`, `/review/{id}` | GET | — | ✓ | ✓ | — |
| `/review/finding/{id}/{fid}`, `/review/{id}/approve` | POST | — | ✓ | ✓ | — |
| `/review/gate-mode` | GET/POST | — | — | ✓ | — |
| `/admin/*` (status, trigger-assessment, training-stats) | GET/POST | — | — | ✓ | — |

**Row-Level Security.** RLS ON with per-org isolation (`profiles.organization_id = auth.uid()`): `profiles` (own row), `risk_finding`, `report_snapshot`, `derived_data_item`, `organization_intelligence_profile` (own org; SME/admin see all). RLS OFF (read-only reference/corpus/catalog, no customer scope): `organization`, `disclosure_clause`, `finding_type`, `recommendation_library`. Not route-exposed: `exemplar`, `training_label`. The service-role key bypasses RLS and is **server-side only** (`app/db.py`) — never shipped to the client, never logged.

## Acceptance criteria
- AC-1 Cross-tenant reads impossible via API or RLS bypass (adversarial tests).
- AC-2 Expired/forged tokens rejected without leaking verification detail.
- AC-3 Role routing: customer cannot reach /review or /admin; SME cannot reach /admin.
- AC-4 `/auth/login` delegates password verification to Supabase Auth and returns the existing app-session contract; the application stores no password/hash and `app/` contains no `local_users.json` runtime reference.
- AC-5 Every demo profile carries the same real `Visentix Demo` workspace id; F23 stores assessed companies as isolated targets while ownership remains scoped to that workspace.
- AC-6 Unknown email, wrong password, missing/disabled profile, and upstream auth rejection all return the same plain `Invalid credentials` response. Passwords, tokens and upstream error bodies never enter application logs.

## Test gate
Existing auth/RLS suites + rate-limit test, token lifecycle tests, cross-tenant adversarial tests.

## Changelog
- 2026-09-03 (owner-approved, shipped code; live provisioning blocked externally): Credentials moved to Supabase Auth while `profiles` remains the role/workspace authority. The idempotent provisioning utility is ready for the seven ordinary customer identities in one isolated `Visentix Demo` organization, but Supabase Auth and REST both returned HTTP 402 before any account or workspace row was created. F23 stores submitted public companies as separate internal targets without granting cross-tenant access. Plans, quotas and firm-role hierarchy are explicitly deferred. The shared demo password is accepted only through a non-echoing prompt and is never written to the repository or application database.
- 2026-07-16: Added Changelog section for template conformance; no behavioral change.
