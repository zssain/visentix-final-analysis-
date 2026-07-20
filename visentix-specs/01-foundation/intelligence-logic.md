# Intelligence Logic — Classification, Benchmarking, Scoring

**Version:** 1.3 · 2026-07-20 · Consolidates VICBNF v2.0, the Derived Intelligence Catalog v1, and the Intelligence Engine Framework. All weights are **initial policy settings**, configurable in `formula_version` / lookup tables, subject to calibration governance — never hardcoded.

## 1. Pipeline (Porter value chain)

`Ingest → Normalize → Classify → Benchmark → Score → Explain → Deliver`, plus a feedback loop (SME labels → calibration). Explainability lineage persists across every stage.

## 2. Organization Intelligence Profile (7 dimensions)

| Dim | Range | Formula (weights) |
|---|---|---|
| **IC** Industry | taxonomy | Controlled 10-industry taxonomy + sub-industries |
| **RSS** Regulatory Scrutiny | 0–100 | State exposure 25% + Data volume 20% + Sensitive data 20% + Advertising/profiling 15% + Industry sensitivity 10% + Regulatory history 10%. Tiers: 0–20 Minimal / 21–50 Moderate / 51–80 High / 81–100 Enhanced |
| **PGMS** Governance Maturity | 0–100 | Governance infra 30% + Operational controls 30% + Transparency 20% + Consumer rights 20%. Tiers: Nascent ≤25 / Developing ≤50 / Managed ≤75 / Mature ≤90 / Leading ≤100 |
| **OSI** Sophistication | 0–100 | Employees 20% + Revenue 15% + Public co 10% + Legal dept 15% + Privacy office 15% + Privacy counsel 10% + Security 5% + AI governance 5% + Governance artifacts 5% |
| **DSI** Data Sensitivity | 0–100 | min(100, Σ(category weight × presence confidence × context multiplier)). Weights: basic 1, device 2, commercial 3, geo 6, AI-inference 7, financial 8, health 9, biometric 10, children 10 |
| **EHP** Enforcement History | tier + 0–100 | None 0 / Limited 1–25 / Moderate 26–50 / Significant 51–75 / High 76–100 |
| **AIGMS** AI Governance | 0–100 | AI use 20% + Profiling transparency 20% + Automated decision 20% + Training data 15% + Consumer controls 15% + Artifacts 10% |

## 3. Notice classification scores

Completeness (expected clauses present / expected), Transparency (transparent/relevant clauses), Ambiguity (ambiguous terms/total), Readability (Flesch-Kincaid + adjustments), Rights, Retention, Sharing, AI disclosure scores. **Score bands:** 90–100 Leading / 75–89 Mature / 60–74 Developing / 40–59 Lagging / 0–39 Deficient.

## 4. Clause taxonomy (semantic DNA)

8 domains + other: **CR** Consumer Rights (access, delete, correct, portability, appeal, opt-out, agent) · **DC** Data Collection (PI categories, sensitive, biometric, precise location, children) · **SH** Sharing (service providers, ad networks, analytics, affiliates, data brokers) · **RT** Retention (specific period, criteria-based, undefined) · **AI** (automated decisions, profiling, human review, training data, transparency) · **SEC** (safeguards, incident/breach) · **TRK** (cookies, preference center) · **XB** (cross-border transfers). Finding codes (TRK-007, SH-002, RT-003 …) are governed in the Codex (`finding_type`).

**v2 reclassification (partially run; completion pending).** A second-pass classifier (`scripts/reclassify_other.py`, `classifier_version = qwen3-8b-local-v1`) re-labels legacy `category='other'` clauses into the 8 domains, writing **only** to `disclosure_clause.category_v2 / nlp_confidence_v2 / classifier_version` (never overwriting the base `category` — see schema.md §2). Downstream reads should prefer `category_v2` when present, falling back to `category`. ⚠️ **Status correction (v1.3, 2026-07-20).** An earlier version of this line claimed the reclassifier had cut the "other" bucket "from ~65% toward ~20%." The live census (`logs/audits/2026-07-data-layer-audit.md`, 2026-07-20) shows that is **not yet true**: of 6,145 clauses, only **2,391 (38.9%) have any `category_v2` value** and **3,754 rows are still `category_v2 IS NULL`**; base `category='other'` remains 3,864 (62.9%). The reclassification has **not been run to completion** — the ~20% target is an aspiration, not the current state. Do not cite the "~20%" figure until a follow-up census confirms it.

## 5. Benchmark population construction

Population key = **Industry + RSS tier + PGMS tier + OSI tier + DSI tier + AIGMS tier + EHP tier**. Dimensions may be relaxed when cohorts are small, but relaxation is recorded in explainability metadata.

| Cohort size | Action |
|---|---|
| ≥100 | Full dimensional cohort |
| 50–99 | Minor weighting relaxation (identify relaxed dimension) |
| 20–49 | Adjacent-tier expansion, flag moderate confidence |
| <20 | Broaden to industry cohort + confidence reduction, flag low confidence |

Five corpus populations: Market Reality, Regulatory Resilience, Enforcement, Gold Standard, AI Governance. Corpus gate: **CQS ≥ 75** (Extraction 25% + Completeness 25% + Freshness 20% + Source reliability 20% + Version stability 10%).

## 6. Normalization engine

Normalization Score = Industry sim 20% + Regulatory sim 20% + Governance sim 15% + Sophistication sim 15% + Data-sensitivity sim 15% + AI-maturity sim 10% + Freshness sim 5% (tier match = 1.0, adjacent = 0.75, non-adjacent = 0.4–0.5; freshness ≤12mo = 1.0, 13–24 = 0.75, >24 = 0.4).
Benchmark Weight = product of relevance factors × freshness. **Never compute percentiles from raw unweighted peer sets.**

## 7. Formula registry (F-001 – F-014)

Shared variables: JW jurisdiction weight, RPW regulator priority weight, DS disclosure severity 0–100, BD benchmark deviation, ES enforcement similarity 0–1, EFW enforcement frequency weight, NC NLP confidence, SR source reliability, IV interpretive variance, CM correlation multiplier 1.00–2.50.

| ID | Formula | Calculation |
|---|---|---|
| F-001 | Source Reliability | (Authority + Freshness + Completeness + Extraction Confidence) / 4 |
| F-002 | Regulatory Exposure | Σ(JW × RPW × DS) normalized 0–100 |
| F-003 | Benchmark Deviation | max(0, TopQuartile − OrgScore) or percentile distance from peer median/top quartile |
| F-004 | Enforcement Correlation | ES × RPW × EFW × 100 |
| F-005 | Disclosure Maturity | (Observed / Expected elements) × 100 − clarity/ambiguity penalties |
| F-006 | Transparency | Completeness × Clarity × Specificity × Explainability factor |
| F-007 | AI Transparency Maturity | (AI controls present / expected) × 100 − AI ambiguity penalty |
| F-008 | Compound Risk | Σ(Related risk scores × CM × RPW) normalized 0–100 |
| F-009 | Confidence-Weighted Score | Derived score × Confidence |
| F-010 | Overall Privacy Intelligence Score | 100 − weighted risk aggregate. Initial weights: Regulatory 25%, Benchmark 20%, Disclosure 20%, Enforcement 15%, AI 10%, Compound 10% |
| F-011 | Benchmark Percentile | PercentileRank(OrgScore in weighted comparable peer population) |
| F-012 | Trend Delta | (Current − Prior) / Prior |
| F-013 | Alert Escalation | Risk increase × Enforcement correlation × Monitoring priority × Confidence |
| F-014 | Report Confidence Index | (Validated / Total findings) × avg SR × avg NC |

## 8. Visentix Confidence Index (VCI)

VCI = NLP 30% + Benchmark 25% + Regulatory 15% + Enforcement 15% + Source reliability 15%.
Bands: 90–100 Very High (no caveat) / 75–89 High / 60–74 Moderate (label) / 40–59 Low (caution, may need review) / <40 Very Low (**suppress or route to review — never present as definitive**). Every intelligence object carries VCI; UI/API expose it.

## 9. Multi-layer risk & severity

Layers: Regulatory Risk (JW × enforcement priority × deficiency severity) · Benchmark Risk (peer deviation × industry sensitivity × gap severity) · Disclosure Quality (vagueness/ambiguity/contradiction/readability; NLP markers: "may share", "trusted partners", undefined retention) · Enforcement Correlation · Compound Risk. Severity: Low / Moderate / High / Severe (enforcement-aligned or materially deficient). Interpretive classifications: High Consensus / Moderate Consensus / Emerging / Ambiguous.

## 10. LLM task boundaries

LLM **may**: summarize clauses (raw text preserved), classify with confidence, suggest regulator mappings (must resolve to structured objects), generate executive language (must cite intelligence objects), rephrase narratives (verified + deterministic fallback).
LLM **may not**: produce final scores (formula layer owns scoring), render legal conclusions, generate any display value not backed by a `derived_data_item`.
Every LLM output records model version, prompt version, confidence, review status.

## 11. Recalculation triggers

Customer upload → full pipeline + snapshot. Monitored hash change → diff, classify changed clauses, rescore affected domains, alert check. New enforcement → update taxonomy/vectors, rerun F-004 for affected domains. Law change → update obligations/weights, rescore jurisdictions. Benchmark refresh (monthly) → rebuild cohorts, preserve versions. Formula update → applies to new outputs only; historical snapshots untouched. Quarter close → frozen publication snapshot.

## 12. Derived Intelligence Rules (DIR)

Governance rules for how *derived intelligence* — every `derived_data_item` object and everything rendered from it — is produced, stored, published, and displayed. These are cited across `schema.md`, F04, F05, F11, F12, and the roadmap; this section is their canonical home (the v1.0 consolidation named the DIRs but dropped their text).

> ⚠️ **Reconstructed pending expert verification.** The original DIR definitions are not present anywhere in the repo. The rules below were reconstructed from how each DIR is *used* across the specs and from `AGENTS.md` Hard Rules 4 & 6, which restate the same lineage guarantees. Confirm each against the source **Derived Intelligence Catalog** before treating as final. DIR-007 and DIR-009 have no live reference and are left reserved — do not assign them meaning until the source is checked.

| ID | Rule | Reconstructed from |
|---|---|---|
| **DIR-001** | Every derived value is materialized as a `derived_data_item` record (score + object_type + generated_at). One shared derived-intelligence object type feeds all four products — no product computes its own derived data. | schema `derived_data_item` "DIR-001…004"; roadmap "shared derived intelligence objects"; Hard Rule 4 |
| **DIR-002** | Each derived value carries ≥1 explainability reference — input refs tracing back to source clause / regulator / benchmark population. No score without a traceable input path. | F04 AC-2 "explainability reference (DIR-002/004)"; Hard Rule 4 |
| **DIR-003** | Each derived value stores the `formula_version_id` that produced it. A formula change writes new rows; it never edits existing ones. | schema `derived_data_item`; Hard Rule 6 |
| **DIR-004** | Each derived value stores a VCI confidence score (+ `vci_components`). VCI travels with the value everywhere it is consumed. | F04 AC-2 "VCI … (DIR-…004)"; §8 VCI |
| **DIR-005** | Anonymized / aggregate outputs (white-label, quarterly) live in tables physically segregated from customer-scoped values. | schema §12 note; F11 "segregated … per DIR-005" |
| **DIR-006** | Minimum-sample suppression: no aggregate is published or exposed externally below the minimum cohort size. Small cohorts are suppressed or carry the low-confidence label — never shown as if robust. | roadmap; F11; F12 "sample-suppressed" |
| **DIR-007** | *Reserved. No live reference in the specs and no source text in the repo — do not assign meaning until confirmed from the Derived Intelligence Catalog.* | — |
| **DIR-008** | Presentation never recalculates. Every UI/PDF surface (and every product) consumes `derived_data_item` / the API; no screen recomputes a score or hardcodes a display number. | README; F05 "presentation never recalculates"; roadmap; Hard Rule 4 |
| **DIR-009** | *Reserved. No live reference; no source text in the repo — confirm before use.* | — |
| **DIR-010** | Reproducibility: every published number is reproducible from its stored snapshot + formula version + benchmark version; a frozen snapshot regenerates identically. | F12; roadmap "reproducible from stored snapshot"; Hard Rule 6 |

## 13. Changelog
- 1.3 (2026-07-20): **§4 status correction (truth reconciliation).** Removed the unsupported claim that the v2 reclassifier had reduced the "other" bucket to ~20%; the 2026-07-20 census shows only 38.9% of clauses have a `category_v2` value (3,754 still NULL). Restated as "partially run; completion pending" with the census numbers. No formula, weight, or taxonomy change. Source: engineer + `logs/audits/2026-07-data-layer-audit.md`.
- 1.2 (2026-07-16): added §12 Derived Intelligence Rules (DIR) registry — restores the DIR definitions the v1.0 consolidation named but dropped; reconstructed from usage + Hard Rules 4/6, flagged for expert verification against the source Catalog. Structural fix (spec-change): DIR refs were dangling across schema/F04/F05/F11/F12/roadmap.
- 1.1 (2026-07-15): §4 records the shipped v2 corpus reclassification (`category_v2`, `classifier_version=qwen3-8b-local-v1`), absorbed from the archived RECLASSIFY_PLAN.md / AUDIT.md and verified against `scripts/reclassify_other.py`.
- 1.0: consolidated from VICBNF v2.0 (all sections + Appendix A), Derived Intelligence Catalog (formula library, variables, triggers, DIRs), Intelligence Engine Framework Appendices B–F.
