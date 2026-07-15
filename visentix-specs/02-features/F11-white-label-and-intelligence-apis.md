# F11 — White-Label Portal & Intelligence APIs

**Status:** proposed · **Release:** R3 · **Depends on:** F03, F04, F05, F10 (tenancy), business-logic.md §3/§6

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

## Acceptance criteria
- AC-1 A partner can generate a client-branded report whose numbers match the underlying derived_data_items exactly.
- AC-2 Feed records below the sample threshold are suppressed, provably.
- AC-3 API keys enforce per-contract rate/usage limits; usage visible in portal.
- AC-4 De-id validation on every externally exposed language pattern.

## Test gate
Feed anonymization + suppression tests, API contract tests, branding-isolation tests, usage-metering tests.
