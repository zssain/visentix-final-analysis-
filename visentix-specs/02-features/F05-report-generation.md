# F05 — Report Generation (12 Sections, Snapshots, PDF)

**Status:** shipped (section gaps per MVP plan Workstream B) · **Release:** R1 · **Depends on:** F04, F06, design-system.md, business-logic.md §2/§5

## Purpose
Assemble the 12-section audit-firm-grade report from derived intelligence objects, freeze it as an immutable snapshot (Analyst + Advisor layers both frozen), render interactively at `/reports/:assessmentId` with PDF parity, and guarantee byte-identical re-pulls.

## Sections
Cover · Executive Summary · Risk Dashboard · Benchmark Intelligence · Regulator Exposure (9×8 heatmap) · Disclosure Findings · Compound Risk · Benchmark Language (side-by-side clause diff) · Recommendations · Risk Reduction · Traceability · Trend & Emerging Risk.

**Closing matter (added from Appendix H prototype):** after Section 12, the report carries a **Next Steps page** (how to operationalize the findings: share internally, build an action plan, validate & re-assess, upgrade to Continuous Monitoring) and a **branded back cover** ("Thank you for your trust" + contact + confidentiality line). Guardrail notes: closing matter is marketing-adjacent copy and still passes the banned-term filter; the monitoring upsell is phrased as capability ("ongoing visibility"), never as risk pressure; the confidentiality line matches the cover's. Closing matter is frozen into the snapshot like every other page.

## Data
Writes: `report_snapshot` (S-#### id, frozen_at, formula/benchmark versions, full payload, draft/approved status). Reads: `derived_data_item` only (DIR-008 — presentation never recalculates).

## Behavior
1. **Narrative engine:** LLM rephrases finding narratives → verification pass → banned-term filter (with source-excerpt handling) → deterministic fallback on failure. Advisor Note prose frozen into snapshot; **never regenerated at render** (M-05).
2. **Snapshot lifecycle:** draft (gold ribbon + diagonal DRAFT watermark, `instant_draft` mode) → SME approval → approved (teal Reproducible ribbon). Provenance ribbon on every report page from real snapshot fields (M-09).
3. **Furniture:** lineage drawer on every number, Codex tooltip on every code (PDF appends Codex appendix), "Intelligence, not legal advice" mark per DDR-007, reader-register toggle — **Executive / Practitioner / Plain-language**, flag-gated (OD-02 Decided 2026-07-27, ai_reviewed). The framework-crosswalk copy in the report is **descriptive-only** (OD-01 Decided 2026-07-27, ai_reviewed). On mobile the Advisor layer may lead with the two OD-03 mitigations (thumb-reachable View Switch, full-screen lineage sheet) — OD-03 Decided 2026-07-27 (ai_reviewed). All three pending human owner confirmation.
4. **Benchmark Language:** side-by-side diff, gold=exemplar-adds / gray-strikethrough=weaker phrasing, show-differences-only toggle, honest cohort footer (live n, date, low-confidence rule).
5. **PDF renderer:** parity with interactive view; double-pull of same snapshot is byte-identical.

## API contracts
- `POST /api/assessments/:id/report` → creates snapshot (respects gate mode).
- `GET /api/reports/:snapshot_id` → full frozen payload incl. snapshot metadata.
- `GET /api/reports/:snapshot_id/pdf` → rendered PDF.

## Guardrails & confidence
Banned-term filter is a hard gate on all narrative content including Recommendations/Risk Reduction static copy. Low-VCI items suppressed before assembly. Every displayed figure traces to a derived_data_item.

## Acceptance criteria
- AC-1 Two consecutive PDF pulls of one snapshot are byte-identical.
- AC-2 Draft/approved visual states match DDR-001; approval flips watermark→teal without recomputing content.
- AC-3 All section gaps in MVP plan Workstream B closed; all 12 sections render real data with lineage affordances.
- AC-4 Guardrail scan of a full generated report returns zero banned terms.
- AC-5 Closing matter (Next Steps + back cover) renders from the snapshot in both interactive and PDF outputs and passes the banned-term filter.

## Mocks
See [`00-plan/mock-tracker.md`](../00-plan/mock-tracker.md): **M-05** (mobile Advisor prose), **M-09** (provenance ribbon S-2041), **M-10** (lineage-drawer descriptions), and **M-03** (exemplar clause, shared with F06).

## Test gate
Report assembly integration tests, byte-identity regression test, guardrail filter tests (incl. source-excerpt exemption and closing-matter copy), PDF/interactive parity checks, section-level vitest.

## Changelog
- 2026-07-27: Recorded three OD closures affecting the report (all ai_reviewed, pending human owner confirmation): **OD-02** reader-register names (Executive/Practitioner/Plain-language, flag-gated), **OD-01** descriptive-only crosswalk copy, **OD-03** advisor-hero on mobile with both mitigations. No render behavior changed. Phase-1 pilot-readiness pass.
- 2026-07-16: Report visual overhaul (user feedback: "reports look ugly"): duplicate provenance ribbon removed — it renders once, globally, in ReportView, now carrying the formula version; Cover rebuilt as an editorial page (eyebrow, larger Fraunces org name, refined meta row) with the Workstream-B score dial (`ScoreDial.tsx` — static SVG arc colored by the shared score band, maturity chip, VCI badge only when the payload carries a real VCI); all 12 sections now render as white cards with Fraunces headings and a gold accent rule; print styles preserved for the PDF renderer.
- 2026-07-16: Added a Mocks section keyed to the mock-tracker (template conformance); no behavioral change.
- 2026-07-15: Added closing matter (Next Steps page + back cover) per Appendix H prototype review; AC-5 and guardrail notes added.
