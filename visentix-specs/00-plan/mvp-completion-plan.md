# MVP Completion Plan

**Version:** 1.2 · 2026-07-16
**Goal:** Take the current build (Phase 11 complete, full test suite green) to a **client-shippable MVP**: a real customer can submit a notice, an SME can review, and a reproducible, branded, fully real-data report is delivered — with zero mock data and all open decisions resolved.

**Definition of done:** [`mock-tracker.md`](mock-tracker.md) all rows Replaced · all 12 report sections spec-complete · [`open-decisions.md`](open-decisions.md) OD-01–OD-05 Decided · demo runbook passes end-to-end on production deploy · first pilot report delivered.

---

## Workstream A — Mock closure (highest priority)

The live [`mock-tracker.md`](mock-tracker.md) (M-01–M-14) is the punch list. Order below is dependency-sorted: backend routes first, then frontend wiring.

### A1. New backend routes needed (blockers)
| Mock | Route to build | Data source | Est. |
|---|---|---|---|
| M-06 | `GET /api/monitoring/trend?org_id` | F-012 outputs from `formula_version` + `report_snapshot` | M |
| M-07 | `GET /api/monitoring/events?org_id` | `monitoring_event` table (exists in schema) | S |
| M-08 | `GET /api/monitoring/alerts?org_id` | F-013 outputs + `enforcement_record` | M |
| ~~M-11~~ | ~~`GET /api/codex`~~ **Built** as `GET /findings/codex` (audit 2026-07-16; tracker row Replaced) | `finding_type` catalog table | — |
| M-13 | `GET/POST /api/admin/gate-mode` | new `platform_setting` row or config table | S |
| M-14 | `POST /api/admin/trigger-assessment` | replace `not_implemented` stub with real batch pipeline call | M |

### A2. Frontend wiring only (backend already exists)
| Mock | Change |
|---|---|
| ~~M-01~~ | **Done** (audit 2026-07-16): Intake wired to real `POST /assessments/`; fixture gone — tracker row Replaced |
| M-02 | Read real `ssrf_protected` flag from intake response for "verified source" badge |
| M-03 | BenchmarkLanguage queries `disclosure_clause WHERE is_exemplar = true` (requires ≥1 SME-approved exemplar per demo cohort — see A3) |
| ~~M-04~~ | **Done** (audit 2026-07-16): counters wired to real `GET /admin/training-stats` — tracker row Replaced |
| M-05 | Mobile Advisor prose rendered from frozen `report_snapshot` Advisor layer — never regenerated |
| M-09 | Provenance ribbon reads real `report_snapshot.id` + `snapshot_frozen_at` threaded through report fetch |
| M-10 | Lineage drawer descriptions from `formula_version.description` (populate NULLs — content task, see A3) |
| M-12 | Cohort `n` always from live `benchmark_membership` count — remove every static `n=30` |

### A3. Content/data prerequisites
- Populate `formula_version.description` in plain English for F-001–F-014 (source: `01-foundation/intelligence-logic.md`).
- Seed and SME-approve at least one de-identified exemplar per demo domain via Workbench so M-03 renders.
- Verify the demo cohort has n ≥ `LOW_CONFIDENCE_COHORT_N` or intentionally exercise the low-confidence footer.

**Exit gate A:** [`mock-tracker.md`](mock-tracker.md) rows all `Replaced`; grep for hardcoded `S-2041`, `n=30`, `142 / 31 / 12` returns nothing; frontend runs with backend down shows honest error states, not stale mocks.

## Workstream B — Report section gap closure

The 11 report-section components (all files exist in `web/src/report/sections/`; gaps migrated here from the archived UI_SPEC section-gap table — F05 owns these as ACs):

Audited against the code 2026-07-16 — statuses verified, not assumed:

1. **Cover.tsx** — ✅ done (2026-07-16): gold hairline + provenance ribbon + **score dial with band-colored arc, maturity band, and VCI badge** (`ScoreDial.tsx`); duplicate cover ribbon removed (renders once, globally).
2. **ExecutiveSummary.tsx** — ✅ done: register toggle built as specced (renders when the payload supplies alternative registers; labels pending OD-02).
3. **RiskDashboard.tsx** — ✅ done: ScoreCell lineage + InfoButton on every metric, "click any score" hint.
4. **BenchmarkIntelligence.tsx** — ✅ done: CohortLabel + low-confidence warning (UI); live n still M-12 upstream. Audit also removed invented `?? 50/75` chart fallbacks.
5. **RegulatorExposure.tsx** — ✅ done: CodexTooltip on finding codes.
6. **FindingsTable.tsx** — ✅ done: AdvisorNote integrated per finding.
7. **CompoundRisk.tsx** — ✅ done: ScoreCell lineage on the compound score. Audit removed a hardcoded `vci={75}`.
8. **BenchmarkLanguage.tsx** — ⚠️ partial: side-by-side comparison built; ❌ **show-differences diff toggle (gold added / warm-gray-strikethrough removed) still missing**. Audit fixed the `?? 30` cohort fallback + added CodexTooltip.
9. **Recommendations.tsx / RiskReduction.tsx** — ❌ open: no automated banned-term test covers these sections' static copy yet (extend `guardrails.test.ts`).
10. **Traceability.tsx** — ✅ UI done: snapshot ID + formula version displayed; real IDs still M-09/M-10 upstream.
11. **TrendPanel.tsx** — ✅ done: sparkline + improvement-colored delta (DDR-009) + `no_prior_history` state.

Remaining WB items: **BenchmarkLanguage diff toggle** (8) · **Recommendations guardrail test** (9). The 2026-07-16 audit also brought every section up to DDR-007 (mark on all 12 sections + both lineage drawers) and replaced fake `S-0000` snapshot fallbacks with honest absence.

**Exit gate B:** PDF export byte-identical on double pull of same snapshot; every section carries the "Intelligence, not legal advice" mark per DDR-007 placement rules; visual QA at 375/768/1280.

## Workstream C — Open decisions (product, not code)

Tracked in the live [`open-decisions.md`](open-decisions.md) register (OD-01–OD-05, each with a recommendation, owner, and status). All five currently sit at **Recommended** — they need sign-off, not more analysis. Decide them, then propagate per the register's close-out procedure. Summary:

| ID | Decision needed | Recommendation to unblock | Owner |
|---|---|---|---|
| OD-01 | Framework Crosswalk copy | Descriptive-only language; ship shell now | Product |
| OD-02 | Reader register names | Executive / Practitioner / Plain-language, flag-gated | Product |
| OD-03 | Advisor-hero-on-mobile default | Approve with the two specced mitigations | Product |
| OD-04 | Real SME names in attribution | Keep "The Visentix Privacy Desk" for MVP | SME team |
| OD-05 | Low-confidence cohort n | Confirm n=10 as `LOW_CONFIDENCE_COHORT_N` | Data |

## Workstream D — Hardening & launch

1. **Auth hardening** — the custom local JWT system (ES256, localStorage profile, `local_users.json`) is fine for demo; before a real client: move seed users to DB, add token rotation/expiry review, rate-limit login, audit RLS policies once more.
2. **Deployment** — finish the Cloudflare Pages deploy (already scripted); stand up production API host; environment-split config; secrets audit (`.gitignore` hygiene already done).
3. **Uncommitted docs** — commit `UI_SPEC.md`, `visentix-design.md`, `visentix-screens.md` edits; adopt this spec repo as their successor.
4. **Demo runbook** — re-run DEMO_RUNBOOK.md end-to-end against production; record a fallback demo video.
5. **Pilot delivery** — one real design-partner notice through the full pipeline with SME review gate ON (`expert_review` mode), delivered as approved (teal-ribbon) PDF. This is the business's stated Success Metric #1.

## Suggested sequence (3 sprints)

| Sprint | Focus |
|---|---|
| 1 | A1 backend routes + A3 content + OD decisions locked |
| 2 | A2 frontend wiring + B section gaps 1–6 |
| 3 | B sections 7–11 + D hardening + pilot delivery |

**Test discipline:** every workstream item adds/updates tests; the full suite must remain green. New monitoring routes need contract tests; report reproducibility needs a byte-identity regression test.

## Changelog
- 1.2 (2026-07-16): Code audit trued up both workstreams. Workstream A: M-01/M-04/M-11 verified done (marked in A1/A2); M-06–M-08 clarified as *unbuilt surfaces*, not mocked ones (F07 status corrected). Workstream B: per-item verified statuses recorded — 8 of 11 done; remaining: Cover VCI dial, BenchmarkLanguage diff toggle, Recommendations guardrail test.
- 1.1 (2026-07-16): Repointed the MOCK TRACKER and Open Decisions references from the archived `UI_SPEC.md` to the new live registries [`mock-tracker.md`](mock-tracker.md) and [`open-decisions.md`](open-decisions.md); no scope change.
- 1.0 (2026-07-15): Initial completion plan derived from the codebase's MOCK TRACKER and section-gap tables.
