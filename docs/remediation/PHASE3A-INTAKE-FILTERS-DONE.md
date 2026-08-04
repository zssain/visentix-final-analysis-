# PHASE 3A — Intake Filters (ARCH-001A) — Completion Record

**Date:** 2026-08-04 · **Commit before:** `8c4ed92` · **Commit after:** working tree, **no commits / no branch** per owner instruction (conflicts with `AGENTS.md` §1.4/§1.7 — logged in `logs/decision-log.md`).

## What shipped
Industry + State-privacy-law filters on the intake screen, **threaded end-to-end and behaviourally verified** — changing a filter changes the downstream score, not just a stored field.

### The chain that now lights up
`intake control → FormData → Form param → validation (reject unknown) → org row (real industry + industry_id + industry_source + jurisdiction_presence) → score_and_persist(refresh_profile=True) → _ensure_org_profile recomputes a NEW versioned profile → compute_ic(real industry) → industry_id → build_population cohort key · compute_rss(real jurisdiction_presence) → state_exposure → scores/percentile/heatmap → report + lineage.`

## Findings addressed
| ID | What changed | Files | Tests | Status |
|---|---|---|---|---|
| ARCH-001A | Two intake filters captured and **consumed**. Options come from the engine's real vocabulary (`config/org_profile_weights.json`) via `GET /config/intake-options` — no divergent hardcoded list. Backend validates against `industry_taxonomy` + `rss_state_lookup` (reject unknown → 422), writes real values onto the org with honest provenance (`industry_source` ∈ user_provided/system_default/unknown), and forces a fresh **versioned** profile (Hard Rule 6) so the change reaches the score. | `app/services/intake_options.py` (new), `app/routers/config_routes.py` (new), `app/routers/assessments.py`, `app/services/live_scoring.py`, `db/migrations/0044_org_industry_source.sql` (new), `scripts/db/apply_and_record.py`, `web/src/pages/customer/Intake.tsx`, `web/src/pages/customer/intake.css`, `app/main.py` | `tests/test_arch001a_intake_filters.py` (11), `web/src/test/Intake.test.tsx` (2) | **TESTED** (ARCH-001A thin slice; migration 0044 prod-apply BLOCKED-EXTERNAL) |
| QA-002 (industry selection) | Intake now has a real Industry dropdown sourced from the taxonomy; consumed by `compute_ic` → cohort. | as above | behavioural test 1 | **RESOLVED** |
| QA-003 (state/legal scope) | Intake now has a State-privacy-laws multi-select sourced from `rss_state_lookup`; consumed by `compute_rss` state_exposure. | as above | behavioural test 2 | **RESOLVED** |

## The behavioural proof (tests 1–2 — the whole point)
- **Industry is consumed:** `compute_org_profile(industry="retail")` → `industry_id=IND-01`; `industry="healthcare"` → `IND-04`. Different `industry_id` ⇒ different `build_population` cohort key (population.py:32). *(test_industry_changes_industry_id_and_cohort_key)*
- **Jurisdiction is consumed:** `jurisdiction_presence=["US-CA"]` (weight 1.0) vs `["US-CO"]` (0.65) → different RSS; `[]` → broad `_default`, distinct from a real state. *(test_jurisdiction_changes_rss, test_jurisdiction_none_uses_broad_default)*
- **Honest unknown:** explicit "Not sure / not listed" → `industry="unknown"`, `industry_source="unknown"`, **no** fabricated `industry_id`; blank leaves the org untouched (no clobber). *(test_apply_filters_unknown…, …blank_does_not_touch_org)*
- **Invalid rejected:** `industry=banana` / `jurisdictions=US-XX` → **422**, not a silent pass-through. *(test_invalid_filter_rejected_422)*
- **Options are the real vocabulary:** endpoint returns taxonomy industries + RSS jurisdictions; `_default` sentinel excluded. *(test_intake_options_payload, test_config_intake_options_endpoint)*
- **Frontend:** options load from `/config/intake-options`; multi-select round-trips; blank shows the honest-degradation note; submit appends `industry` + `jurisdictions` to the FormData. *(web Intake.test.tsx ×2)*

## Value sets (the engine's real vocabulary — not invented)
- **Industries** ← `industry_taxonomy` keys (retail→IND-01, healthcare→IND-04, financial_services/fintech→IND-05, technology/saas→IND-07, …) + explicit `unknown`.
- **Jurisdictions** ← `rss_state_lookup` codes: US-CA, US-NY, US-TX, US-CO, US-CT, US-VA, US-WA, US-FED, EU (the `_default` sentinel is not selectable).

## Schema note (AGENTS.md §2 — introspected first)
- `organization.jurisdiction_presence` (jsonb) **already existed** — no migration needed; only populated.
- `organization.industry_source` did not exist → **migration 0044** adds it (additive, nullable, idempotent `ADD COLUMN IF NOT EXISTS`). Registered in `apply_and_record.py::APPLY_NOW`.

## Gate (vs baseline)
```
cd web && npx tsc --noEmit  → 0
cd web && npx vitest run     → Test Files 9 passed (9) · Tests 83 passed (83)   [+2 vs Phase 2's 81]
cd web && npm run build      → 0
./.venv/bin/python -m pytest -q → 5 failed, 983 passed, 15 skipped in 252.12s (exit 1)
```
### Full backend suite vs baseline (`910 passed, 3 failed`)
- **Phase 3A:** `983 passed, 5 failed, 15 skipped` (+10 passing vs Phase 2's 973). New backend tests: `test_arch001a_intake_filters.py` (11).
- **Failure accounting (all explained, no new code regressions):**
  - Environmental live-DB failures (`test_embeddings*`, `test_schema_p1[disclosure_clause]`) — pre-existing, variance run-to-run.
  - `test_f02_ingestion_foundation::test_schema_migrations_rows_match_file_checksums` + `::test_apply_now_order_and_step_a_first` — the SAME two live-DB ledger tests from Phase 2, now also covering **0044** (both 0043 and 0044 are registered-but-not-applied per the owner's "Leave BLOCKED-EXTERNAL" choice). They go green when the migrations are applied.

## Migrations
- `db/migrations/0044_org_industry_source.sql` — additive/idempotent/no-RLS-change (existing table). **Prod apply = BLOCKED-EXTERNAL** (same posture as 0043): `PYTHONPATH=. ./.venv/bin/python -m scripts.db.apply_and_record`; verify `select column_name from information_schema.columns where table_name='organization' and column_name='industry_source';` returns a row.

## Removed
- The manual "set the pilot org's industry in the DB before intake" step in `docs/DEMO_RUNBOOK.md` — replaced by the intake filter (this feature). The remaining runbook items (profiling sanity-check, CQS gating) are kept and reworded.

## Notes for the next prompt (ARCH-001B / Phase 3 remainder)
- ARCH-001B: the full multi-step intake (org profile → data practices → benchmark config → scope preview → audience/template modes QA-013 + processing disclosure QA-012). The `assessment_job` (QA-011) + these two filters are the foundation to build on.
- Apply migrations 0043 + 0044 to make async intake + `industry_source` live (clears the 2 ledger-test reds).
- Remaining Phase-3 roadmap items: DATA-001/002/003, FE-001, AI-002/004, SEC-005/006/008, BACK-002, DATA-004, FIND-001.
