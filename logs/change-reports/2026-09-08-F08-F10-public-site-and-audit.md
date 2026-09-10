# F08/F10 — Public site integration and app UI/truth audit

The former application-root redirect now lives at `/workspace`. Eight public
website routes from the sibling `visentix` working tree are adapted into the
existing React Router frontend. Login returns users to the existing role landing
or their requested protected page. Signed-in users can visit public pages without
the workspace rail and retain the background-task tracker.

The owner approved one frontend and explicitly deferred website redesign. Existing
hero/section content was adapted to current tokens and components; this is not a
complete visual clone. Prototype claims about scale, scores, certifications,
pricing, team/customer history and past publications were excluded. Contact does
not collect or pretend to deliver messages. No new dependencies or mocks shipped.

## Changes

| Files | Purpose |
| --- | --- |
| `web/src/pages/public/{Home,Platform,Solutions,NoticeAssessment,QuarterlyOverview,Resources,About,Contact}.tsx` | Eight adapted public pages |
| `web/src/pages/public/{PublicLayout,shared}.tsx` | Public navigation, existing theme/footer, accessible mobile sheet and shared sections |
| `web/src/{App.tsx,routes/registry.ts,pages/Login.tsx}` | Routing/layout and centralized workspace entry |
| `web/src/test/public_site.test.tsx` | Public access, navigation, role boundaries, background progress and honest contact behavior |
| `visentix-specs/02-features/F08-amendment-2026-09-08-public-site.md` | Owner-approved scope and acceptance criteria |
| `visentix-specs/02-features/F08-finding-codex-and-methodology.md` | Amendment reference; existing gaps remain open |
| `visentix-specs/01-foundation/design-system.md`, `AGENTS.md` | Route map and public-hero exception; generated version update |
| `README.md`, `logs/decision-log.md` | Single-frontend entry points and decision trace |
| `logs/audits/2026-09-08-ui-and-app-truth.md`, `logs/audits/2026-09-08-ui/` | Prioritized app audit, capability reconciliation, measurements, selected fixture screenshots and source hashes |
| This report | Scope, validation and follow-ups |

**Tables/columns added:** none. **Migrations:** none. **Live data/storage writes:**
none. **Deployment/commit/push:** none. The sibling repository and its uncommitted
changes remain intact. Source HEAD and working-tree route hashes are recorded in
`logs/audits/2026-09-08-ui/source-provenance.json`.

## Run and review

Use the existing backend setup and `cd web && npm run dev`. Visit `/` for the
website, `/login` for authentication, and `/workspace` for the existing role
landing. Existing assessment/report URLs continue to work. Production hosting
must retain the existing SPA deep-link fallback for these added routes.

Validation: `cd web && npx vitest run` (23 files, 228 tests passed),
`npm run build` (passed, existing large-bundle warning), `make guards` (passed),
and generated AGENTS consistency check. Browser evidence covers 78 light route/
viewport combinations plus eight dark diagnostic checks using isolated fixtures.
No customer data was used in screenshots.

The isolated backend baseline is **not green**: 1013 passed, 268 existing skips,
1 existing PDF byte-determinism failure (OD-18). Real environment files were
excluded from the temporary test copy and dummy configuration supplied. No tests
were weakened. This prevents declaring the full repository test gate complete.

## Follow-ups

The [audit](../audits/2026-09-08-ui-and-app-truth.md) contains 13 open findings.
Prioritize confidence suppression/lineage, report plotting and overflow, and PDF
determinism. Reconcile public catalog access and the unsupported analyst role in
specs before implementing their permission contracts. Then repair empty/error
states and shared dialog/navigation behavior. Website redesign remains deferred.
Production jobs, deployment state and the live corpus were not validated here.

Recommend an incident record for A01 if a read-only production investigation
confirms customer exposure to below-floor monitoring values. OD-18 already tracks
the PDF failure, so this report does not create a duplicate incident.
