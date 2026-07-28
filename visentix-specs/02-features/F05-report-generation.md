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
See [`00-plan/mock-tracker.md`](../00-plan/mock-tracker.md): **M-05**, **M-09**, **M-10**, **M-03** all **Replaced** (2026-07-27) — advisor prose from the frozen snapshot only; provenance ribbon from the authoritative `report_snapshot.id`/frozen-at; lineage descriptions from `GET /api/formulas` (`formula_version.description`); exemplars from `disclosure_clause.is_exemplar`. Exemplar *content* still pending SME re-review.

## Addendum — Recommendation evidence stacks (SHIPPED 2026-07-28)

> **Shipped:** `services/evidence.py` + `GET /assessments/{id}/findings/{fid}/evidence`; assembled + frozen once at approval via a hook in `review.approve` (`freeze_evidence_on_approval`, idempotent → DIR-010); `recommendation_evidence` table (migration 0041, live); `EvidenceStack` drawer in the report FindingsTable. Obligation context from `clause_obligation` (verbatim register), one approved exemplar or one of three distinct honest-absence lines, ≤2 resolved-enforcement precedents, `risk_reduction_delta` NULL. `tests/test_f05_evidence.py` (6, AC-E1..E5). **Implementation note:** the frozen stack lives in `recommendation_evidence` (the durable artifact) rather than inline in the snapshot JSON — byte-identity holds because rows are written once at approval and never re-assembled.


Each Recommendation becomes an **expandable evidence stack** that shows *why* it's there, using data that already exists — obligation context, an approved exemplar, and resolved enforcement precedent. **Assembled once, at SME review-approval / snapshot-freeze time, and FROZEN into the snapshot** (DIR-008 / Hard Rule 6 — presentation never recalculates; served from the snapshot, never re-assembled at render).

### Data (new — amends schema.md)
`recommendation_evidence(id uuid pk, finding_id fk→risk_finding, assessment_id fk→privacy_notice(notice_id), obligation_refs jsonb [{obligation_id, similarity, matched_terms}], exemplar_clause_id fk→disclosure_clause null (SME-**approved** only), enforcement_refs jsonb [{enforcement_id, similarity}] — **resolved enforcement only, max 2**, risk_reduction_delta numeric null, formula_version_id text, confidence numeric, generated_at)`.
Reads: `clause_obligation` (obligation context — the F05 addendum's obligation source; scope recorded in `logs/eval/obligation_match_scope.json`), `disclosure_clause` (`is_exemplar=true, exemplar_status='approved'`), `enforcement_record` (`resolution_status='resolved'`).
Also documents the **live-but-undocumented `recommendation_library`** table (`finding_type_code, title, body_template, severity_bucket`) — the origin of Recommendations content.

### Assembly (hook: `report/assembly.py`)
For each **confirmed** finding in the report, `assemble_report` builds one `recommendation_evidence` row and embeds it in the snapshot payload:
- **Obligation context** — from `clause_obligation` for the finding's cited clauses (obligation + similarity + matched_terms). Copy register is **verbatim from `obligation_match.py`**: *"Matches are EXPOSURE CONTEXT only — never a legal conclusion. Unverified obligations (effective_date=NULL) carry reduced confidence."*
- **Exemplar** — a single **SME-approved** clause (`exemplar_status='approved'`) for the finding's domain, or an **honest absence line** (no approved exemplar for this domain yet). Never a non-approved exemplar.
- **Enforcement precedent** — up to **2** rows from **resolved** enforcement only (`resolution_status='resolved'`), each with regulator + year + similarity.
- **`risk_reduction_delta` — NULL forever.** intelligence-logic.md defines **no** risk-reduction formula; the column exists only for a future expert-defined formula. It is never computed or invented here (MUST NOT).
- **Honest absence, three distinct claims:** an org whose cohort was **not** matched (out of `obligation_match_scope`) shows *"obligation context not yet available"*; a clause with matches below the 0.35 floor shows *"no related obligations above the similarity threshold"*; no approved exemplar shows *"no approved exemplar for this domain yet."* These are never conflated.

### API
`GET /assessments/{id}/findings/{fid}/evidence` → the frozen stack **from the snapshot** (org-scoped; 403 cross-org). Never assembled at render. Every element echoes its refs for the lineage drawer.

### Acceptance criteria (addendum)
- **AC-E1** Evidence stacks are assembled at approval/freeze and served from the snapshot; a second GET/PDF pull is byte-identical (Hard Rule 6). Nothing re-assembles at render.
- **AC-E2** Enforcement refs are **resolved-only** and capped at 2; obligation context uses the verbatim exposure-context register; exemplars are **approved-only**.
- **AC-E3** `risk_reduction_delta` is **null** in every stack (no formula exists); the UI shows the delta row only when non-null (i.e. never, today).
- **AC-E4** Absence states render the three distinct honest claims (out-of-scope vs below-floor vs no-approved-exemplar), never conflated.
- **AC-E5** Cross-org evidence read → 403.

## Test gate
Report assembly integration tests, byte-identity regression test, guardrail filter tests (incl. source-excerpt exemption and closing-matter copy), PDF/interactive parity checks, section-level vitest. **Addendum:** evidence uses resolved-enforcement-only + approved-exemplars-only; three honest-absence states; delta stays null when the formula is absent; snapshot byte-identity with stacks embedded; cross-org evidence 403.

## Changelog
- 2026-07-28 (engineer, DRAFT pending approval): **Addendum — recommendation evidence stacks.** New `recommendation_evidence` table + `GET /assessments/{id}/findings/{fid}/evidence`; stacks assembled at approval/freeze in `report/assembly.py` and frozen into the snapshot (never render-time). Obligation context (from `clause_obligation`, verbatim exposure-context register), one SME-approved exemplar or honest absence, ≤2 resolved-enforcement precedents, and a `risk_reduction_delta` that is **null forever** (no formula in intelligence-logic — never invented). Documents the live `recommendation_library` table (Recommendations origin). AC-E1..E5. **Not yet implemented — awaiting owner approval of this spec + F18-rewrite.md.**
- 2026-07-27 (engineering closeout): **M-03/M-05/M-09/M-10 Replaced.** M-03 — report assembly sources BenchmarkLanguage exemplars from `disclosure_clause` (`is_exemplar=true, exemplar_status=approved`), domain-mapped via `config/clause_taxonomy.json`, honest absence per domain. M-05 — `AdvisorNote` renders advisor prose from the frozen snapshot only (hardcoded fallback removed; honest absence + regression test). M-09 — `ReportView` threads the authoritative `report_snapshot.id`/frozen-at into the provenance ribbon and sections. M-10 — new `GET /api/formulas` serves `formula_version.description`; lineage drawers read it (hardcoded copy removed). Also (Workstream B): BenchmarkLanguage show-differences diff toggle (gold added / warm-gray strikethrough removed, off by default, accessible); guardrails.test.ts extended over Recommendations + RiskReduction static copy. **SME re-review of the 16 exemplars' content still required.**
- 2026-07-27: Recorded three OD closures affecting the report (all ai_reviewed, pending human owner confirmation): **OD-02** reader-register names (Executive/Practitioner/Plain-language, flag-gated), **OD-01** descriptive-only crosswalk copy, **OD-03** advisor-hero on mobile with both mitigations. No render behavior changed. Phase-1 pilot-readiness pass.
- 2026-07-16: Report visual overhaul (user feedback: "reports look ugly"): duplicate provenance ribbon removed — it renders once, globally, in ReportView, now carrying the formula version; Cover rebuilt as an editorial page (eyebrow, larger Fraunces org name, refined meta row) with the Workstream-B score dial (`ScoreDial.tsx` — static SVG arc colored by the shared score band, maturity chip, VCI badge only when the payload carries a real VCI); all 12 sections now render as white cards with Fraunces headings and a gold accent rule; print styles preserved for the PDF renderer.
- 2026-07-16: Added a Mocks section keyed to the mock-tracker (template conformance); no behavioral change.
- 2026-07-15: Added closing matter (Next Steps page + back cover) per Appendix H prototype review; AC-5 and guardrail notes added.
