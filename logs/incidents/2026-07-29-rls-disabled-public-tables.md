# Incident: RLS disabled on 38 public tables — anon-key data exposure via PostgREST

**Date:** 2026-07-29 · **Filed by:** engineer · **Severity:** blocking (security — customer data exposed)

## What happened
Supabase advisor flagged `rls_disabled_in_public` on project *Visentix Proto*. Inventory found **38 of 56 public base tables with `rowsecurity=false`**, each carrying the default `anon` + `authenticated` grants (SELECT/INSERT/UPDATE/DELETE). Because Supabase exposes every public table through PostgREST, the **anon key can read — and, given the DML grants, potentially write — these tables directly**, bypassing the FastAPI backend entirely. Confirmed customer data is readable.

The advisor's stated hypothesis (0037–0041 tables) is **too narrow**: those 11 tables are the most recent additions to an already-open set. Most exposed tables predate 0037 — including original corpus/schema tables that have been RLS-off since project inception.

## Exposure proof (anon key vs production PostgREST — row COUNT only, no rows read/logged)
| Table | anon HTTP | rows exposed |
|---|---|---|
| `organization` | 206 | 26,690 |
| `notice_section` | 206 | 540,912 (customer notice content) |
| `partner_api_key` | 200 | 0 (empty today — but schema exposed; would leak partner API keys once populated) |

Method: `GET /rest/v1/<t>?select=*` with `apikey`/`Bearer` = anon key, `Prefer: count=exact`, `Range: 0-0`. Only HTTP status + `Content-Range` total captured. No row bodies were requested, read, or logged.

## Root cause
RLS was **never enabled project-wide**. Tables have been created without `ENABLE ROW LEVEL SECURITY` since the original corpus load (pre-0001) and in every migration since, including 0037–0041. Only 18 tables (the F10 customer-data set + a few later ones) ever got RLS turned on. Supabase's default grants to `anon`/`authenticated` on the public schema then exposed every RLS-off table through PostgREST.

**Why the app was unaffected functionally (and why the fix is safe):** the API reads/writes via PostgREST using the **service-role key** (`app/db.py`), which bypasses RLS; migrations/scheduler connect as the DB owner (direct Postgres), which also bypasses RLS. The **web client never uses the anon key for data** — no `createClient`/`.from()` in `web/src`; all data flows through FastAPI. The anon key appears only on the public JWKS endpoint (`app/auth.py`). So enabling RLS + revoking `anon`/`authenticated` grants (deny-by-default) closes the hole without breaking any legitimate access.

## Exposure window
Per-table, from each table's creation date through 2026-07-29. Original corpus/schema tables: since project inception. 0037–0041 tables (`alert_delivery`, `job_run`, `litigation`, `org_notification_setting`, `bulk_job*`, `feed_access_log`, `partner*`, `quarterly_*`, `clause_rewrite`, `recommendation_evidence`): since their 2026-07-2x apply dates. Closed by migration 0042 (2026-07-29). Anon + service keys rotated post-fix (were the live attack surface during the window).

## Full inventory — 38 tables with rowsecurity=false (all anon-readable)
Origin migration in brackets; "base" = pre-0001 corpus/schema.

**Customer / tenant data (highest sensitivity):**
organization [base], privacy_notice [base], notice_section [base], disclosure_clause [base], source_record [base], monitoring_event [base], org_notification_setting [0037], finding_clause [base], finding_enforcement [base], finding_legal_reference [0011/0016], clause_obligation [base], obligation [base]

**Partner (secrets):**
partner [0039], partner_api_key [0039], partner_workspace [0039]

**Backend / internal ops:**
alert_delivery [0037], job_run [0037], bulk_job [0038], bulk_job_row [0038], feed_access_log [0039], gold_label [0036], clause_rewrite [0041], recommendation_evidence [0041], quarterly_metric [0040], quarterly_snapshot [0040], litigation [0037], litigation_event [base], training_label [0008]

**Reference / corpus / catalog (no tenant scope, but still anon-exposed):**
finding_type [0001], formula_version [base], recommendation_library [0001], regulator [base], legal_reference [0011/0016], enforcement_record [base], explainability_reference [0011/0015], exemplar [0001], benchmark_cluster [base], benchmark_membership [base]

**Already RLS ON (18, for contrast — NOT changed by 0042):** profiles, risk_finding, report_snapshot, derived_data_item, organization_intelligence_profile (each with F10 per-org policies); assessment_review, review_queue_item, platform_setting, security_event, crawl_target, ingestion_run, organization_alias, parser_version, sic_industry_map, source_registry, source_version, ftc_topic_domain_map, schema_migrations (RLS on, 0 policies = deny-by-default).

## What stopped it / how it was found
Supabase advisor (`rls_disabled_in_public`). Not caught by our own CI — there was no test asserting RLS state. That absence is the lesson.

## Proposed lesson
Add a standing test that iterates all public base tables and asserts `rowsecurity=true` (fail CI otherwise), and an "ENABLE RLS + REVOKE anon/authenticated" line in the migration checklist/template, so no future `CREATE TABLE` can reopen this class of gap.

## Resolution (2026-07-29)
- **Migration `0042_enable_rls_all_public.sql` applied + recorded** (schema_migrations checksum `5c576cf6c51e…`). Deny-by-default (ENABLE RLS + REVOKE anon/authenticated) on all 38 currently-false tables via a dynamic, idempotent DO block.
- **Verified:** public base tables RLS ON = 56, OFF = 0. Anon curl on `organization` / `notice_section` / `partner_api_key` now returns **HTTP 401** (was 206 with 26,690 / 540,912 rows). Only the 5 F10 per-org-policy tables (profiles, risk_finding, report_snapshot, derived_data_item, organization_intelligence_profile) retain anon grants — RLS-governed, intended.
- **Pre-change insurance:** `db/schema_dumps/rls_state_pre0042_*.sql` (exact rowsecurity + grants for rollback).
- **Guard added:** `tests/test_rls_enabled.py` (asserts rowsecurity=true on all public tables; live-DB, registered in conftest) + `db/migrations/_TEMPLATE.sql` checklist (ENABLE RLS + REVOKE on every new table).

## References
- Fix: `db/migrations/0042_enable_rls_all_public.sql` (applied 2026-07-29).
- Guard: `tests/test_rls_enabled.py`, `db/migrations/_TEMPLATE.sql`.
- Inventory script (read-only, scratchpad): `rls_inventory.py`.
- Decision-log: 2026-07-29 entry. Rotation: LAUNCH-READINESS-v2.md §A3 (anon + service keys — owner executes).
