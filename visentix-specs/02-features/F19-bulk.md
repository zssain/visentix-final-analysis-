# F19 — Bulk Screening Mode (regulator / law-firm / insurer journeys)

**Status:** approved — in-progress (owner-approved 2026-07-28 with the three adjustments in changelog 0.2)
**Release:** R2
**Owner:** eng (batch runner + endpoints) + SME (register/vocabulary sign-off on the export notice)
**Depends on:** `services/reassessment.py` (`trigger_reassessment` — the verified multi-notice batch kernel), `live_scoring.score_and_persist` (the single scoring path), F01 intake (`extract_from_url` → `decompose` → classify → persist), F10 (roles/tenancy), `services/scoring/heatmap.py` (domain aggregation), `services/scoring/vci.py` (suppression), F06/F09 gate (draft never auto-approved), schema.md

## Purpose
Give a **screening** user — a regulator running a sector scan, a plaintiff/claimant law firm triaging a target list, an insurer pricing a book of insureds — a way to submit **many organizations' notices at once** and get back a **risk-ranked exposure grid** where every number carries VCI, cohort `n`, and a **draft-grade** badge. It is a **triage funnel, not a verdict engine**: results are measurement (exposure / maturity vocabulary only), created in **draft state and never auto-approved**, so a human decides what to pull forward into a full expert-reviewed assessment. This is the real batch surface built on the already-shipped kernel (`POST /admin/trigger-assessment` → `reassessment.py`), replacing the F12 bulk mock (M-23/M-24).

## Users & entry points
`analyst` (new role) or `admin` · `/bulk` (replaces the current mock `web/src/pages/bulk/` — F12 M-23/M-24). Upload CSV/JSON → job list → results grid → per-org draft report. Tenant-scoped: a job belongs to the owner's `org_id` and is invisible cross-org (F10 AC-1).

## Data (new — amends schema.md; migration 0038)
```
bulk_job(
  id uuid pk, org_id uuid fk→organization /* owner tenant */, created_by uuid,
  label text, status text CHECK IN ('queued','running','partial','completed','failed'),
  row_count int, completed_count int, failed_count int,
  created_at timestamptz default now(), finished_at timestamptz null)

bulk_job_row(
  id uuid pk, bulk_job_id uuid fk→bulk_job, position int, org_name text, notice_url text,
  status text CHECK IN ('pending','running','succeeded','failed','insufficient_profile'),
  assessment_id uuid fk→privacy_notice(notice_id) null, error text null)
```
Reads (no new scoring objects): `derived_data_item`, `report_snapshot`, `risk_finding`, `assessment_review` (for `review_status` per row), `benchmark_membership` (cohort `n`). All scoring rows are written by the **existing** `score_and_persist` path — F19 adds no scoring columns.

**Role (F10):** add `'analyst'` following the existing `require_role(*roles)` pattern in `app/auth.py` (verified: roles are free strings on `profiles.role` / the local-auth `app_role` claim — no code enum). Migration 0038 relaxes/extends any `profiles.role` CHECK constraint to include `'analyst'` if one exists live; otherwise no DB change. Bulk endpoints require `admin | analyst`.

## API contracts
All endpoints tenant-scoped to the caller's `org_id`; every score payload carries `vci` + `formula_version` + cohort lineage (inherited from `score_and_persist`, unchanged).

- **`POST /bulk/jobs`** — `require_role('admin','analyst')`. Accepts **multipart CSV** (headers `org_name,notice_url`) **or JSON** `{label, rows:[{org_name, notice_url}]}`. Validates **≤ 200 rows** (reject 201+ → `400`) and each `notice_url` **well-formed** (scheme http/https, parseable host). **One-running-job-per-tenant guard:** if the caller's tenant already has a `bulk_job` in `status='running'` (or `'queued'`), reject with **`409`** and an honest message ("A screening job is already running for your organization — wait for it to finish before starting another."). This is a hard requirement because execution is **in-process, sequential BackgroundTasks**: without the guard a second 200-row job silently queues behind the first with no feedback (and would misbehave outright if the execution model ever changes). → **`202 {bulk_job_id}`**. Creates one `bulk_job` (`status='queued'`, `row_count=N`) + N `bulk_job_row` (`status='pending'`), then hands off to a **FastAPI background task**.
- **`GET /bulk/jobs`** — list, tenant-scoped (owner `org_id` only).
- **`GET /bulk/jobs/{id}`** — job + rows (paginated); 404 cross-org (never leak existence).
- **`GET /bulk/jobs/{id}/results`** — per **succeeded** row:
  ```
  { org_name, review_status,                       // 'draft' | 'in_review' | 'approved'
    overall,          // number OR null when vci.suppress → { overall:null, suppressed_reason:'low_confidence' }
    domain_scores[8], // 8 taxonomy domains (heatmap TAXONOMY_DOMAINS order); same suppression rule per cell
    cohort:{ n, relaxation_label },
    top_findings:[{code, domain, severity}]  // max 3, ranked by severity
    vci }
  ```
- **`GET /bulk/jobs/{id}/export.csv`** — `PlainTextResponse` (the `eval.py` `csv.writer` pattern). Results flattened, one org per row. **Suppressed cells rendered literally as `suppressed_low_confidence`.** The **first line is a notice row** (SME-set copy): `Screening intelligence — automated analysis, not expert-reviewed. Scores are draft-grade comparisons, not conclusions.` Vocabulary is **exposure / maturity only** — zero verdict terms (guardrail static test extended to the export header + every emitted cell).

### Gate semantics (MUST hold)
Bulk assessments are created by `score_and_persist`, which **already** enqueues each as SME **draft** (`get_or_create_review` → `AssessmentStatus.DRAFT`) and **never auto-approves**. Results endpoints serve **draft-grade** numbers and include `review_status` per row so the UI can badge them. F19 changes **nothing** about the gate — it only surfaces the draft state.

## Batch runner (`services/bulk.py` — orchestration only, no new scoring)
Per row, **sequentially**, each wrapped in its own `try/except` so one failure never sinks the job:
1. **Resolve org — screening-scoped, NEVER an existing customer tenant (cross-tenant trap).** Bulk **does not** call `_find_or_create_org(org_name)` (which resolves by name/slug and would attach the row to — and expose — an existing customer's org record). Instead it **always creates a fresh screening `organization`** (new uuid, `entity_type='target'`, `tenant_id='bulk:<owner_org_id>'`, `organization.name` namespaced `"<org_name> · screening <job8>"` so it can never collide with the single-assessment name/slug lookup in either direction). The display name shown in results comes from `bulk_job_row.org_name`, not `organization.name`. The scored assessment's `organization_id` is this screening org — so an analyst scanning 200 companies that happens to include one of our own customers scores that customer **fresh from the public notice only**, under the **bulk-job owner's** tenant, and **never reads or writes the customer's private org record**. Results are gated by `bulk_job` ownership, not by the screening orgs.
2. **Intake the URL** via the **shared** F01 path — `extract_from_url` → `decompose` → classify → persist `privacy_notice`/`notice_section`/`disclosure_clause`. This intake block is **factored out of `create_assessment` into a shared helper** so bulk and single intake are **one path** (no forked intake); `create_assessment` is refactored to call it (behavior unchanged).
3. **Score** by calling **`trigger_reassessment(notice_ids=[notice_id], triggered_by=...)`** — the verified kernel, which routes through `score_and_persist`. **No second scoring path** (MUST NOT). Row → `assessment_id = notice_id`, `status='succeeded'`.
4. **Honest failure mapping:**
   - extract/decompose/SSRF/HTTP error → `status='failed'`, `error` = the exception message (bounded, no secrets).
   - notice yields **no clauses** (kernel returns `skipped_no_clauses`) **or** org profile / population cannot be built → **`status='insufficient_profile'`** (honest — the org simply can't be benchmarked from what live scoring already has; **no invented cohort**). UI row text (SME-set): *"Not scored — we could not build a reliable company profile or peer comparison from public information. No score is shown rather than an unfair one."*
5. Update `bulk_job.completed_count`/`failed_count` after each row. Final `status`: all succeeded → `completed`; some succeeded + some failed/insufficient → **`partial`**; zero succeeded → `failed`. `finished_at = now()`.

**Sector heat strip** = aggregate **mean of each of the 8 domain scores across the job's succeeded rows** (suppressed cells excluded from the mean, count shown), computed via the `heatmap` domain taxonomy/aggregation — a measurement summary, not a ranking verdict.

## Frontend contract (`web/src/pages/bulk/` — replace the M-23/M-24 mock)
- **Upload step:** drag CSV or paste JSON → **client-side row-validation preview** (bad URLs / >200 rows flagged before submit) → submit → `202`.
- **Job list:** status chips, progress `completed/total`, **auto-poll every 5 s while `running`** (stop on terminal status).
- **Results grid:** sortable columns (org, overall, 8 domains, cohort `n`, VCI); **domain filter chips**; **"draft-grade" badge throughout**; **sector heat strip** on top (aggregate domain means). **Export CSV** button. A **score-cell click opens that assessment's report route** — the draft gold watermark shows naturally (no F19-specific watermark logic; it's the existing draft state).
- **Failed rows** render inline with their `error` text; **`insufficient_profile`** rows show a plain-English line ("Not enough of this org's notice could be profiled to benchmark it — no score was invented.").
- Suppressed cells render the suppression state (never a fabricated number). Empty/loading/error per existing customer-page conventions; reduced-motion honored on the poll spinner + heat strip.

## Connection flow
analyst uploads CSV → `202` → poll job → rows flip `pending → running → succeeded` → grid fills incrementally → filter to a domain (e.g. `tracking_cookies`) → sort worst-first → click org → **draft report opens (gold watermark)** → back → **Export CSV** (with the `not-expert-reviewed` notice embedded).

## Guardrails & confidence
- **Vocabulary:** exposure/maturity only; the guardrail static test is **extended to the CSV export** (header notice line + every cell) — zero verdict terms.
- **VCI suppression** (`vci.suppress`, threshold < 40) applied in **both** JSON results and CSV; CSV suppressed cells = literal `suppressed_low_confidence`.
- **Draft-grade** everywhere; nothing auto-approved; the report watermark is the existing draft watermark (never stripped in export).
- **No invented cohorts** for unprofilable orgs → honest `insufficient_profile`.
- **Row cap 200**, enforced server-side (client preview is convenience only).
- **Single scoring path:** scoring goes through `trigger_reassessment` → `score_and_persist`. Asserted by an import/wiring test (no forked scorer).

## Mocks
Replaces **M-23** (batch results queue) and **M-24** (clause-level evidence per flag) — mark both **Replaced** in `mock-tracker.md` on merge (real batch pipeline + real `derived_data_item`/finding evidence).

## Acceptance criteria
- **AC-1** `POST /bulk/jobs` with 200 valid rows → `202 {bulk_job_id}`; **201 rows → rejected** (no job created).
- **AC-2** A single **malformed-URL row fails alone**, other rows succeed, job ends **`partial`** (one bad row never sinks the batch).
- **AC-3** **Tenancy:** a job created under org A is **invisible** to org B on list/detail/results/export (404, no existence leak).
- **AC-4** **Suppression** appears in **both** JSON (`overall:null` + `suppressed_reason`, suppressed domain cells) **and** CSV (`suppressed_low_confidence`).
- **AC-5** **Export** contains the `screening intelligence — not expert-reviewed` notice line and **zero verdict terms** (guardrail test over the export).
- **AC-6** **Single code path:** scoring is reached only via `trigger_reassessment` → `score_and_persist` (import/wiring test; no forked scorer).
- **AC-7** An unprofilable org → row `insufficient_profile` (no fabricated score/cohort); a no-clause notice maps there too.
- **AC-8** Every succeeded row is **draft** (`review_status='draft'`, never auto-approved); score-cell click opens the report with the draft watermark.
- **AC-9** `analyst` can reach `/bulk/*`; `customer` cannot (403); admin can.
- **AC-10** **Cross-tenant trap:** a bulk row whose `org_name`/URL matches an **existing customer tenant** is scored into a **fresh screening org** — the resulting assessment's `organization_id` is **not** the existing customer's org id, the customer's private rows are never read or mutated, and nothing about the customer's org record leaks into the job. (Directly tested.)
- **AC-11** **One-running-job-per-tenant:** submitting a second job while the tenant already has a `running`/`queued` job → `409` (no second job created).

## Test gate
`tests/test_f19_bulk.py` — 201-row rejection (AC-1); malformed-URL row fails alone → `partial` (AC-2); cross-org invisibility (AC-3); suppression in JSON and CSV (AC-4); **export contains the draft-grade notice + zero verdict terms** — extend the guardrail static test to the export header (AC-5); **reassessment.py reuse** — assert the single code path via import test, no forked scorer (AC-6); `insufficient_profile` mapping (AC-7); draft-not-approved (AC-8); role gating `analyst`/`customer` (AC-9); **cross-tenant trap** — a row matching an existing customer org scores into a fresh screening org, never the customer's (AC-10); one-running-job-per-tenant `409` (AC-11). Frontend vitest: upload validation preview, incremental poll fill, suppressed/failed/insufficient cell states, draft-grade badge, export button.

## Open questions
- **OQ-1 [SME] — RESOLVED 2026-07-28 (acting SME).** Export notice line = *"Screening intelligence — automated analysis, not expert-reviewed. Scores are draft-grade comparisons, not conclusions."*; `insufficient_profile` row text = *"Not scored — we could not build a reliable company profile or peer comparison from public information. No score is shown rather than an unfair one."* Both plain-language, no internal vocabulary, no verdict terms.
- **OQ-2 [ENG]** Background execution: FastAPI `BackgroundTasks` (in-process, sequential) for R2; the one-running-job-per-tenant `409` guard (AC-11) makes the sequential model safe. Revisit a durable queue if job sizes/volume grow (kept out of scope to avoid a second execution model).
- **OQ-3 [PRODUCT/OD] — RESOLVED 2026-07-28 (owner).** Row cap **200** and **5 s** poll approved as spec'd. Added the one-running-job-per-tenant guard (AC-11) as a condition of the sequential execution model.

## Changelog
- 0.2 (2026-07-28): Owner-approved for build with three adjustments — (1) one-running-job-per-tenant `409` guard (AC-11) made explicit for the sequential BackgroundTasks model; (2) acting-SME set the export notice + `insufficient_profile` copy (OQ-1 RESOLVED); (3) cross-tenant trap hardened — bulk rows always score into a fresh screening org, never an existing customer tenant's record (AC-10, tested). OQ-3 RESOLVED (200-row cap / 5 s poll). Source: owner + acting SME.
- 0.1 (2026-07-28): Initial spec (DRAFT). Bulk screening surface on the verified `reassessment.py` kernel — `bulk_job`/`bulk_job_row` (migration 0038), `analyst` role, `POST /bulk/jobs` (CSV/JSON, ≤200), list/detail/results/export.csv; per-row intake (shared F01 helper) → `trigger_reassessment` → `score_and_persist` (single scoring path); draft-never-auto-approved; VCI suppression + guardrail extended to export; replaces F12 M-23/M-24. Not implemented — awaiting owner approval. Source: engineer (F19).
