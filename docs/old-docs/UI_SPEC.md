# Visentix UI Spec Sheet — Unified Build Reference

> **How to read this document.**  
> This is the single source of truth for every screen and component in the Visentix frontend.  
> It synthesises `visentix-design.md` (DDRs), `visentix-logic.md` (engine/pipeline), `visentix-screens.md` (screen specs), and six screen ideas reviewed and decided on below.  
> Decisions on each idea are documented so we can defend them. Mock data is tracked in **§ MOCK TRACKER** at the end — every mock entry must be replaced before shipping to a real client.

---

## 0. Canonical Design System

These tokens are **fixed**. Never invent new colours outside this set.

| Token | Hex | When to use |
|---|---|---|
| Deep Navy | `#09234F` | Primary background (nav, drawers, chips) |
| Executive Blue | `#005FA3` | Interactive states, links |
| Teal | `#55C7B3` | Verified / approved / live states |
| Soft White | `#F7F8FA` | Page backgrounds |
| Warm Gray | `#D9DDE2` | Borders, dividers, strikethrough diffs |
| Subtle Gold | `#C8A46A` | Provisional / draft / premium accents |
| Red | `#F87171` | **Low-score exposure only** — never decorative |
| Emerald | `#10b981` | Live-dot, upward trend deltas |

**Diff palette rule (applies everywhere diffs appear):**  
`gold (#C8A46A)` = added/new · `warm-gray strikethrough (#D9DDE2)` = removed/old.  
Red stays reserved for low-score exposure. This palette must be consistent across all screens.

**Score-band rule (single source of truth: `web/src/lib/scoreBands.ts`):**  
`≥70` = red (high exposure) · `≥45` = gold (elevated) · below = teal. Never redefine these thresholds locally.

**Trend/delta color rule — color by IMPROVEMENT, not direction:**  
Exposure scores read lower = better. A falling score is **teal** (improving); a rising score is **red** (worsening). Arrows (▲/▼) show direction; color carries the judgement. Applies to deltas, sparklines, and change-feed stripes. Emerald stays reserved for the live-dot only.

**Low-confidence cohort threshold:** one constant, `LOW_CONFIDENCE_COHORT_N` (currently 10, OD-05 pending). Every "small cohort" warning uses it — never a local literal.

**Typography:**
- `Fraunces` — display/serif headlines, Advisor Note lede, report covers
- `Inter` — all UI chrome, labels, nav, buttons
- `Source Sans 3` — data, numerics, monospace IDs (tabular-nums required on all figures)

**Quality floor (every screen):**
- Responsive to mobile (breakpoints: 375px / 768px / 1280px)
- Visible keyboard focus on all interactive elements
- `prefers-reduced-motion`: evidence still reachable, animation skipped
- `font-variant-numeric: tabular-nums` on every numeric value
- "Intelligence, not legal advice" mark at foot of every finding and report (DDR-007)

---

## 1. Intake & Decomposition Explorer — KEEP (new screen — fills gap in screens.md)

**Decision:** Keep. Fills the real gap that `screens.md` waved at the intake form without speccing it. The split-pane "original doc vs extracted clauses" is exactly right — it is the first appearance of lineage in the user journey and should visually rhyme with the lineage drawer (same navy chips, same clause-chip style).

**What was rejected:** The "SSRF-Protected shield" icon. A regulator does not know what SSRF is. Naming an attack class in the customer UI reads as jargon noise or, worse, like we are advertising the class of bug we guard against. The protection is real; the UI should not name the attack. Replace with a quiet **"verified source"** mark.

### Purpose
First screen the customer sees after submitting a privacy notice. Maps the ingestion + decomposition stage of the pipeline. Makes lineage visible from the first interaction.

### Route
`/intake` (customer role) then redirects to `/intake/:assessment_id` once processing begins

### Layout (desktop — split pane)

```
┌────────────────────────────────────────────────────────────────────┐
│  SiteNav (navy)                                                     │
├──────────────────────────────────┬─────────────────────────────────┤
│  LEFT PANE: Original Document    │  RIGHT PANE: Extracted Clauses  │
│                                  │                                 │
│  [Intake form OR rendered doc]   │  Domain filter pills            │
│                                  │  Clause chip list (C-001 …)     │
│  Formats: URL · PDF · Text       │  Each chip: code + domain eye-  │
│                                  │  brow + first 80 chars of text  │
│  URL field: "verified source" ✓  │                                 │
│  mark on successful fetch        │  Click chip → full clause text  │
│  (no SSRF mention anywhere)      │  highlights in left pane        │
│                                  │                                 │
│  Progress steps:                 │  Status: parsing → classifying  │
│  Ingest → Decompose → Classify   │  → ready                        │
└──────────────────────────────────┴─────────────────────────────────┘
```

### Key components

| Component | Detail |
|---|---|
| Intake form | URL input + "verified source" badge on success; PDF upload (max 10MB, MIME: pdf/html/text); raw text textarea |
| Progress stepper | `Ingest → Decompose → Classify` — left-stripe timeline style (same stripe used in mobile change feed and lineage micro-timeline) |
| Clause chips (navy) | `C-118` code + domain eyebrow + text preview. Same chip style as lineage drawer, establishing visual rhyme |
| Domain filter pills | The 8 taxonomy domains + `other`. Filters clause list. |
| Highlight sync | Clicking a clause chip highlights the matching span in the left-pane document view |
| Clause count | `n clauses extracted · n domains detected` — honest, no inflated counts |

### States
- **Waiting** — blank intake form, no assessment in progress
- **Processing** — stepper animated (respects `prefers-reduced-motion`), clause list fills as classification completes
- **Ready** — "View Assessment →" CTA appears, clause list fully populated
- **Error** — parsing failure in plain language (no stack traces)

### Mock items
→ See MOCK TRACKER M-01, M-02

---

## 2. Snapshot Comparator — SPLIT INTO TWO FEATURES (not one screen)

**Decision:** Right idea, but conflated two distinct features that must be separated.

**Feature A — Determinism Proof (provenance ribbon, no diff needed)**  
Proving a re-pull is identical does not require a diff — there is nothing to compare. The provenance ribbon already does this by showing you are on the same frozen snapshot ID. This is covered by DDR-004 and the Provenance Ribbon cross-screen furniture. Do not build a dedicated screen.

**Feature B — Version-over-Time Diff (belongs with Trend, F-012)**  
Diffing S-2041 against S-2040 is change-over-time. This belongs with F-012 Trend and should live in the Monitoring dashboard change feed. It should **lead with score deltas** (41→38, defensible and precise), not prose. Word-level diffs of narrative text are noisy and can surface awkward phrasing to a legal reader.

**Diff palette consistency rule established here:** gold = added, gray strikethrough = removed, everywhere. See §0.

### Where it goes
- Determinism: handled by Provenance Ribbon (DDR-004), already cross-screen furniture.
- Version diff: Continuous Monitoring dashboard → change feed → score delta rows.

---

## 3. Clause Comparison — KEEP IDEA, REPLACE SLIDER WITH SIDE-BY-SIDE

**Decision:** The idea is strong; the drag-slider interaction is wrong and was already wrong in `screens.md §3`. A drag-to-reveal slider works for images (spatial); text reflows, so the middle position shows half-diffed prose, which is fiddly. Fix: **side-by-side layout with diffs always highlighted** and a **"Show differences only / Show full clauses" toggle**. Memorability comes from the honest cohort footer and quality of the diff, not the gimmick.

This replaces §3 "Benchmark Language Comparison slider" in `screens.md`.

### Purpose
Show the customer their clause against the peer cohort exemplar, with differences always visible. One of the most persuasive moments in the report.

### Location
Section 8 of the 12-section report: `BenchmarkLanguage.tsx`

### Layout

```
┌──────────────────────────────────────────────────────────────┐
│  Toggle: [Show differences only]  [Show full clauses]        │
├─────────────────────────┬────────────────────────────────────┤
│  YOUR CLAUSE            │  COHORT EXEMPLAR                   │
│  (Source: C-118, TRK)   │  (Anonymised, SME-reviewed)        │
│                         │                                    │
│  …shares data with      │  …shares data with                 │
│  ~~third parties~~      │  [+disclosed third-party+]         │
│  for marketing          │  [+categories+] for                │
│                         │  [+legitimate business+]           │
│                         │  [+purposes+]                      │
├─────────────────────────┴────────────────────────────────────┤
│  Cohort: n=30 peers · 2026-06-19 · Low confidence if n<10   │
│  [Lineage]  [Finding code chip]                              │
└──────────────────────────────────────────────────────────────┘
```

**~~ ~~** = gray strikethrough (your weaker phrasing removed in exemplar)  
**[+ +]** = gold highlight (exemplar adds this, your clause lacks it)

### Mock items
→ See MOCK TRACKER M-03

---

## 4. Lineage Drawer — MOSTLY COVERED BY DDR-005, ONE UPGRADE KEPT

**Decision:** Mostly redundant with DDR-005, which is already in the component spec. Two corrections and one genuine steal:

**Correction 1 — interaction model:**  
`hover` reveals the affordance (dotted underline). `click` opens the drawer. Hover-to-open a full-panel is unusable on touch — iPads are a primary review device for this audience.

**Correction 2 — no invented formula math:**  
Do not ship made-up equations to lawyers. Real formula definitions come from the engine (F-001…F-014). The lineage drawer shows formula ID and plain-language description only — the math lives in the Methodology page.

**Genuine steal — micro-timeline of inputs:**  
Replace flat input rows with a horizontal micro-timeline: `Clause → Regulator → Jurisdiction → Cohort`. Rhymes with the intake progress stepper and left-stripe mobile timeline.

### Drawer spec (updates DDR-005)

| Element | Detail |
|---|---|
| Trigger | Dotted underline on any score. Hover = underline visible. Click = drawer slides in from right |
| Formula ID | `F-010` as a navy chip, plain-language purpose below |
| Input micro-timeline | Horizontal flow: `C-118 (clause)` → `FTC (regulator)` → `California (jurisdiction)` → `n=30 cohort` |
| VCI | Confidence dial / percentage with label |
| Snapshot ID | `S-2041` monospace, frozen date |
| Formula statement | Plain English only — no LaTeX or math notation |
| Touch | Drawer = full-screen bottom sheet on mobile |
| prefers-reduced-motion | Drawer appears instantly, no slide |

---

## 5. SME De-Identification Mode — KEEP (internal tool, jargon register is correct here)

**Decision:** Keep. The de-id regex checker is a real backend feature. The one-click "replace with [REDACTED]" flow is a genuine trust-builder. Jargon like "PII detected" is appropriate here — the SME Workbench is internal, the audience is expert. This is the opposite register from Screen 1, where the same jargon fails.

**Additions required:**
1. Show **which category was caught** (name / email / URL / custom token) so the SME understands the block.
2. Surface the **training-label counter** here — confirmed / edited / dismissed counts — as part of the rigor story.
3. Red blocking error is acceptable here (second legitimate use of red, after low-score exposure). Style it distinctly: **lock icon + underline**, not a score bar.

### Location
SME Workbench v2 — `ReviewQueue.tsx` → upgrade to three-pane layout

### Layout

```
┌──────────────────────────────────────────────────────────────────────┐
│  SME Workbench · Queue: 4 findings pending                           │
│  Training labels: ✓ 142 confirmed · ✎ 31 edited · ✕ 12 dismissed    │
├──────────────────┬───────────────────────┬───────────────────────────┤
│  SOURCE CLAUSE   │  AUTO FINDING         │  ADVISOR NOTE EDITOR      │
│  (left pane)     │  (center pane)        │  (right pane)             │
│                  │                       │                           │
│  C-118 text      │  Finding code chip    │  Fraunces lede textarea   │
│                  │  Analyst metric grid  │  Body textarea            │
│  🔒 john@doe.com │  Confirm / Edit /     │  Attribution: Privacy Desk│
│  [email]         │  Dismiss              │  Reviewer slot (empty)    │
│                  │                       │                           │
│  🔒 Jane Smith   │                       │  Codex reference panel    │
│  [name]          │                       │                           │
│                  │                       │                           │
│  [Replace all    │                       │                           │
│   with REDACTED] │                       │                           │
└──────────────────┴───────────────────────┴───────────────────────────┘
```

### De-id states
- **Clean** — source clause as plain text, approve button active
- **PII detected** — offending tokens underlined + lock icon + red underline. Category label shown below each flag: [name], [email], [url], [custom]. Approve button disabled.
- **Redacted** — flagged tokens replaced with [REDACTED] inline, approve re-enabled
- **Queue empty** — calm empty state ("All findings reviewed. Next batch expected [date].")

### Mock items
→ See MOCK TRACKER M-04

---

## 6. Mobile Advisor View — KEEP (with one product caveat documented)

**Decision:** Keep. The insight that regulators review on mobile while traveling is real. "Prose-first, metrics as pills" is the right adaptation.

**Product caveat (document for product approval):**  
"Advisor becomes the hero on mobile" is a product decision, not just a layout one — it makes evidence secondary on small screens, slightly undercutting the evidence-first thesis. Fine to default mobile to Advisor view, but:
1. View switch must be a **thumb-tap away** (fixed bottom bar, not buried in a menu).
2. Lineage drawer must render as a **full-screen bottom sheet** on mobile so evidence is never lost, just reordered.

**Pattern to carry forward:** The left-stripe timeline used in the mobile change feed should be reused in the intake flow (Screen 1 progress stepper) and the lineage input micro-timeline (Screen 4). Establishes cross-screen visual language.

### Mobile layout (375px)

```
┌─────────────────────────────┐
│  [← Back]    S-2041 · DRAFT │  ← Provenance ribbon (condensed)
├─────────────────────────────┤
│  TRK-007  data_sharing      │  ← Finding code chip + eyebrow
│  Third-Party Sharing Risk   │  ← Serif title (Fraunces)
├─────────────────────────────┤
│  [Analyst]    [Advisor] ←●  │  ← View switch (bottom-fixed bar)
├─────────────────────────────┤
│  ADVISOR VIEW (default)     │
│                             │
│  Gold left-rule             │
│  Fraunces italic lede…      │
│  Body prose…                │
│                             │
│  Exposure pill · Cohort pill│
│  VCI pill                   │
│                             │
│  [View lineage ↗]           │  ← Opens full-screen bottom sheet
├─────────────────────────────┤
│  "Intelligence, not legal   │
│   advice"                   │
└─────────────────────────────┘
```

### Lineage bottom sheet (mobile)
Full-screen sheet slides up from bottom. Same content as the lineage drawer (DDR-005) — micro-timeline, formula ID, VCI, snapshot ID. Dismiss by swipe-down or ✕.

### Mock items
→ See MOCK TRACKER M-05

---

## Cross-Screen Furniture (required on every surface)

These components appear globally. Their specs are the authority.

### PageHeader (every routed screen)
- One component (`PageHeader.tsx`): **eyebrow** (where you are — matches the nav label) · **title** · **description** (one plain-language sentence saying what the screen does) · **actions** (right side: status chips, counts, primary CTA).
- Every routed screen opens with it. No screen may invent its own header layout.
- Language balance: the title may use product vocabulary (Codex, Workbench); the description must be plain English a first-time legal reader understands.
- Nav label ↔ eyebrow ↔ title must agree. Current map:
  | Route | Nav label | Title |
  |---|---|---|
  | `/assessments` | Monitor | Privacy Intelligence Monitor |
  | `/intake` | Intake | Submit a Privacy Notice |
  | `/review` | Workbench | SME Workbench |
  | `/admin` | Admin | Admin Console |
  | `/codex` | Codex | Finding Codex |
  | `/methodology` | Methodology | How Visentix Works |

### Provenance Ribbon (DDR-004)
- Appears on every report page and every dashboard surface
- **Snapshot surfaces only** — never on Admin or other screens where nothing is a reproducible snapshot; diluting the ribbon's meaning breaks its trust story
- Contents: `S-2041` (monospace snapshot ID) · formula version + frozen date · Reproducible mark
- Approved state: teal mark. Draft state: gold mark + diagonal "DRAFT — PENDING EXPERT REVIEW" watermark behind content
- Condensed variant on mobile (ID + status mark only, tap to expand)

### Lineage Drawer (DDR-005, updated by §4 above)
- Triggered by dotted underline on any score
- Hover = affordance visible. Click/tap = drawer opens
- Desktop: right-panel slide-in. Mobile: full-screen bottom sheet
- Contents: micro-timeline, formula ID + plain description, VCI, snapshot ID, frozen date
- No mathematical notation — plain English only

### Codex Tooltip (DDR-006)
- Every finding code (TRK-007, SH-002, RT-003) is a hover/focus target
- Tooltip shows: canonical Codex definition + exposure signal + related codes
- PDF export auto-appends relevant Codex entries as appendix
- Code chips are always navy, everywhere

### View Switch (DDR-002)
- Appears wherever a finding has both Analyst and Advisor layers
- Label: `Analyst` / `Advisor` (not "Data / Summary")
- Desktop: toggle at top of finding card. Mobile: bottom-fixed bar (thumb-reachable)
- Both layers stored in snapshot → both reproducible

### Live-Dot
- Emerald pulse animation (`.live-dot`)
- Monitoring surfaces only
- `prefers-reduced-motion`: static dot, no pulse

### "Intelligence, not legal advice" mark (DDR-007)
- Appears at foot of every finding card and report section, and in the lineage drawer and SME editor
- **Not** on Login, Monitor chrome, Admin, Codex, or Methodology — repeated everywhere it reads as nervousness, not discipline
- Small, designed mark — not a paragraph of legalese
- Never omit where findings/reports appear; never make it larger than necessary

---

## Existing Screens — Status & Gaps

| Screen | screens.md status | Codebase status (2026-07-15) | Gap |
|---|---|---|---|
| Advisor Note component | "built — see visentix-advisor-note.html" | Built — `AdvisorNote.tsx` | Wire real data (mocks per tracker) |
| Continuous Monitoring dashboard | Hero of release | Built — `Dashboard.tsx` (PageHeader, hero sparkline, domain score+delta cards, feed, alerts) | M-06/M-07/M-08/M-09 mocks to wire |
| Report showcase upgrade | Styling on existing 12 sections | 12 sections built with ribbon, lineage affordances, side-by-side diff | Reader-register toggle still a stub (OD-02) |
| Finding Codex | Spec exists | Built — `FindingCodex.tsx` | M-11 mock → `/api/codex` |
| Methodology / About page | Spec exists | Built — `Methodology.tsx` | — |
| Quarterly Report reader | Spec exists | No page exists | New page to build |
| SME Workbench v2 | Spec exists | Built — `ReviewQueue.tsx` three-pane + de-id mode | M-04 mock; wire real queue actions |
| Framework Crosswalk | "held for product approval" | Not built | Hold — build shell only |
| Intake & Decomposition Explorer | Gap in screens.md | Built — `Intake.tsx` split-pane + stepper | M-01/M-02 mocks; PDF mode UI-only |

### Report sections in codebase vs. spec

All 12 sections exist as TSX files in `web/src/report/sections/`. Known gaps:

| Section | File | Gap |
|---|---|---|
| Cover | Cover.tsx | Missing: gold hairline rules, VCI dial, provenance ribbon |
| Executive Summary | ExecutiveSummary.tsx | Missing: reader-register toggle |
| Risk Dashboard | RiskDashboard.tsx | Missing: lineage drawer affordances on score cells |
| Benchmark Intelligence | BenchmarkIntelligence.tsx | Missing: cohort size honest display |
| Regulator Exposure | RegulatorExposure.tsx | Missing: Codex tooltip on finding codes |
| Disclosure Findings | FindingsTable.tsx | Missing: Advisor Note component integration |
| Compound Risk | CompoundRisk.tsx | Missing: lineage drawer |
| Benchmark Language | BenchmarkLanguage.tsx | Slider → replace with side-by-side (§3 above) |
| Recommendations | Recommendations.tsx | Review for guardrail compliance |
| Risk Reduction | RiskReduction.tsx | Review for guardrail compliance |
| Traceability | Traceability.tsx | Missing: snapshot ID, formula version display |
| Trend & Emerging Risk | TrendPanel.tsx | Missing: sparklines, delta display, no_prior_history state |

---

## Build Order (recommended)

1. Design system tokens → `index.css` — establish all CSS vars for tokens above
2. Cross-screen furniture → `ProvenanceRibbon`, `LineageDrawer`, `CodexTooltip`, `ViewSwitch`, `LiveDot`, `IntelligenceMark` components
3. Advisor Note component → core novel component; blocks everything that uses it
4. Intake & Decomposition Explorer → new route, new screen
5. Report section upgrades → layer furniture onto existing 12 sections, replace BenchmarkLanguage slider
6. Continuous Monitoring dashboard → hero screen rebuild
7. SME Workbench v2 → three-pane + de-id mode
8. Finding Codex page → new route
9. Methodology page → new route
10. Mobile responsive pass → all screens, mobile Advisor View, bottom sheet
11. Quarterly Report reader → editorial layout
12. Framework Crosswalk shell → held for product approval

---

## Open Decisions (waiting on product approval)

| ID | Decision | Blocker |
|---|---|---|
| OD-01 | Framework Crosswalk copy — descriptive vs. verdict language | Product approval must confirm guardrail extension |
| OD-02 | Reader register names — Executive / Practitioner / Plain-language (final names TBD) | Product approval |
| OD-03 | "Advisor becomes hero on mobile" default — does it contradict evidence-first thesis? | Product decision documented in §6 |
| OD-04 | Real SME names in attribution slot — governance timing | SME team |
| OD-05 | Cohort size threshold for "low confidence" label | Data team to define n cutoff |

---

---

# MOCK TRACKER

> Every item in this table is **mock data** that must be replaced before shipping to a real client.
> When replacing, delete the row or mark it [REPLACED] and note the real data source.

| ID | Screen | What is mocked | Real data source when ready | Notes |
|---|---|---|---|---|
| M-01 | Intake & Decomposition Explorer | Clause extraction simulated with static JSON fixture while LLM classifier is offline | `POST /api/assessments` → `disclosure_clause` table rows from Supabase | Backend route `assessments.py` exists; wire to real decomposition output |
| M-02 | Intake & Decomposition Explorer | "verified source" badge always shown on URL fetch success | Real SSRF validation result from backend (`ssrf_protected` flag in response) | Backend already validates SSRF; frontend just needs to read the flag |
| M-03 | Clause Comparison (BenchmarkLanguage) | Exemplar clause is hardcoded as a static string in BenchmarkLanguage.tsx | `disclosure_clause` rows where `is_exemplar = true`, queried from Supabase | SME must first clean and approve exemplars via Workbench |
| M-04 | SME Workbench — De-id checker | Training label counts (confirmed/edited/dismissed) are hardcoded as 142 / 31 / 12 | `GET /api/admin/health` training_stats block, or direct Supabase query on `training_label` table | Admin health route exists in `health.py` — surface stats from there |
| M-05 | Mobile Advisor View | Advisor Note prose is hardcoded house-voice text | Frozen `report_snapshot` Advisor layer, fetched from report endpoint | Report snapshot freezes prose at publication; render from snapshot, never regenerate |
| M-06 | Continuous Monitoring dashboard | Sparkline data is static array of scores | F-012 Trend Delta outputs from `formula_version` + `report_snapshot` tables | Trend endpoint not yet exposed; will need new `/api/monitoring/trend` route |
| M-07 | Continuous Monitoring dashboard | Change feed is a static list of 4 hardcoded events | Real events from `monitoring_event` table, filtered by org | `monitoring_event` table exists in schema; backend route needed |
| M-08 | Continuous Monitoring dashboard | Alert center cards are static | F-013 Alert Escalation outputs from Supabase `enforcement_record` / monitoring logic | Alert route needed |
| M-09 | Report — Cover, Traceability | Provenance ribbon shows hardcoded `S-2041`, date `2026-06-19` | Real `report_snapshot.id` and `snapshot_frozen_at` from Supabase | Already stored in DB; just needs to be threaded through report fetch response |
| M-10 | Lineage Drawer | Formula plain-language descriptions are hardcoded strings | `formula_version` table — `description` column | Table exists; descriptions may need to be populated if NULL |
| M-11 | Finding Codex | Codex entries are a static JSON array | `finding_type` catalog table in Supabase | Table exists with real codes; build a `/api/codex` GET endpoint |
| M-12 | All screens | Cohort size shown as `n=30` everywhere | Real cohort query: `SELECT COUNT(*) FROM benchmark_membership WHERE cohort_id = …` | Never display a static n; always query live |
| M-13 | Admin Console | Global Gate Mode setting simulated in React console component | `GET /api/admin/gate-mode` and `POST /api/admin/gate-mode` | Backend endpoints do not exist; UI simulates the configuration state locally. |
| M-14 | Admin Console | Trigger Batch Assessment simulated with a delay and notification | `POST /api/admin/trigger-assessment` | Backend route exists as a stub returning not_implemented; UI simulates full execution. |

---

*Last updated: 2026-07-15. All phrasing in this document follows exposure/maturity/likelihood/benchmark/confidence language — no legal verdicts. 2026-07-15 consistency pass: PageHeader furniture (DDR-008), improvement-based delta coloring (DDR-009), score-band + low-confidence-cohort constants centralised in `scoreBands.ts`, trust-mark placement trimmed (DDR-007 refinement), provenance ribbon restricted to snapshot surfaces, domain scorecards lost their mini-sparklines.*
