# F17 — Evaluation Harness (Measurement Only)

**Status:** proposed
**Release:** R2
**Owner:** eng (harness) + SME (gold labels, golden-notice blessing)
**Depends on:** intelligence-logic.md §2/§3/§7/§8, schema.md, F01 (decompose + `is_noise`), F03 (benchmark/percentile), F04 (F-004 enforcement), F06 (SME workbench, `training_label`, `assessment_review`), F09 (Admin Console)

## Purpose
Give the platform an honest, repeatable **measurement** layer: how accurate is clause classification, is the VCI confidence signal actually catching errors, do the deterministic scores move in the directions intelligence-logic.md claims, are benchmark percentiles well-formed, and what is the human-precision rate of findings. **This feature MEASURES; it never tunes.** No weight, threshold, taxonomy, or formula is changed here. Every result either shows real numbers or says "awaiting SME labels", and every recommendation names an owner (SME vs eng) — the harness itself fixes nothing.

## Users & entry points
- **SME** — labels the gold set and blesses/swaps golden notices via a labeling view that reuses F06 workbench idioms; route `/eval/label`. CSV export/import for offline labeling.
- **Eng / CI** — runs the eval scripts (`scripts/eval/*`) and the golden-notice CI diff; reads `INTELLIGENCE-QUALITY.md`.
- **Admin** — sees the finding **precision** panel (confirm/edit/dismiss rate per finding_type) in the Admin Console (F09).

## Data
- **New:** `gold_label` (migration — amends schema.md §2): `label_id` (pk), `clause_id` (fk → disclosure_clause), `labeler`, `labeled_at`, `gold_domain` (one of the 8 + `other`), `verdict` (correct/incorrect/ambiguous vs the machine `category_v2`), `note`, `gold_set_version`. **The harness pre-fills NOTHING** — `gold_domain`/`verdict` are only ever written by a human labeler (or a human-authored CSV import).
- **Reads (never writes):** `disclosure_clause` (`category_v2`, `nlp_confidence_v2`, `is_noise`, `embedding`, source lineage via section→notice→org), `derived_data_item` (scores + VCI), `risk_finding` (`finding_type_code`), `training_label` (`action` ∈ confirmed/edited/dismissed, `finding_id`), `assessment_review` (`finding_reviews` jsonb), `report_snapshot` (golden-notice freeze), `benchmark_membership` / percentiles (F03).
- **Golden files:** `tests/golden/notices/<slug>.json` — frozen full-pipeline outputs for 3 blessed notices.

## GOLD SET (component 1)
- **Stratified 200-clause sample** across **8 domains × 5 VCI bands (§8) × corpus source** (fresh-2026 `open_web`, upload/rehearsal intake, legacy Princeton). Sampling is deterministic (seeded) and **excludes `is_noise = true` clauses** (Prompt-2 noise filter landed — migration 0034). Strata counts are recorded; under-populated cells are reported honestly, never back-filled to hit 200.
- **Labeling UI** at `/eval/label` reuses F06 workbench idioms (clause card, domain chips, keyboard nav). Shows the clause text + its machine `category_v2` + `nlp_confidence_v2`; the labeler enters `gold_domain`, `verdict`, optional `note`. **No pre-filled gold_domain/verdict.** CSV **export** (blank gold columns) and **import** (human-filled) both write `gold_label` with labeler + timestamp.

## CLASSIFIER EVAL (component 2) — GATED on labels
Runs only over clauses that have a `gold_label`; if none, every metric emits "awaiting SME labels".
- **Accuracy** = agreement of `category_v2` with `gold_domain`.
- **Per-domain confusion matrix** (9×9 incl. `other`).
- **Per-source split** (fresh-2026 / upload / legacy) — accuracy may differ by provenance.
- **VCI calibration** — error rate per VCI band (§8). **The claim under test:** low-VCI clauses concentrate the errors (i.e. error rate rises as VCI falls). Reported as an observation, never auto-acted.
- **Stability (not accuracy):** re-run classification 3× on a fixed 50-clause subset; report agreement across runs. Labeled explicitly as *stability/determinism*, distinct from accuracy vs gold.

## SCORE VALIDITY (component 3) — perturbation + cited monotonicity
Per-domain **perturbation**: synthetically weaken a domain's clauses in a copy of a notice (never mutate stored data) → assert that domain's exposure worsens and its maturity falls, while other domains move less than a tolerance. Each assertion is stated **verbatim from intelligence-logic.md with a section citation** — if it cannot be cited, it is not asserted:
- **M-1 (§7, F-005):** "Disclosure Maturity = (Observed / Expected elements) × 100 − clarity/ambiguity penalties" → removing observed elements in a domain **decreases** F-005 (maturity falls). **Asserted.**
- **M-3 (§7, F-010):** "Overall Privacy Intelligence Score = 100 − weighted risk aggregate" → increasing the risk aggregate **decreases** F-010. **Asserted.**
- **M-4 (§7, F-006):** "Transparency = Completeness × Clarity × Specificity × Explainability factor" → lowering completeness **decreases** F-006. **Asserted.**
- **M-5 (§8, VCI):** "<40 Very Low (suppress or route to review — never present as definitive)" → an object with VCI < 40 lands in the Very-Low band (suppress/route), and VCI is monotone in its confidence inputs. **Asserted.**
- **F-002 (§7) — REPORTED, NOT ASSERTED.** `compute_f002` defines "DS (disclosure severity) = proportion of clauses in each domain", and domain proportions are coupled (Σ = 1). The verbatim §7 formula does **not** license a clean "weaken → exposure worsens" direction, so per "if you can't cite it, don't assert it" F-002 is measured and **reported** in INTELLIGENCE-QUALITY.md — flagged **[EXPERT]** (should regulatory severity track disclosure *volume* or *quality*?), never asserted or fixed here.
Failures of the asserted M-1/M-3/M-4/M-5 are **reported, not fixed** (a failing monotonicity is an eng/expert finding for review).

## GOLDEN NOTICES (component 4)
- **3 public retail-cohort notices** spanning **strong / mid / weak** disclosure. Selection rationale is stated in the spec/PR; **the SME blesses or swaps** the picks before they are authoritative.
- Full-pipeline outputs (decompose → classify → profile → score → findings → VCI) are **frozen as golden files**; a CI diff test fails if any output drifts. **Only a change to a cited `formula_version` may legitimately alter a golden file** (the diff message names which formula_version must have changed).

## BENCHMARK SANITY (component 5)
- Per cohort, assert the percentile distribution is **well-formed** (monotone non-decreasing, spans ~[0,100], no degenerate all-100 unless n and construction justify it).
- Inject a **synthetic strong org**; assert it lands in the **upper half** of its cohort. The synthetic org is **removed after the test** (no residue in benchmark tables).

## PRECISION METRIC (component 6)
- From `training_label.action` and `assessment_review.finding_reviews`, compute **confirm / edit / dismiss rate per `finding_type`** (join `finding_id` → `risk_finding.finding_type_code`).
- Surface as a read-only panel in the **Admin Console (F09)**; honest empty state ("no SME review actions yet") when there is no review data.

## INTELLIGENCE-QUALITY.md (component 7)
- A living report with **real numbers where data exists, else "awaiting SME labels."** Sections mirror components 2–6.
- Every recommendation carries an **owner tag** — **[SME]** (label more, bless/swap notices, adjudicate ambiguous domains, decide any threshold change) vs **[ENG]** (fix a harness bug, wire a metric, investigate a reproducible monotonicity failure). **The harness changes no weight/threshold/formula based on results.**

## API contracts
- `GET /eval/gold-set` — the current stratified sample (clause text + machine label; **no gold fields pre-filled**). Auth: sme/admin.
- `POST /eval/gold-label` — write one human label to `gold_label` (labeler from auth). Rejects any attempt to write a label without a human labeler.
- `GET /eval/gold-set/export.csv` / `POST /eval/gold-set/import.csv` — round-trip labeling.
- `GET /eval/finding-precision` — confirm/edit/dismiss rate per finding_type (consumed by the F09 Admin Console panel). Auth: admin.
- All read endpoints that surface a score echo its `vci` + `formula_version` (template rule); the eval endpoints surface labels/metrics, not new scores, so they add no `derived_data_item`.

## Behavior & states
- **Empty / awaiting labels:** every gated metric shows "awaiting SME labels — N of 200 labeled" rather than a fabricated number.
- **Loading / re-run:** stability re-runs show per-run progress.
- **Low-confidence:** VCI-calibration buckets are the object of study, not a gate here.
- **Mobile / reduced-motion:** labeling view degrades to a single-column card list.

## Guardrails & confidence
- **Measurement only — zero tuning.** No endpoint or script in F17 writes a weight/threshold/formula/taxonomy value.
- Banned-term filter applies to any generated prose in `INTELLIGENCE-QUALITY.md` and the Admin panel (exposure/maturity/likelihood language only).
- The harness **pre-fills no gold labels**; a label without a human `labeler` is rejected.
- Perturbation runs on **copies**; stored `disclosure_clause` / scores are never mutated. The synthetic benchmark org is removed after its test.

## Mocks (if any)
none — every number is a live query, a frozen golden file, or an honest "awaiting SME labels."

## Acceptance criteria
- **AC-1** `gold_label` exists (migration, ledgered); the gold-set sampler produces a deterministic, `is_noise`-excluded, stratified 200-clause set with honest per-cell counts; it writes **zero** gold_domain/verdict values itself.
- **AC-2** Classifier eval computes accuracy + 9×9 confusion + per-source split **only** over `gold_label`ed clauses; with zero labels it emits "awaiting SME labels" everywhere (no fabricated accuracy).
- **AC-3** VCI calibration reports error rate per §8 band as an observation; stability (3× on 50) is reported separately and labeled as stability, not accuracy.
- **AC-4** Each score-validity assertion is traceable verbatim to a cited intelligence-logic.md section (M-1…M-5); perturbation moves the target domain in the cited direction and others within tolerance, or the harness **reports** the deviation (fixes nothing).
- **AC-5** Golden-notice CI diff fails on any pipeline-output drift and names the `formula_version` that would have to change; selection rationale recorded; SME bless/swap tracked in SME-REVIEW-CHECKLIST.
- **AC-6** Benchmark sanity confirms well-formed percentile distributions and the synthetic strong org lands upper-half; the synthetic org leaves no residue.
- **AC-7** Finding-precision panel shows confirm/edit/dismiss per finding_type from real review data, honest empty state otherwise.
- **AC-8** `INTELLIGENCE-QUALITY.md` shows real numbers or "awaiting SME labels", and every recommendation carries an [SME]/[ENG] owner; no weight/threshold/formula changed by this feature.

## Test gate
- `tests/test_f17_gold_set.py` — deterministic stratification, noise exclusion, no pre-filled labels.
- `tests/test_f17_classifier_eval.py` — metrics math on a synthetic labeled fixture; "awaiting labels" path.
- `tests/test_f17_score_validity.py` — the M-1…M-5 perturbation/monotonicity assertions (cited).
- `tests/test_f17_golden_notices.py` — CI diff against frozen golden files.
- `tests/test_f17_benchmark_sanity.py` — distribution well-formedness + synthetic-org upper-half + cleanup.
- `tests/test_f17_precision.py` — confirm/edit/dismiss rate math + empty state.

## Open questions
- **OQ-1 [SME]** Which 3 public retail notices are the blessed golden set (strong/mid/weak)? Eng proposes; SME blesses or swaps. Tracked in SME-REVIEW-CHECKLIST.
- **OQ-2 [SME]** Gold-set labeling itself — 200 clauses need human labels before any accuracy/VCI-calibration number is real.
- **OQ-3 [SME/expert]** If VCI calibration shows low-VCI is **not** catching errors, any threshold change is an expert decision (out of scope here — reported only).

## Changelog
- 0.1 (2026-07-28): Initial spec — measurement-only evaluation harness (gold set + classifier eval + score-validity/monotonicity + golden notices + benchmark sanity + finding precision + INTELLIGENCE-QUALITY.md). Zero tuning; all monotonicity assertions cited verbatim to intelligence-logic.md §7/§8. Source: engineer (F17 task).
