# MVP Completion Plan

**Version:** 1.1 · 2026-07-16
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
| M-11 | `GET /api/codex` | `finding_type` catalog table (exists, real codes) | S |
| M-13 | `GET/POST /api/admin/gate-mode` | new `platform_setting` row or config table | S |
| M-14 | `POST /api/admin/trigger-assessment` | replace `not_implemented` stub with real batch pipeline call | M |

### A2. Frontend wiring only (backend already exists)
| Mock | Change |
|---|---|
| M-01 | Intake explorer reads `POST /api/assessments` → real `disclosure_clause` rows; delete static JSON fixture |
| M-02 | Read real `ssrf_protected` flag from intake response for "verified source" badge |
| M-03 | BenchmarkLanguage queries `disclosure_clause WHERE is_exemplar = true` (requires ≥1 SME-approved exemplar per demo cohort — see A3) |
| M-04 | Workbench training-label counters from `GET /api/admin/health` training_stats |
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

1. **Cover.tsx** — gold hairline rules, VCI dial, provenance ribbon.
2. **ExecutiveSummary.tsx** — reader-register toggle (blocked by OD-02; build behind a feature flag with placeholder register names, swap labels on decision).
3. **RiskDashboard.tsx** — lineage drawer affordance (dotted underline) on every score cell.
4. **BenchmarkIntelligence.tsx** — honest cohort-size display (live n, M-12).
5. **RegulatorExposure.tsx** — Codex tooltips on finding codes.
6. **FindingsTable.tsx** — integrate AdvisorNote component per finding.
7. **CompoundRisk.tsx** — lineage drawer on compound scores.
8. **BenchmarkLanguage.tsx** — confirm slider fully replaced by side-by-side diff with show-differences toggle (per UI_SPEC §3).
9. **Recommendations.tsx / RiskReduction.tsx** — guardrail compliance pass: run banned-term filter over static copy; verify exposure/maturity language only.
10. **Traceability.tsx** — snapshot ID + formula version display (M-09/M-10).
11. **TrendPanel.tsx** — sparkline + delta (improvement-colored per DDR-009) + clean `no_prior_history` state.

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
- 1.1 (2026-07-16): Repointed the MOCK TRACKER and Open Decisions references from the archived `UI_SPEC.md` to the new live registries [`mock-tracker.md`](mock-tracker.md) and [`open-decisions.md`](open-decisions.md); no scope change.
- 1.0 (2026-07-15): Initial completion plan derived from the codebase's MOCK TRACKER and section-gap tables.
