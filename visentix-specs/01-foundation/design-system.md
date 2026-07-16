# Design System — Tokens, Furniture, DDR Summary

**Version:** 1.3 · 2026-07-16 · Condenses the Brand Guide, DDRs, and UI_SPEC §0 into one authority. Design principle: **legal-and-regulator "premium" is confident stillness plus evidence everywhere.** Motion exists only to reveal evidence.

## 1. Tokens (fixed — never invent colors)

| Token | Hex | Use |
|---|---|---|
| Deep Navy | `#09234F` | Primary bg (nav, drawers, chips) |
| Executive Blue | `#005FA3` | Interactive states, links |
| Teal | `#55C7B3` | Verified / approved / live / improving |
| Soft White | `#F7F8FA` | Page backgrounds |
| Warm Gray | `#D9DDE2` | Borders, dividers, removed-diff strikethrough |
| Subtle Gold | `#C8A46A` | Provisional / draft / premium / added-diff |
| Red | `#F87171` | High exposure + deficient/lagging maturity + worsening deltas + de-id block ONLY (poor standing under either polarity — see §2) |
| Emerald | `#10b981` | Live-dot only |

**Typography:** Fraunces (display/serif, Advisor lede, report covers) · Inter (UI chrome) · Source Sans 3 (data/numerics, `tabular-nums` required on all figures). Marketing/site may also use Aptos/Avenir per Brand Guide.

## 2. Semantic rules (single sources of truth in code)

- **Score coloring is polarity-aware — color always carries the same judgement.** Teal = good standing, gold = middling / needs attention, red = poor standing, for *every* score, regardless of which direction the number runs. Two canonical scales in `web/src/lib/scoreBands.ts`, never redefined locally:
  - **Exposure scores** (higher = worse: Regulatory Exposure, Compound Risk, Enforcement Correlation, Benchmark Deviation…): ≥70 red · ≥45 gold · below teal (`scoreBandColor`).
  - **Maturity scores** (higher = better: Overall Privacy Intelligence, Disclosure Maturity, Transparency, AI Transparency, Benchmark Percentile…): color follows the canonical VICBNF maturity bands — ≥75 teal (Mature/Leading) · ≥60 gold (Developing) · below red (Lagging/Deficient) (`maturityBandColor`). The color must always agree with the displayed band label: "Deficient" is never teal.
  - A metric whose polarity is unknown renders **neutral navy** — never a guessed judgement. The per-metric polarity registry lives beside the scales (`metricPolarity`); Data/SME verify new entries.
- **Direction affordance:** any surface that presents a score out of context states which direction is better (e.g. a quiet "higher is better" hint) and, for benchmarked scores, what the score is relative to (the peer cohort). VCI is never shown as a bare number — it carries its band label and a plain-language tooltip.
- **Delta coloring — by improvement, not direction** (DDR-009, `trendColor`): exposure falling = teal, rising = red; arrows show direction, color carries judgement. `trendColor` takes a per-metric **polarity flag**: maturity-type indices (higher = better, e.g. the quarterly Intelligence Indicators) invert the mapping — rising = teal, falling = red.
- **Diff palette:** gold = added, warm-gray strikethrough = removed, everywhere.
- **Low-confidence cohort:** one constant `LOW_CONFIDENCE_COHORT_N` (currently 10, OD-05).

## 3. Cross-screen furniture (required components)

| Component | Rule |
|---|---|
| **PageHeader** (DDR-008) | Every routed screen: eyebrow (= nav label) · title · one plain-English description · actions slot. Nav ↔ eyebrow ↔ title must agree |
| **Provenance Ribbon** (DDR-004) | Snapshot surfaces only (never Admin). Mono snapshot ID, formula version + frozen date, Reproducible mark (teal approved / gold draft + diagonal DRAFT watermark) |
| **Lineage Drawer** (DDR-005) | Dotted underline on any score; hover = affordance, click = drawer (right slide desktop, full-screen bottom sheet mobile). Contents: input micro-timeline (Clause → Regulator → Jurisdiction → Cohort), formula ID chip + plain-English description (no math notation), VCI, snapshot ID, frozen date |
| **Codex Tooltip** (DDR-006) | Every finding code is hover/focus target → canonical definition + exposure signal + related codes; PDF appends Codex appendix; code chips always navy |
| **View Switch** (DDR-002) | Analyst / Advisor labels; toggle top of card desktop, bottom-fixed bar mobile; both layers frozen in snapshot |
| **Live-Dot** | Emerald pulse, monitoring surfaces only; static under reduced motion |
| **"Intelligence, not legal advice" mark** (DDR-007) | Finding cards, report sections, lineage drawer, SME editor. NOT on Login/Monitor chrome/Admin/Codex/Methodology |

## 4. Key DDR decisions (defendable choices)

- **DDR-001:** draft state = gold watermark + gold ribbon (not yellow banner — yellow reads as error to legal readers).
- **DDR-002:** dual-voice Analyst (Source Sans metric grid, cold, deterministic) / Advisor (Fraunces italic lede, gold left-rule, warm prose, attribution). The visual inversion *is* the message.
- **DDR-003:** house persona "The Visentix Privacy Desk" in attribution; styled-but-empty reviewer slot awaiting SME governance.
- **Register rule:** customer-facing screens use plain language (no jargon like "SSRF"); SME Workbench may use expert jargon ("PII detected").

## 5. Quality floor (every screen)

Responsive 375/768/1280 · visible keyboard focus · `prefers-reduced-motion` respected (evidence still reachable) · tabular numerics · honest counts (live cohort n, exact code counts) · error states in plain language, never stack traces.

## 6. Route map

| Route | Nav label | Title |
|---|---|---|
| `/assessments` | Monitor | Privacy Intelligence Monitor |
| `/intake` | Intake | Submit a Privacy Notice |
| `/rewrite` | Rewrite | Trust Language Studio |
| `/vendors` | Vendors | Vendor Due Diligence |
| `/review` | Workbench | SME Workbench |
| `/quarterly` | Quarterly | Quarterly Intelligence Report * |
| `/crosswalk` | Crosswalk | Framework Crosswalk |
| `/codex` | Codex | Finding Codex |
| `/methodology` | Methodology | How Visentix Works |
| `/trust` | Trust Center | Trust Center * |
| `/admin` | Admin | Admin Console |
| `/partner` | Partner | Partner Portal |
| `/bulk` | Bulk | Bulk Analysis |
| `/reports/:assessmentId` | — | Report reader |

Nav is a grouped sidebar: **Workspace** (Monitor, Intake, Rewrite, Vendors, Workbench) · **Intelligence** (Quarterly, Crosswalk, Codex, Methodology, Trust Center) · **Administration** (Admin, Partner, Bulk). Below 900px it collapses to a hamburger drawer.

\* **Recorded DDR-008 exception:** the two public *editorial* pages (`/quarterly`, `/trust`) open with a full-bleed editorial cover/hero instead of the shared PageHeader — like the report reader, they are documents, not workflow screens. Every other routed screen keeps PageHeader with eyebrow = nav label.

## Changelog
- 1.3 (2026-07-16): **Score coloring made polarity-aware** (user feedback: a Deficient 34.9 rendered teal while 82.2 exposure rendered red — color contradicted meaning). §2 now defines the maturity color scale from the canonical VICBNF maturity-band thresholds (≥75 teal · ≥60 gold · <60 red — color always agrees with the band label), keeps the exposure scale unchanged, adds the neutral-navy rule for unknown polarity, and requires direction/relative-to affordances + labeled VCI. §1 red-usage rule extended to deficient/lagging maturity (same judgement, other polarity). NEEDS EXPERT/DATA: verify the per-metric polarity registry (esp. Benchmark Deviation, Enforcement Correlation classed as exposure).
- 1.2 (2026-07-16): Route map updated with the seven routes added by F11–F16 (audit finding: doc drift); recorded the grouped-sidebar nav structure and the DDR-008 editorial exception for `/quarterly` and `/trust`.
- 1.1 (2026-07-15): trendColor extended with per-metric polarity flag (maturity vs exposure) per Appendix I prototype review.
- 1.0 (2026-07-15): initial consolidation.
