# Visentix MVP — Post-Gap-Closure Audit
**Date:** 2026-06-29 (post G1–G10)
**Prior audit:** AUDIT_vs_PDF_spec.txt (2026-06-29, pre-gap-closure)

Legend: [BUILT] = fully implemented + tested | [REPORTED] = blocked, documented

## Stage 1 — The Front Door

| Component | Prior | Now | Evidence |
|---|---|---|---|
| Upload (URL/PDF/text) | [BUILT] | [BUILT] | 31 intake tests |
| Decompose (sections→clauses) | [BUILT] | [BUILT] | Unchanged |
| Classify (8 domains) | [PARTIAL] | [BUILT] | G4: LLM classify wired into POST /assessments with keyword fallback. 9 tests. |
| Corpus reclassify | [MISSING] | [BUILT] | G4 Part B: 2,391 "other" clauses → 1,663 reclassified to meaningful domains via category_v2 (additive, original untouched). |

## Stage 2 — The Brain

| Component | Prior | Now | Evidence |
|---|---|---|---|
| Company Profile (7 scores) | [BUILT] | [BUILT] | 30 profiles, 29 tests |
| Normalization | [BUILT] | [BUILT] | 30 rows weighted, 20 tests |
| F-001 Source Reliability | [MISSING] | [BUILT] | G5: 303 verification rows in derived_data_item. Zero drift. 12 tests. |
| F-002 Regulatory Exposure | [BUILT] | [BUILT] | With lineage |
| F-003 Benchmark Deviation | [BUILT] | [BUILT] | Weighted peers |
| F-004 Enforcement Correlation | [MISSING] | [BUILT] | G1: 26 notice rows, similarity.py helper, ES×RPW×EFW×100. 14 tests. |
| F-005 Disclosure Maturity | [BUILT] | [BUILT] | element_checklist.csv |
| F-006 Transparency | [BUILT] | [BUILT] | 4-factor product |
| F-007 AI Transparency | [BUILT] | [BUILT] | AI elements |
| F-008–F-014 | [BUILT] | [BUILT] | Including F-012/F-013 enhanced (G6) |
| VCI | [BUILT] | [BUILT] | Labels + suppression |
| Findings (catalog) | [BUILT] | [BUILT] | 140 rows, 13 tests |
| Regulator Heatmap | [PARTIAL] | [BUILT] | G3: 9×8 grid, RPW×density×EFW, F-004 boost. 12 tests. |
| clause_obligation | [PARTIAL] | [BUILT] | G2: Module built + 12 tests. Obligation embeddings backfilled (154/154). |
| F-012 Trend Delta | [PARTIAL] | [BUILT] | G6: Real delta when prior exists; honest "no_prior_history" + VCI=0.1 when not. 12 tests. |
| F-013 Alert Escalation | [PARTIAL] | [BUILT] | G6: Real signal with monitoring; low-confidence label without. 6 tests. |

## Stage 3 — The Trust Layer

| Component | Prior | Now | Evidence |
|---|---|---|---|
| Lineage | [BUILT] | [BUILT] | 883 derived rows, 0 missing lineage |
| Reproducibility | [BUILT] | [BUILT] | 3 reports byte-identical incl §5 heatmap + §8 exemplar |
| Guardrail | [BUILT] | [BUILT] | 31 tests |
| Narrative | [BUILT] | [BUILT] | Number verifier + fallback, 16 tests |
| SME Gate | [BUILT] | [BUILT] | 21 tests |
| Training Capture | [BUILT] | [BUILT] | 12 tests |
| Exemplar Review | [MISSING] | [BUILT] | G7: Clean/approve routes, de-id validator, 3 demo cleaned. 15 tests. |

## Stage 4 — The Report

| Component | Prior | Now | Evidence |
|---|---|---|---|
| 12-section assembly | [BUILT] | [BUILT] | §5 now has real heatmap, §8 has cleaned exemplars |
| PDF render (weasyprint) | [BUILT] | [BUILT] | G10: RENDERER config flag, smoke test |
| PDF render (Playwright) | [PARTIAL] | [REPORTED] | G10: pypi.org blocked by network egress. Code path exists. Documented. |
| Report route in portal | [MISSING] | [BUILT] | G9: /reports/:assessmentId renders all 12 sections. 9 tests. |

## Stage 5 — The Platform

| Component | Prior | Now | Evidence |
|---|---|---|---|
| Three roles | [BUILT] | [BUILT] | 3 users (admin/sme/customer) |
| RLS | [BUILT] | [BUILT] | 5 tables with policies |
| Admin console | [BUILT] | [BUILT] | Health + training stats + DB overview |
| Login redirect | [BUG] | [BUILT] | G8: AuthProvider context, declarative redirect, no imperative navigate(). 10 tests. |
| CORS | [PARTIAL] | [BUILT] | G10: Defaults to both localhost + 127.0.0.1. Never wildcard. 4 tests. |

## Audit Verification

| Check | Result |
|---|---|
| Backend tests | **408 passed**, 0 failed, 0 skipped |
| Frontend tests | **45 passed**, 0 failed, 0 skipped |
| **Total tests** | **453** |
| derived_data_item missing formula_version | **0** |
| derived_data_item missing source_lineage | **0** |
| derived_data_item missing confidence_score | **0** |
| Fabricated cohort strings | **0** |
| LLM calls in scoring/profiling/normalization | **0** |
| Reproducibility (3 reports) | **Identical** (incl §5 heatmap + §8 exemplar) |
| sme_cleaned exemplars | **3** (data_sharing, retention, ai_automated_decisions) |
| Obligation embeddings NULL | **0** (154/154 backfilled) |
| Corpus reclassified (other→domain) | **1,663** of 2,391 |
