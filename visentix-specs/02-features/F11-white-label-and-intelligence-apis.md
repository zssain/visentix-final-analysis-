# F11 — White-Label Portal & Intelligence APIs

**Status:** shipped UI — partner portal built, all data mocked (M-19–M-22); Intelligence APIs, tenancy & metering backend proposed · **Release:** R3 · **Depends on:** F03, F04, F05, F10 (tenancy), business-logic.md §3/§6

## Purpose
Product 3: let consulting/law/audit/insurance partners deliver Visentix intelligence under their brand — partner portal with client workspaces, branded report templates, anonymized data feeds, and the public Intelligence API suite.

## Components
1. **Partner portal:** client workspace CRUD, branding controls (logo, palette applied to report templates), usage tracking, licensing limits per contract.
2. **Intelligence APIs** (contracts per VICBNF §14 — every payload includes VCI, formula_version, explainability refs where permitted):
   - Organization Profile API · Notice Classification API · Benchmark Population API · Derived Intelligence API · Explainability API · White-Label Feed API (dataset_id, schema_version, refresh_date, permitted_use, confidence metadata).
3. **Anonymized feeds:** benchmark data, regulator trends, risk signals, industry maturity — aggregated, de-identified (reuse F06 de-id pipeline), **minimum-sample suppression** before any external exposure (DIR-006).
4. **Report template engine:** same intelligence rendered as partner-branded assessment, legal memo, board deck, or data export.

## Data
New: `partner`, `client_workspace`, `api_key`, `usage_record`, `feed_snapshot` (anonymized aggregates, segregated from customer-scoped tables per DIR-005). Amend schema.md when implemented.

## Guardrails & confidence
External feeds carry data dictionary + methodology + permitted-use restrictions; no customer-specific traceability leaves the platform; confidence metadata mandatory on every feed record; guardrail vocabulary applies to partner-branded narratives identically.

## Mocks
The portal is UI-built ahead of the backend; every displayed value is mocked and registered in [`00-plan/mock-tracker.md`](../00-plan/mock-tracker.md).

| ID | What's mocked | Real source | Removal plan |
|---|---|---|---|
| M-19 | Partner contract + client workspaces (usage, status, branding flags) | `partner`, `client_workspace` tables + live usage, scope-isolated (DIR-005) | Build tenancy + workspace CRUD; enforce partner isolation |
| M-20 | API keys + per-contract usage / rate limits | `api_key`, `usage_record` metering | Build key issuance + real usage metering; enforce limits server-side |
| M-21 | Anonymized feed catalog (schema, refresh, permitted-use, VCI, suppression) | `feed_snapshot` aggregates with min-sample suppression (DIR-006) | Build feed aggregation + server-enforced suppression |
| M-22 | Branding config + report templates | Partner branding store applied by the report template engine | Persist branding; wire template engine to branded render |

## Acceptance criteria
- AC-1 A partner can generate a client-branded report whose numbers match the underlying derived_data_items exactly.
- AC-2 Feed records below the sample threshold are suppressed, provably.
- AC-3 API keys enforce per-contract rate/usage limits; usage visible in portal.
- AC-4 De-id validation on every externally exposed language pattern.

## Behavior & states
**What is real today:** the partner portal (`/partner`) is built as UI — contract/usage summary with quota meters, client-workspace list, branding controls with a live report preview, API-key table with per-key usage metering, the anonymized feed catalog, and the report-template picker. It renders entirely from mocked data (M-19–M-22); **no tenancy, usage-metering, feed, or Intelligence-API backend is wired yet**, and there is no `partner` role — the route is gated to `admin` for demo access pending F10 tenancy.

States implemented on the UI: usage-limit / quota-caution states surfaced on both the contract meter and per-key meters (gold ≥85%, red at limit); feeds below minimum sample rendered as a visible suppression card, never at low confidence (DIR-006); expired API keys shown rejected/greyed; every feed card shows confidence metadata (VCI) and permitted-use. Responsive at 375/768/1280; reduced-motion honored. No provenance ribbon — nothing on the portal chrome is a reproducible snapshot.

Guarantees still to be enforced by the backend (not yet real): usage-limit-reached actually rejecting calls; partner/client-workspace scope isolation across real tenants (DIR-005 — mocked here as one partner's data); server-side feed suppression; unauthorized/expired key rejection at the API; every payload carrying VCI + formula_version + lineage. Full API-surface contracts remain fixed at approval.

## Test gate
Feed anonymization + suppression tests, API contract tests, branding-isolation tests, usage-metering tests.

## Changelog
- 2026-07-16 (audit): Portal flash notices moved to the shared useFlash/FlashNotice furniture (fixes an overlapping-timer bug); no behavior or AC change.
- 2026-07-16: Partner portal built UI-only against mocks (engineer). Status → "shipped UI, all data mocked"; added Mocks section (M-19–M-22) and rewrote Behavior & states to separate real UI from the not-yet-wired tenancy/metering/feed/API backend. Route `/partner` gated to `admin` pending the `partner` role (F10 tenancy). Files: `web/src/pages/partner/{PartnerPortal.tsx,mockData.ts,partner.css}`, `/partner` route + admin nav. Intelligence APIs + anonymized-feed backend remain proposed.
- 2026-07-16: Added Behavior & states and Changelog sections for template conformance; no scope change (feature remains proposed).
