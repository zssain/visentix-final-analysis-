# F10 — Auth, Roles & Multi-Tenancy

**Status:** shipped (custom local JWT); hardening R1→R2 · **Release:** R1 hardening / R2 tenancy · **Depends on:** schema.md §2.1

## Purpose
Custom JWT auth replacing Supabase Auth: login, session persistence, role loading (customer / SME / admin, later partner + portfolio roles), role-based routing, and tenant isolation for the GRC/white-label era.

**JWT algorithms (as built, verified in `app/auth.py` / `app/routers/auth.py`):** verification tries **ES256** via Supabase JWKS first, with an **HS256 fallback** on the shared JWT secret; the local seed/dev auth issues **HS256** tokens (`algorithm="HS256"`). Every authenticated request checks signature + expiry + audience. (R1 removes the local HS256 seed path from the production build — see below.)

## Current state
AuthProvider context + declarative routing (login-redirect bug fixed); profile persisted in localStorage; `local_users.json` seed; JWT error details no longer leaked; RLS policies fixed (infinite recursion, NULL `auth.uid()`).

## R1 hardening (before first paying client)
1. Seed users → DB table with hashed credentials; remove `local_users.json` from production path.
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

## Test gate
Existing auth/RLS suites + rate-limit test, token lifecycle tests, cross-tenant adversarial tests.

## Changelog
- 2026-07-16: Added Changelog section for template conformance; no behavioral change.
