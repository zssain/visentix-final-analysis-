# F12 — Quarterly Intelligence Report & Bulk Analysis

**Status:** shipped UI — Quarterly reader page real, all data mocked (M-15–M-18); aggregation/publication backend proposed; bulk analysis unbuilt · **Release:** R4 · **Depends on:** F02 (corpus scale), F03, F04, F11 (anonymization)

## Purpose
Product 4: the redacted, industry-wide Quarterly Global Privacy Intelligence Report — top-of-funnel marketing engine and analyst/regulator credibility asset — plus the V2 bulk-analysis workflows (regulator sector scans, law-firm screens, audit prospecting) that reuse the same aggregation machinery.

## Quarterly engine
1. **Quarter close:** freeze publication snapshot (dataset, formula versions, benchmark versions, cut-off date); run anonymization + minimum-sample checks.
2. **Metrics:** industry benchmark rankings, top disclosure gaps (finding-frequency ranks), compound risk patterns, AI governance trend adoption, regulator/enforcement theme shifts (F-012 across corpus), and the **Visentix Privacy Intelligence Indicators** — five named market-average indices published with QoQ deltas: Disclosure Maturity Index, AI Transparency Index, Consumer Rights Clarity Score, Enforcement Sensitivity Index, Compound Risk Index.
3. **Methodology section auto-generated** from dataset metadata: corpus size, benchmark populations, VCI bands, formula versions, cut-off date.
4. **Reader page:** editorial layout — full-bleed Fraunces cover, sector charts (Recharts), regulator heatmap, honest cohort sizes always visible, quiet "Assessed by Visentix" mark, CTA into the platform. Landing/download/registration flow, report archive, subscriber management.

## Publication section manifest (from Appendix I prototype)
| # | Section | Data source | Notes |
|---|---|---|---|
| — | Cover | Publication snapshot | Corpus stats (orgs / industries / jurisdictions / clauses analyzed) are **real counts from the frozen snapshot** — Hard Rule 7: never the prototype's "1,250+ / 9.8M+" placeholder scale |
| 1 | Executive Summary + Intelligence Indicators panel | Indicators (above) with QoQ deltas | Each index carries VCI + methodology link |
| 2 | Key Quarterly Findings | F-012 deltas across corpus | Six-tile trend layout |
| 3 | Industry Benchmark Rankings | Disclosure Maturity Index by industry | Cohort n per industry shown |
| 4 | Regulator & Enforcement Intelligence | Enforcement corpus, activity change by regulator, top themes | Descriptive counts of observed activity only |
| 5 | AI Governance Intelligence | AIGMS/F-007 trend line, top AI disclosure gaps | |
| 6 | Disclosure Trend Intelligence | Prevalence change by domain QoQ | |
| 7 | High-Risk Disclosure Patterns | F-008 compound patterns with prevalence % | Exposure framing, never allegations |
| 8 | Benchmark Spotlight | Anonymized top-quartile language patterns | Must pass the SME de-id + approval pipeline (F06) and minimum-sample suppression before publication |
| 9 | Strategic Outlook | Observed trend directions | **Guardrail: descriptive-only** — states observed momentum ("enforcement activity around dark patterns continued rising"), never predictions, forecasts, or predicted scores (prediction is R5 scope) |
| 10 | Methodology & Intelligence Engine | Auto-generated from snapshot metadata | |
| 11 | About Visentix + subscribe/CTA back cover | Static, guardrail-filtered | |

**Metric polarity rule for QoQ deltas:** the Indicators are *maturity* indices (higher = better) — the mirror of exposure scores. Delta coloring keys to `trendColor` with an explicit per-metric polarity flag (DDR-009 extended): maturity rising = teal, falling = red; exposure the reverse. Arrows show direction; color carries judgement.

## Bulk analysis (shares aggregation layer)
Company-list upload → batch pipeline → risk-ranked queue with issue filters, evidence snippets, confidence, export (CSV / evidence package). Persona modes: regulator sector scan (heat map, outliers, common gaps), plaintiff-firm screen, audit prospecting. Access-controlled — bulk screening is a sensitive capability; contract-gated.

## Guardrails & confidence
Public metrics: reproducible from frozen snapshots (DIR-010), anonymized, sample-suppressed; descriptive language only. Bulk outputs are exposure intelligence with evidence references — never allegations or verdicts.

## Behavior & states
**What is real today:** the Quarterly reader page (`/quarterly`, public route) is fully built as UI — full-bleed cover, the 5-index Intelligence Indicators panel, the 11 editorial sections from the manifest, sector rankings, the regulator activity heatmap, the AI-governance trend line, and the About/CTA back cover. It renders entirely from mocked aggregates (M-15–M-18); **no aggregation backend, publication-snapshot freeze, or bulk-analysis workflow is wired yet.**

States implemented on the reader page: honest cohort `n` shown on every ranking row with a low-confidence flag below `LOW_CONFIDENCE_COHORT_N`; Benchmark Spotlight filters below-threshold cohorts and renders a visible suppression notice (AC-6); per-metric polarity delta coloring (AC-8); reproducible provenance ribbon on the cover; responsive at 375/768/1280; reduced-motion honored. The regulator heatmap uses a neutral navy-intensity scale (observed-activity volume), deliberately not the red exposure scale, so shading never reads as a verdict.

Not yet built: publication-snapshot freeze + reproducibility (AC-1), methodology auto-generation from real snapshot metadata (AC-4), the bulk-analysis upload → ranked-queue workflow and its persona modes (AC-3), and the landing/download/registration/subscriber flow. These remain proposed pending the aggregation backend.

## Mocks
The reader page is UI-built ahead of the backend; every displayed figure is mocked and registered in [`00-plan/mock-tracker.md`](../00-plan/mock-tracker.md): **M-15** (publication snapshot + cover corpus counts), **M-16** (five Intelligence Indicators + QoQ deltas), **M-17** (section aggregates: rankings, regulator activity, AI governance, disclosure trends, compound patterns), **M-18** (Benchmark Spotlight excerpts).

| ID | What's mocked | Real source | Removal plan |
|---|---|---|---|
| M-15 | Publication snapshot id + cover corpus counts (orgs / industries / jurisdictions / clauses) | Frozen publication snapshot metadata (DIR-010) | Build quarter-close freeze; read real counts (AC-5, Hard Rule 7) |
| M-16 | Five named Intelligence Indicators + QoQ deltas | Market-average aggregates per `formula_version`, each with VCI | Build indicator aggregation over the corpus |
| M-17 | Section aggregates (industry rankings, regulator activity, AI-governance trend, disclosure trends, compound patterns) | Corpus aggregation from `derived_data_item` / F-012 deltas | Build the aggregation layer shared with bulk analysis |
| M-18 | Benchmark Spotlight excerpts | SME-approved + de-identified exemplars above the minimum-sample threshold (F06 pipeline) | Wire to approved exemplar store; enforce suppression (AC-6) |

## Acceptance criteria
- AC-1 Every published statistic reproducible from the frozen publication snapshot.
- AC-2 No public metric derived from a cohort under the suppression threshold.
- AC-3 Bulk scan of N companies produces a ranked queue where every flag links to clause-level evidence + VCI.
- AC-4 Methodology section values match the snapshot metadata automatically.
- AC-5 Cover corpus stats equal the frozen snapshot's real counts (a mismatch or placeholder fails the publication build).
- AC-6 Benchmark Spotlight excerpts exist only if SME-approved + de-identified and above the suppression threshold.
- AC-7 Strategic Outlook copy passes the banned-term filter AND contains no predictive claims (no "will", "forecast", "predicted" framing about regulator or company behavior).
- AC-8 Indicator QoQ deltas color by per-metric polarity (maturity vs exposure), verified by unit tests on `trendColor`.

## Test gate
Publication freeze tests, aggregation reproducibility tests, suppression tests, batch pipeline scale test, cover-stat snapshot-equality test, outlook guardrail scan, polarity unit tests.

## Changelog
- 2026-07-16: Reader page built UI-only against mocks (engineer). Status → "shipped UI, all data mocked"; added Behavior & states and Mocks sections; registered M-15–M-18. `trendColor` in code now implements the per-metric polarity flag design-system.md v1.1 §2 already specified (AC-8), backward-compatible with default "exposure". Aggregation/publication backend and the bulk-analysis half remain proposed. Files: `web/src/pages/quarterly/{QuarterlyReport.tsx,mockData.ts,quarterly.css}`, `web/src/lib/scoreBands.ts`, `/quarterly` route + nav.
- 2026-07-15: Added publication section manifest from Appendix I prototype review — Intelligence Indicators panel (5 named indices), Benchmark Spotlight, Strategic Outlook (descriptive-only guardrail), real-count cover rule, metric-polarity delta coloring; AC-5–AC-8 added.
