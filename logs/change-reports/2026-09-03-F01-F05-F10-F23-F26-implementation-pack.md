# Change Report — F01/F05/F10/F23/F26 Implementation Pack

**Branch:** `feat/F22-F24-F25-F26-implementation-pack` · **Date:** 2026-09-03 · **Merge:** NOT merged

## Outcome

Shipped the owner-approved, currently buildable slice of the implementation pack: guardrail/CI repairs, Supabase-backed credential verification, a private internal-demo workspace with separately stored assessment targets, content-free per-user auditing, deterministic bundled-notice flags, and the supplied PDF visual direction. Plans, quotas, scheduled reassessment, shared rate-limit infrastructure, crawler egress changes, and firm-role hierarchy remain deferred by the owner's decisions.

Live schema work is complete. Live demo-account provisioning is not complete: Supabase Auth and REST returned HTTP 402 during the initial workspace lookup, before any account or workspace row was created. The retry-safe provisioning utility is ready for use after project access is restored.

## Application changes

- `app/services/authentication.py`, `app/routers/auth.py`, `app/auth.py`: Supabase Auth performs credential verification; `profiles` remains the application role/workspace authority; the response contract remains stable; error states collapse to one response without retaining upstream bodies.
- `app/services/internal_demo.py`, assessment/findings/report/explain/scoring services: enabled demo users resolve a public hostname to a workspace-owned, isolated target. New rows retain both target and workspace ownership; legacy rows use the documented null-only fallback.
- `app/middleware/audit.py`, `app/routers/account.py`: authenticated requests schedule one metadata-only audit write after response handling. `/account/audit` is always filtered by caller plus organization.
- `app/services/intake/entity_scan.py`: deterministic flag-only detection for multiple self-identifying organizations, with null confidence and no scoring effect.
- `app/services/report/renderer.py`, `app/services/report/assembly.py`: editorial cover, compact executive/dashboard presentation, repeated findings headers, severity guidance, Next Steps, single closing Disclosure, honest missing-score states, and catalog-code validation.
- `scripts/build_report_css.py`, `report.template.css`, generated `report.css`/`report_tokens.py`: light-theme OKLCH tokens convert deterministically to print-safe sRGB. Out-of-gamut standing-mid tokens are visibly reported when clamped; risk cut-points are unchanged.
- `scripts/db/provision_demo_users.py`: explicit-email, idempotent Supabase Auth/profile provisioning; the shared credential is accepted only through a non-echoing prompt.
- Guard work: generated banned-term runtime list, all repository guards wired into CI/Make, explicit supersession for F11/F12/F14, and a superseded-spec drift check.

## Schema changes

The following additive, idempotent migrations were introspected, applied, and recorded in the live migration ledger. No existing rows were modified and no raw artifact was touched.

- `0050_f26_audit_event.sql`: new append-only `audit_event`, request-id uniqueness, organization/user/time index, 12-month expiry metadata, RLS, direct-grant revocation.
- `0051_submission_entity_flag.sql`: new append-only `submission_entity_flag`, assessment/time index, nullable confidence, RLS, direct-grant revocation.
- `0052_f23_internal_demo_workspace.sql`: new `workspace_target`; nullable `profiles.third_party_assessment_enabled`; nullable `workspace_organization_id` on `privacy_notice`, `risk_finding`, `derived_data_item`, `report_snapshot`, `assessment_job`, and `assessment_intake_scope`; supporting indexes, RLS, direct-grant revocation.

## Verification

- Backend full run: `991 passed, 268 skipped, 0 failed`. The non-zero skip count means the live pre-merge gate is not certified; the configured Supabase gateway is externally blocked and the repository auto-skips live/ML modules when unavailable.
- Focused offline contracts: authentication/provisioning/audit/workspace/entity scan `20 passed`; report suite `82 passed, 1 pre-existing environment-dependent skip`.
- Frontend: TypeScript clean; Vitest `211 passed`.
- PDF: visually inspected cover, body, traceability, closing and back pages; fixed one traceability spill page; ten repeated byte-identity runs produced `20 passed, 0 failed`. OD-18 remains open because this result does not overrule the recorded intermittent baseline.
- Repository guards: generated assets, acronym, color, contrast, dead CSS, hedging, labels, masking, mocks, routes and specs pass. The local docs-layout guard rejects the owner's untracked root file `visentix-implementation-pack.md`; it was deliberately preserved and is not part of the implementation changes.
- `git diff --check`: clean.

## How to run

```bash
./.venv/bin/pytest -q
cd web
npx tsc --noEmit
npx vitest run
cd ..
make guards
```

After Supabase project access is restored, run `scripts/db/provision_demo_users.py` with each approved `--email` argument and enter the shared credential only at its prompt. Re-run the live auth/RLS/integration modules afterward; do not bypass Supabase Auth with direct inserts.

## Follow-ups

- Owner/project admin: restore Supabase Auth and REST access, then rerun demo provisioning and the live test gate.
- Existing open decision OD-18: PDF byte-identity remains a recorded intermittent renderer issue even though this ten-run sample passed.
- Retention operations: `audit_event.expires_at` records the 12-month obligation; physical expiry requires separately authorized operations because destructive data work is outside this change.
