# MOCK TRACKER — the MVP mock-closure punch list

**Version:** 1.5 · 2026-07-16
**Authority:** this is the live, canonical tracker of every mock in the product. It replaces the `MOCK TRACKER` section of the archived `docs/old-docs/UI_SPEC.md`. `00-plan/mvp-completion-plan.md` Workstream A drives these to closure; each feature spec's Mocks section points here.

**Rule (unchanged):** every mock must be replaced with real data before shipping to a real client. Never display a hardcoded score, cohort `n`, snapshot ID, or count. Status values: **Open** (still mocked) · **In progress** · **Replaced** (real data wired, verified).

**Definition of done:** every row below `Replaced`, and `grep` for hardcoded `S-2041`, `n=30`, `142 / 31 / 12` returns nothing (Workstream A exit gate).

| ID | Feature | Screen | What's mocked | Real source | Status | Removal plan |
|---|---|---|---|---|---|---|
| M-01 | F01 | Intake & Decomposition Explorer | Clause extraction simulated with a static JSON fixture while the LLM classifier is offline | `POST /api/assessments` → real `disclosure_clause` rows | Open | Backend `assessments.py` exists; wire to real decomposition output, delete fixture |
| M-02 | F01 | Intake & Decomposition Explorer | "verified source" badge always shown on URL fetch success | Real `ssrf_protected` flag in the intake response | Open | Backend already validates SSRF; frontend reads the flag |
| M-03 | F05/F06 | Clause Comparison (BenchmarkLanguage) | Exemplar clause hardcoded as a static string | `disclosure_clause WHERE is_exemplar = true` | Open | SME must clean + approve ≥1 exemplar per demo cohort via Workbench first |
| M-04 | F06 | SME Workbench — de-id checker | Training-label counts hardcoded 142 / 31 / 12 | `GET /api/admin/health` training_stats (or `training_label` count) | Open | Health route exists — surface stats |
| M-05 | F05 | Mobile Advisor view | Advisor Note prose hardcoded house-voice text | Frozen `report_snapshot` Advisor layer | Open | Render from snapshot, never regenerate |
| M-06 | F07 | Continuous Monitoring dashboard | Sparkline is a static array of scores | F-012 trend-delta outputs (`formula_version` + `report_snapshot`) | Open | Build `GET /api/monitoring/trend?org_id` |
| M-07 | F07 | Continuous Monitoring dashboard | Change feed is 4 hardcoded events | `monitoring_event` table, filtered by org | Open | Build `GET /api/monitoring/events?org_id` (table exists) |
| M-08 | F07 | Continuous Monitoring dashboard | Alert-center cards are static | F-013 alert outputs + `enforcement_record` | Open | Build `GET /api/monitoring/alerts?org_id` |
| M-09 | F05/F07 | Report — Cover, Traceability | Provenance ribbon shows hardcoded `S-2041`, date `2026-06-19` | Real `report_snapshot.id` + `snapshot_frozen_at` | Open | Stored already; thread through report fetch |
| M-10 | F05 | Lineage drawer | Formula plain-language descriptions hardcoded | `formula_version.description` column | Open | Populate NULL descriptions (content task, Workstream A3) |
| M-11 | F08 | Finding Codex | Codex entries are a static JSON array | `finding_type` catalog table (real codes) | Open | Build `GET /api/codex` |
| M-12 | all | All screens | Cohort size shown as `n=30` everywhere | Live `SELECT COUNT(*) FROM benchmark_membership WHERE cohort_id = …` | Open | Never display a static n; always live-query |
| M-13 | F09 | Admin Console | Global Gate Mode simulated locally in React | `GET/POST /api/admin/gate-mode` (new `platform_setting`) | Open | Build the endpoints; UI reads/writes real state |
| M-14 | F09 | Admin Console | Trigger Batch Assessment simulated with a delay | `POST /api/admin/trigger-assessment` | Open | Replace the `not_implemented` stub with the real batch pipeline call |
| M-15 | F12 | Quarterly Report reader page | Publication snapshot id + cover corpus counts (orgs / industries / jurisdictions / clauses) hardcoded in `mockData.ts` | Frozen publication snapshot metadata (DIR-010) | Open | Build quarter-close freeze; read real counts (AC-5, Hard Rule 7) |
| M-16 | F12 | Quarterly Report reader page | Five named Intelligence Indicators + QoQ deltas hardcoded | Market-average aggregates per `formula_version`, each with VCI | Open | Build indicator aggregation over the corpus |
| M-17 | F12 | Quarterly Report reader page | Section aggregates — industry rankings, regulator activity, AI-governance trend, disclosure trends, compound patterns | Corpus aggregation from `derived_data_item` / F-012 deltas | Open | Build the aggregation layer shared with bulk analysis |
| M-18 | F12 | Quarterly Report reader page | Benchmark Spotlight excerpts hardcoded | SME-approved + de-identified exemplars above the minimum-sample threshold (F06 pipeline) | Open | Wire to approved exemplar store; enforce suppression (AC-6) |
| M-19 | F11 | Partner Portal | Partner contract + client workspaces (usage, status, branding flags) hardcoded in `mockData.ts` | `partner`, `client_workspace` tables + live usage, scope-isolated (DIR-005) | Open | Build tenancy + workspace CRUD; enforce partner isolation |
| M-20 | F11 | Partner Portal | API keys + per-contract usage / rate limits | `api_key`, `usage_record` metering | Open | Build key issuance + real usage metering; enforce limits server-side |
| M-21 | F11 | Partner Portal | Anonymized feed catalog (schema, refresh, permitted-use, VCI, suppression flag) | `feed_snapshot` aggregates with min-sample suppression (DIR-006) | Open | Build feed aggregation + server-enforced suppression |
| M-22 | F11 | Partner Portal | Branding config + report templates | Partner branding store applied by the report template engine | Open | Persist branding; wire template engine to branded render |
| M-23 | F12 | Bulk Analysis | Batch results — ranked company queue (exposure score, VCI, cohort n, top issues) hardcoded in `mockData.ts` | Batch pipeline over the aggregation layer (shared with M-17); scores from `derived_data_item` | Open | Build the batch pipeline; rank from real scores |
| M-24 | F12 | Bulk Analysis | Clause-level evidence snippets per flag | `disclosure_clause` rows + finding-type classification, with VCI | Open | Link each flag to real clause evidence (AC-3) |
| M-25 | F13 | Framework Crosswalk | Crosswalk mappings (domain/code → framework citation + note) hardcoded in `mockData.ts` | `framework_reference` table + `finding_type`, via `GET /api/crosswalk` | Open | Build mapping table + endpoint; expert signs off descriptive copy (OD-01), then swap |
| M-26 | F14 | Trust Language Studio | Rewrite prompts (per-domain gap status, current excerpt, suggested pattern, rationale, cohort n) hardcoded in `mockData.ts` | Authored `rewrite_pattern` library + `disclosure_clause` (org clauses + `is_exemplar` patterns), via `GET /api/rewrite` | Open | Author + SME-sign-off the pattern library; wire the endpoint over real gaps + approved exemplars |

## Changelog
- 1.5 (2026-07-16): Registered M-26 for the F14 Trust Language Studio, built UI-only against mock patterns ahead of the authored pattern library + backend.
- 1.4 (2026-07-16): Registered M-25 for the F13 Framework Crosswalk Explorer, built UI-only against mock citations ahead of the `framework_reference` backend + OD-01 copy sign-off.
- 1.3 (2026-07-16): Registered M-23–M-24 for the F12 Bulk Analysis workflow, built UI-only against mocks ahead of the batch pipeline.
- 1.2 (2026-07-16): Registered M-19–M-22 for the F11 Partner Portal, built UI-only against mocks ahead of the tenancy/metering/feed backend.
- 1.1 (2026-07-16): Registered M-15–M-18 for the F12 Quarterly Report reader page, built UI-only against mocks ahead of the aggregation backend. Every displayed figure on `/quarterly` is mocked; real sources and removal plans recorded per row.
- 1.0 (2026-07-16): Migrated the MOCK TRACKER out of the archived `UI_SPEC.md` into the live spec system, keyed each row to its owning feature spec, and added an explicit Status column so MVP mock-closure is measurable inside the specs.
