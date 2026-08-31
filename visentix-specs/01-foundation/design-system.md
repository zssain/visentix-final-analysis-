# Design System — Tokens, Furniture, DDR Summary

**Version:** 1.8 · 2026-08-31 · Condenses the Brand Guide, DDRs, and UI_SPEC §0 into one authority. Design principle: **legal-and-regulator "premium" is confident stillness plus evidence everywhere.**

**Motion — amended 2026-08-31 (owner).** The previous rule read *"Motion exists only to reveal evidence."* The owner has asked for figures and charts that animate to their value. This is a deliberate reversal, recorded as such rather than allowed to drift in. Motion is now permitted for **arrival** only, under four binding constraints (§7).

## 1. Tokens (fixed — never invent colors)

**Single source of truth: `web/src/theme.css`.** No component, page, chart or stylesheet may define a colour value. Tokens are oklch and are consumed through the shadcn/Tailwind token names (`--background`, `--card`, `--primary`, `--muted-foreground`, `--border`, …), which the owner supplied on 2026-08-31 and which are recorded there verbatim.

Two token groups exist that the shadcn set does not cover, because they carry meaning the framework has no name for:

### 1.1 Standing scale (OD-13) — the only colours that judge

Traffic light. **Green = good · Yellow = middling · Red = poor.** A surface may use these *only* to express a standing. Values are per-mode: a light standing colour is **never** reused in dark.

| Token | Light | Contrast on card | Dark | Contrast on card |
|---|---|---|---|---|
| `--standing-good` | `oklch(0.520 0.108 163.3)` | 5.21:1 | `oklch(0.750 0.108 163.3)` | 8.18:1 |
| `--standing-mid` | `oklch(0.545 0.125 77.5)` | 5.04:1 | `oklch(0.750 0.125 77.5)` | 7.69:1 |
| `--standing-bad` | `oklch(0.500 0.182 29.5)` | 6.58:1 | `oklch(0.750 0.182 29.5)` | 6.79:1 |

**Contrast is computed, never eyeballed.** `scripts/check_contrast.mjs` recalculates all six from `theme.css` on every run and fails below WCAG AA (4.5:1), so the ratios above cannot drift from the values. This guard exists because measuring found two live defects:

- **`--mid` was `#A87400` = 4.07:1 on white and had been shipping as a text colour** — below AA for normal text. A washed-out number is a legibility bug, not a matter of taste.
- The light standing values measured **2.64–3.34:1 on the dark card**. Dark mode requires lifted variants, not the same hex.

### 1.2 Non-standing status — what KIND a thing is

| Token | Job |
|---|---|
| `--provisional` | draft · mock · not-yet-verified · added-diff |
| `--verified` | approved · live · frozen |

Kept structurally separate from the standing scale so a palette change to one can never silently restate the other. **A draft notice is not a bad score.**

### 1.3 Chart ramp

`--chart-1` … `--chart-5` is a **sequential** ramp (one hue, lightness 0.845 → 0.432). It is for **magnitude only** — heatmap cells, meters, part-to-whole bars. It cannot carry identity: five shades of one green cannot tell entities apart. `--chart-1` and `--chart-2` measure 1.52:1 and 2.51:1 on white and are **fills only, never text or thin strokes**. If a genuinely categorical series is ever needed, it is a new decision, not a generated hue.

### 1.4 Legacy token bridge (temporary)

The old brand names (`--navy`, `--exec-blue`, `--teal`, `--gold`, `--soft-white`, `--good`/`--mid`/`--bad`, …) still exist in `index.css` but **hold no values** — each resolves to a shadcn token. This lets unmigrated pages adopt the palette and respond to the theme without being edited. Names are retired as their pages migrate; **nothing may be added to the bridge.**

**Typography:** Fraunces (display/serif, Advisor lede, report covers) · Inter (UI chrome) · Source Sans 3 (data/numerics, `tabular-nums` required on all figures). Marketing/site may also use Aptos/Avenir per Brand Guide.

### 1.5 Dark mode

Three states — light · dark · **system** — because a two-way switch cannot express "follow my OS" and would override a reader whose system is dark with no way back. Choice persists to `localStorage` (guarded; private mode throws) and sets `root.style.colorScheme` so native scrollbars and form controls follow. Every token has a dark value; **a surface that hard-codes a colour cannot respond to the theme**, which is why §1's no-colour-outside-the-token-layer rule is enforced rather than advisory.

**Open residue (OD-17): the PDF renderer still has its own ramp.** `app/services/report/renderer.py` `_RAMP` renders four bands at 25/50/75 with its own hexes — different values *and* different thresholds from the web scale's 45/70. Tailwind cannot reach WeasyPrint, and WeasyPrint does not parse `oklch()`. The PDF therefore keeps its own stylesheet (owner-confirmed 2026-08-31), but its values must be **generated from `theme.css`, not hand-copied**. Reconciling the palette is a design call; reconciling the **thresholds** is a Hard Rule 3 matter and is expert-owned. Do not unilaterally change either.

## 2. Semantic rules (single sources of truth in code)

- **Score coloring is polarity-aware — color always carries the same judgement.** Green = good standing, yellow = middling / needs attention, red = poor standing, for *every* score, regardless of which direction the number runs (traffic-light scale, §1; teal/gold remain in code until the OD-13 hexes land). Two canonical scales in `web/src/lib/scoreBands.ts`, never redefined locally:
  - **Exposure scores** (higher = worse: Regulatory Exposure, Compound Risk, Enforcement Correlation, Benchmark Deviation…): ≥70 red · ≥45 yellow · below green (`scoreBandColor`).
  - **Maturity scores** (higher = better: Overall Privacy Intelligence, Disclosure Maturity, Transparency, AI Transparency, Benchmark Percentile…): color follows the canonical VICBNF maturity bands — ≥75 green (Mature/Leading) · ≥60 yellow (Developing) · below red (Lagging/Deficient) (`maturityBandColor`). The color must always agree with the displayed band label: "Deficient" is never green.
  - A metric whose polarity is unknown renders **neutral navy** — never a guessed judgement. The per-metric polarity registry lives beside the scales (`metricPolarity`); Data/SME verify new entries.
- **Direction affordance:** any surface that presents a score out of context states which direction is better (e.g. a quiet "higher is better" hint) and, for benchmarked scores, what the score is relative to (the peer cohort). VCI is never shown as a bare number — it carries its band label and a plain-language tooltip.
- **The band leads; the number follows** (owner-decided 2026-08-31). A move from 60 to 70 carries no meaning a reader can act on; a move from *Developing* to *Mature* does. On every customer-facing surface the **band label is the headline** (typographically dominant) and the precise figure is **secondary** — available in the lineage drawer, on hover/focus, and in the PDF's traceability section, never removed. Lineage, reproducibility, and byte-identity are unaffected: the number is still stored, still frozen, still traceable (Hard Rules 4 & 6). SME/Analyst surfaces may keep the number as headline.
- **Peer position is stated in words** (owner-decided 2026-08-31). Wherever a score is benchmarked, the surface says where the organization sits in plain comparative language ("about average for similar organizations", "above average…") alongside the band. The governed comparative vocabulary and its cut-points live in `intelligence-logic.md` §3 — **never invented per-screen**, and no comparative word appears until that vocabulary is expert-confirmed (OD-14).
- **One name, one number** (owner-decided 2026-08-31). A named measure ("Overall", "Overall Privacy Intelligence Score") must show the **same value, same band, same label, and same color everywhere it appears** in a given snapshot — cover, dashboard, section body, PDF, monitoring hero. Two surfaces disagreeing about "Overall" is a defect, not a rounding preference. Rounding and precision for a named measure are decided once, in `scoreBands.ts`, and reused; no surface re-rounds or re-derives. See lesson L-009.
- **Delta coloring — by improvement, not direction** (DDR-009, `trendColor`): exposure falling = teal, rising = red; arrows show direction, color carries judgement. `trendColor` takes a per-metric **polarity flag**: maturity-type indices (higher = better, e.g. the quarterly Intelligence Indicators) invert the mapping — rising = teal, falling = red.
- **Earn your place** (DDR-011, owner-decided 2026-08-31). Every element that occupies permanent screen space must answer one question: *what does the reader do with this?* If the honest answer is "nothing", it does not get a card, a column, or a panel. Three failure modes this rule exists to stop, all observed on the live Monitor: a panel that **cannot** populate in the current configuration (three empty monitoring boxes advertise absence); a panel showing **internal machinery** a customer has no use for (SME review counts on a customer dashboard); and a panel showing an **identifier or version with no meaning attached** (a truncated snapshot UUID, `Population v269382882`). Screen space is the scarcest thing on the page — a real number that the reader cannot act on still costs the number next to it.
- **Machinery is available on command, not on display** (DDR-011). Snapshot IDs, formula versions, benchmark-population versions, cohort internals, and confidence mechanics are **evidence** — they must be reachable in one gesture (lineage drawer, a disclosure control, Traceability, copy-to-clipboard) and reproducible on demand, but they do not lead, and they do not sit permanently in a reader's field of view. This is not a retreat from "evidence everywhere": evidence stays one click away and nothing is deleted from the snapshot. What changes is the default state — closed, not open. A surface that leads with an opaque identifier has spent its most valuable position on the least usable fact on the page.
- **Diff palette:** gold = added, warm-gray strikethrough = removed, everywhere.
- **Low-confidence cohort:** one constant `LOW_CONFIDENCE_COHORT_N` = **10** (OD-05 Decided 2026-07-27, ai_reviewed — pending human owner confirmation).

## 3. Cross-screen furniture (required components)

| Component | Rule |
|---|---|
| **PageHeader** (DDR-008) | Every routed screen: eyebrow (= nav label) · title · one plain-English description · actions slot. Nav ↔ eyebrow ↔ title must agree |
| **Provenance Ribbon** (DDR-004, revised 2026-08-31) | Snapshot surfaces only (never Admin). **Leads with meaning, not with the identifier:** the frozen date and the Reproducible / Draft mark are what render (teal approved / gold draft + diagonal DRAFT watermark). The snapshot ID and formula version are reached **on command** — a copy control on the ribbon and the full values in Traceability — never printed raw as the ribbon's first element. A bare UUID is not a label; if an ID is shown it is labelled as one. Reproducibility is unaffected: the same ID is still frozen, still exact, still one gesture away (DDR-011) |
| **Shell & primary navigation** (DDR-010) | Grouped left rail. Active state is unmistakable (filled pill + left rule); grouping is carried by **spacing and a divider rather than a shouted label**; icons are quiet and consistently weighted; generous vertical rhythm. Below 900px it collapses to a hamburger drawer (unchanged). The rail is chrome — it never competes with the content for attention |
| **Lineage Drawer** (DDR-005) | Dotted underline on any score; hover = affordance, click = drawer (right slide desktop, full-screen bottom sheet mobile). Contents: input micro-timeline (Clause → Regulator → Jurisdiction → Cohort), formula ID chip + plain-English description (no math notation), VCI, snapshot ID, frozen date |
| **Codex Tooltip** (DDR-006) | Every finding code is hover/focus target → canonical definition + exposure signal + related codes; PDF appends Codex appendix; code chips always navy |
| **View Switch** (DDR-002) | Analyst / Advisor labels; toggle top of card desktop, bottom-fixed bar mobile; both layers frozen in snapshot |
| **StatusDot** (was Live-Dot) | Monitoring/health surfaces only. Colour says what KIND of state it is (`--verified` live / `--standing-bad` stopped), **never how good a score is** — the old emerald pulse collided with green-means-good on the standing scale. Pulse is hidden under `prefers-reduced-motion`; the superseded dot animated forever regardless |
| **Scope statement (front) + Disclosure (end)** (DDR-007, revised 2026-08-31) | **Replaces the per-surface "Intelligence, not legal advice" mark.** A deliverable opens with a plain-language **scope statement** (what was assessed, against what, as of when — the Assessment Scope front matter, F05 RPT-006) and closes with a single **Disclosure** block (what this intelligence is and is not, how it should and should not be used, confidence and cohort caveats). Applies to the report, the PDF, and any exported/partner deliverable. The mark is removed from finding cards, report section furniture, the lineage drawer, and the SME editor. **The removal is contingent on both bookends actually rendering** — a surface that drops the mark without the scope-and-disclosure pair is a regression, not a simplification. **Needs expert + engineer joint approval before code changes** (see §4 DDR-007). |

### 3.1 Component system — shadcn/Radix (owner-decided 2026-08-31)

The UI is built on **shadcn** components vendored into `web/src/components/ui/` and styled with Tailwind v4. This reverses an earlier recommendation to keep hand-rolled CSS; the owner decided, and the decision is recorded here rather than argued in a commit.

Binding rules:

| Rule | Why |
|---|---|
| **Components are owned, not imported from a package.** They live in the repo and may be edited | shadcn's own model; a variant we need (`standing-*`) cannot be added to a locked dependency |
| **A component names a MEANING, never a colour.** `<Badge variant="standing-bad">`, never a red | The superseded `.badge-*` classes hard-coded hex outside the token layer, so the traffic-light decision never reached them |
| **Overlays use Radix** (Dialog, Tooltip, DropdownMenu, Sheet, Popover, Select) | Focus trap, restore-focus, Escape, roving focus and typeahead are where hand-rolled a11y quietly fails. The superseded LineageDrawer wired only Escape; the superseded CodexTooltip was hover-only and unreachable by keyboard |
| **All legacy CSS lives in `@layer legacy`**, declared before Tailwind's layers | In Tailwind v4 unlayered CSS beats layered CSS *regardless of specificity*. Unlayered element rules silently defeated every utility (L-015) |
| **No new inline `style={{}}` for anything a token or utility covers.** Computed values (a bar's `width`, a token-derived `background`) are the exception | 522 inline style objects were the mechanical cause of the app looking like several products |

## 4. Key DDR decisions (defendable choices)

- **DDR-001:** draft state = gold watermark + gold ribbon (not yellow banner — yellow reads as error to legal readers).
- **DDR-002:** dual-voice Analyst (Source Sans metric grid, cold, deterministic) / Advisor (Fraunces italic lede, gold left-rule, warm prose, attribution). The visual inversion *is* the message.
- **DDR-003:** house persona "The Visentix Privacy Desk" in attribution (OD-04 Decided 2026-07-27, ai_reviewed — keep for MVP, revisit at first paying client); styled-but-empty reviewer slot awaiting SME governance.
- **Advisor-hero on mobile (OD-03 Decided 2026-07-27, ai_reviewed):** the Advisor layer may lead on mobile, with the two required mitigations already specced in §3 — a thumb-reachable Analyst/Advisor View Switch (bottom-fixed bar) and a full-screen lineage bottom sheet.
- **DDR-007 (revised 2026-08-31, owner-decided):** the per-surface "Intelligence, not legal advice" mark is replaced by **scope up front + one disclosure at the end**. Rationale: repeating a disclaimer on every card read as defensive and diluted it — a reader who sees it eight times stops reading it. Stating the scope before the reader starts and the disclosure where they finish is both more honest and more legible. This does **not** relax any guardrail: banned-term filtering, VCI suppression, and exposure-only vocabulary are unchanged (business-logic §2, Hard Rules 1–9). Because DDR-007 is a standing trust mechanism, the code change is gated on **expert + engineer joint approval**.
- **DDR-010 (2026-08-31, owner-decided): the quiet rail.** The sidebar reads dated because it is a flat list of labels with a weak active state and three shouted group headings — it *announces* structure instead of *showing* position. The fix is mechanical, not decorative: an unmistakable active state (filled pill + left rule), grouping expressed as spacing and a hairline divider instead of caps labels, consistent icon weight, and more vertical breathing room. Navy shell retained — "confident stillness" is the brand, and the problem was never the color. Explicitly rejected: a light shell (too large a departure for the value) and an icon-only collapsing rail (adds a mode to learn for horizontal space this layout does not yet need).
- **DDR-011 (2026-08-31, owner-decided): earn your place / progressive disclosure.** Persistent space is reserved for what the reader can act on; machinery is one gesture away. See §2. This is the rule that governs whether a new panel ships visible, on-demand, or not at all — and it is the rule to cite when removing one.
- **Register rule:** customer-facing screens use plain language (no jargon like "SSRF"); SME Workbench may use expert jargon ("PII detected").
- **Acronym rule (2026-08-31, owner-decided):** customer-facing surfaces **minimize acronyms**. A house acronym (RSS, PGMS, OSI, DSI, AIGMS, EHP, VCI, CQS, F-0xx, DIR-0xx) is **never the label** a customer reads — it may appear only as a secondary reference *after* a plain-English name, or inside the lineage drawer / methodology / Codex where the reader has asked for the mechanics. Externally-owned acronyms a privacy reader genuinely uses (CCPA, GDPR, FTC) are fine on first mention; anything else is spelled out. Finding codes stay as chips (they are identifiers, not vocabulary) and keep their Codex tooltip. SME/Analyst surfaces are exempt. Plain-English names for each dimension are governed in `intelligence-logic.md` §2 — never coined per-screen.
- **No negative framing (2026-08-31, owner-decided):** customer-facing prose describes the *position and the opportunity*, not a deficiency in the reader. Say what stronger peers disclose and what closing the gap would move, rather than what the organization "fails" or "lacks". This is a register rule on top of the verdict ban, not a replacement for it — see business-logic §2.

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

## 7. Motion (amended 2026-08-31, owner)

Figures and charts may animate **to** their value. Four constraints, all load-bearing:

1. **Arrival only — never a transition between two real values.** A score easing 62 → 71 renders an improvement that did not happen.
2. **The final value is the accessible value from the first frame.** It lives in `aria-label`; the animating text is `aria-hidden`. A number that is only correct once it finishes is unreadable to a screen reader and untestable.
3. **`prefers-reduced-motion` lands instantly** — and so does the *absence* of `matchMedia` (jsdom), which keeps tests deterministic instead of racing `requestAnimationFrame`.
4. **Never in any PDF path.** The print renderer must stay deterministic, and OD-18 already has byte-identity failing.

Implementation: `web/src/components/ui/animated-number.tsx`.

## Changelog

- 1.8 (2026-08-31): **shadcn/Tailwind v4 adopted (owner).** §1 rewritten around the owner-supplied oklch token set with `theme.css` as the single source of colour; standing scale restated per-mode with computed AA ratios and a CI guard (`scripts/check_contrast.mjs`) after measurement found `--mid` shipping at 4.07:1 as text and the light standing values at 2.64–3.34:1 on dark. Added §1.2 non-standing status tokens, §1.3 sequential chart ramp (magnitude only), §1.4 the temporary legacy bridge, §1.5 dark mode (three states). Added §3.1 component-system rules including the `@layer legacy` cascade rule (L-015). Live-Dot superseded by StatusDot. **§7 records the owner's reversal of the motion principle** — arrival animation permitted under four constraints. OD-17 narrowed: the PDF keeps its own stylesheet (owner-confirmed) but must generate its values from `theme.css`.
- 1.7 (2026-08-31): **OD-13 Decided (owner) — the traffic-light standing scale is live.** §1 records the adopted values: Green `#0E7C57`, Yellow `#A87400`, Red (standing) `#B42318`, chosen ink-weight so scores clear AA as text — the superseded pastels did not, which is why scores read washed out. Single source of truth `scoreBands.ts` (`STANDING_GOOD`/`STANDING_MID`/`STANDING_BAD`) mirrored as `--good`/`--mid`/`--bad`. The DDR-001 draft-watermark collision is **resolved**: gold stays the watermark and now carries no judgement anywhere, so the two roles never overlap. **Band thresholds are unchanged** (exposure 45/70, maturity 60/75) — only the colors moved. New **OD-17** records the residue: the PDF renderer's `_RAMP` uses different hexes over four bands at 25/50/75, so palette *and* threshold parity between screen and PDF still needs resolving — the thresholds are expert-owned (Hard Rule 3). Source: owner (product).
- 1.6 (2026-08-31): **Owner feedback pass 2 — shell modernization and progressive disclosure.** §2 adds **earn your place** and **machinery on command** (DDR-011): permanent space goes to what the reader can act on, while snapshot IDs, formula/population versions and cohort internals stay reachable in one gesture but stop leading. §3 revises the **Provenance Ribbon (DDR-004)** to lead with the frozen date and Reproducible mark, with the ID reached via a copy control and Traceability rather than printed raw, and adds a **Shell & primary navigation** row. §4 adds **DDR-010 (the quiet rail** — unmistakable active state, grouping by spacing not caps labels, consistent icon weight, navy retained; light shell and icon-only rail explicitly rejected) and **DDR-011**. Nothing is deleted from any snapshot and no reproducibility guarantee changes — only the default disclosure state. Source: owner (product) verbal notes.
- 1.5 (2026-08-31): **Owner feedback pass — standing colors, band-first scores, bookended disclosure, acronyms.** (a) §1/§2 adopt the **traffic-light standing scale** green/yellow/red for every score surface; teal and gold keep only their non-standing jobs; the Green/Yellow hexes are **PROPOSED pending OD-13** and must not be guessed in code, and OD-13 must resolve the DDR-001 gold-draft-vs-yellow-standing collision. (b) §2 adds **band leads / number follows**, **peer position in words** (vocabulary governed in intelligence-logic §3, gated on OD-14), and **one name, one number** consistency (lesson L-009). (c) §3/§4 revise **DDR-007**: the per-surface "Intelligence, not legal advice" mark is replaced by a plain-language scope statement at the front and one disclosure at the end — **needs expert + engineer joint approval** before code. (d) §4 adds the **acronym rule** (house acronyms are never the customer-facing label) and the **no-negative-framing** register rule. No thresholds, weights, or band cut-points changed. Source: owner (product) verbal notes.
- 1.4 (2026-07-27): Propagated three Phase-1 open-decision closures (all **ai_reviewed**, pending human owner confirmation): **OD-05** — `LOW_CONFIDENCE_COHORT_N = 10` confirmed (§2); **OD-04** — keep "The Visentix Privacy Desk" house persona (DDR-003); **OD-03** — advisor-hero on mobile with the two specced mitigations (§4, referencing §3 furniture). No tokens, scales, or DDR choices changed — decisions recorded against existing behavior.
- 1.3 (2026-07-16): **Score coloring made polarity-aware** (user feedback: a Deficient 34.9 rendered teal while 82.2 exposure rendered red — color contradicted meaning). §2 now defines the maturity color scale from the canonical VICBNF maturity-band thresholds (≥75 teal · ≥60 gold · <60 red — color always agrees with the band label), keeps the exposure scale unchanged, adds the neutral-navy rule for unknown polarity, and requires direction/relative-to affordances + labeled VCI. §1 red-usage rule extended to deficient/lagging maturity (same judgement, other polarity). NEEDS EXPERT/DATA: verify the per-metric polarity registry (esp. Benchmark Deviation, Enforcement Correlation classed as exposure).
- 1.2 (2026-07-16): Route map updated with the seven routes added by F11–F16 (audit finding: doc drift); recorded the grouped-sidebar nav structure and the DDR-008 editorial exception for `/quarterly` and `/trust`.
- 1.1 (2026-07-15): trendColor extended with per-metric polarity flag (maturity vs exposure) per Appendix I prototype review.
- 1.0 (2026-07-15): initial consolidation.
