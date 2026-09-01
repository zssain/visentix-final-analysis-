# Session Report — 2026-09-01

**Branch:** `feat/shadcn-ui-system` · 59 commits, 35 of them today · never merged to main
**Gate at close:** pytest **1186 passed**, vitest **181/181**, `tsc -b` clean, build clean, **ten CI guards green**
**Known-failing:** the OD-18 PDF byte-identity pair — pre-existing, measured at 5 failures in 10 runs on an *unmodified* tree

This is a dated record: true on its date. The live list of what is left is
[`visentix-specs/00-plan/remaining-work.md`](../../../visentix-specs/00-plan/remaining-work.md);
every decision awaiting a human is in
[`open-decisions.md`](../../../visentix-specs/00-plan/open-decisions.md).

---

## 1. What we accomplished

### 1.1 The report — the artifact customers forward

| Change | Why it mattered |
|---|---|
| **Source summary** (RPT-007, F05 AC-17) | Per-judgment "what this rests on" + evidence-base strength, stated **separately from the score**, so a good score on a thin base still reads as a thin base. Frozen into the snapshot, never recomputed |
| **Significance ordering** (AC-19) | Findings were sorted **alphabetically by code**, and takeaways took `findings[:5]` — so a low-severity `AI-004` displaced a high-severity `SH-002`. The "top" findings a report led with were the alphabetically first ones |
| **Explorable heatmap cell** (AC-13) | Every cell is a real `<button>`; mouse and keyboard are one path. Panel renders only frozen snapshot fields |
| **Contents map + one part-heading shape** | The document had no statement of what it contained — the first thing a forwarded reader needs |
| **Cover before contents, and an arrival** | A reader learns whose report it is before being handed a map of it. Staggered entrance, arc drawing to its value, counting figure |
| **Traceability, Disclosure, Recommendations rebuilt** | See §2.4 for the dark-mode bug this uncovered |
| **Register selector made real** | It had rendered three badges that did nothing (DDR-011) |

### 1.2 The app — every route on the component system

**All 13 routes** are on shadcn/Tailwind: assessments · intake · rewrite · vendors · workbench · quarterly · crosswalk · finding codes · methodology · trust center · admin · partner · bulk screening.

**Legacy CSS: 2,562 → 276 lines**, and every class remaining in `index.css` is live.
Deleted outright: `furniture.css` (631) · `App.css` (431) · `advisor-note.css` (234) ·
`intake.css` (413) · `multiselect.css` (83) · `workbench.css` · `bulk.css` ·
`partner.css` · `trust.css` · `vendors.css` · `quarterly.css` · `crosswalk.css` ·
`rewrite.css` · plus 117 dead classes and 30 more from `index.css`.

Also: a glass sidebar and page header built to **one recipe**; a dark-mode theme
toggle; a `ReportCard` shaped 8.5:11 with band-anchored gradient, tilt and
parallax; a paginated assessments table; a naming contract (§1.4).

### 1.3 Foundations that did not exist before

- **One background-task system** replacing three unrelated ones (`assessment_job` + stage polling + a floating tracker).
- **A route registry** — one declaration per route, with build-flag masking that survives dead-code elimination.
- **A label registry** (`lib/labels.ts`) — a reader never sees a raw enum, and an unknown value stays *visibly* unknown rather than being prettified into a plausible word.
- **Published, versioned methodology** — `GET /formulas/method-version`, public, exposing version and dates but never a weight or a threshold.

### 1.4 Ten CI guards

Each was written to catch a drift already measured, and **each was verified to reject a known-bad input before being relied on.**

| Guard | What it caught on its first run |
|---|---|
| `check_contrast.mjs` | `--mid` shipping at **4.07:1** as text; light standing values at 2.64–3.34:1 on dark |
| `check_colors.py` | 272 hard-coded colours; `.badge-moderate` and `.badge-low` rendering the **same** colour |
| `check_routes.py` | 14 disagreements between §6, the registry and the router |
| `check_masking.py` | `release.sh`'s identifier list had gone **stale after renames** — the gate would have passed while real identifiers leaked |
| `check_mocks.py` | Mocked surfaces shipping unbadged |
| `check_acronyms.py` | House acronyms as reader-facing labels |
| `check_docs_layout.py` | Two expert-owned decisions at the repo root for five weeks, outside the register |
| `check_hedging.py` | Sentences stacking two or more qualifiers (stacking, not hedging) |
| `check_dead_css.py` | 117 dead classes; `quarterly.css` was 47 live rules out of 310 |
| `check_labels.py` | `FindingCodex.tsx` defining its **own** `domainLabel` — the public Codex said "Ai Automated Decisions" where the report said "AI & Automated Decisions" |

### 1.5 Documentation

Plan documents **11 → 8**, each authoritative for one thing.
`docs/old-docs/` (19 files) deleted; `docs/remediation/` (13) archived by month;
`docs/SECURITY_MATRIX.md` and `docs/UI_DESIGN_SYSTEM.txt` deleted — both had gone
false (see §2.5). `design-system.md` 1.8 → **1.11**; four new lessons; the OD
register gained OD-20…OD-23.

---

## 2. Bugs found — the pattern

Nearly every defect this session was the same shape: **absence, or a missing
value, rendering as something favourable — or a control that lies.**

### 2.1 Absence rendering as a good number

- **`dashboard-stats` emitted `0` for an unmeasured metric.** The client un-guessed it with `score > 0`, which is wrong in both directions: a genuine 0 is the *best possible* result on an exposure metric and rendered as "not recorded"; and any surface not repeating the guess would print a fabricated 0 as real. Now `null`.
- **Compound risk: a missing score rendered green.** Zero exposure reads as good.
- **Assessments showed "No assessments yet" when the backend was unreachable.** `api.get(...).catch(() => [])` collapsed a dead host, a 500 and a genuinely empty list into one friendly empty state — and made the error branch beneath it unreachable code.
- **The report card apologised for a score that existed.** It fell back to the org-wide figure and, when that couldn't be attributed, printed a sentence explaining *our plumbing* to the reader. `derived_data_item` carries `notice_id`; 71 of 100 notices had their own score. The endpoint just never read it.

### 2.2 Labels that state the wrong thing

- **Quarterly status: `status === "draft" ? … : "Approved"`.** Every status that is not literally `draft` rendered as **Approved** — on a table where Approved is the difference between "nobody may see this" and "this is public".
- **Four chips built a CSS class from a raw database value** (`bulk-status-chip st-${status}` and three others). An unmapped value rendered an unstyled chip carrying the database's own word.
- **"Draft — gold watermark"** named a PDF rendering detail, on a badge that was already gold.
- **"Back to Assessments" pointed at `/`**, which is the *role-based* home — an admin landed on the Console, an SME on the Workbench. The label lied to everyone who was not a customer.

### 2.3 Controls and colour that mislead

- The executive summary's **register selector rendered three badges that did nothing**.
- **Effort/impact pills had no background** — `var(--teal)18` is invalid CSS.
- `scoreBands.ts` was a **second source of truth**, so every `scoreBandColor()` caller rendered the *light* standing colour in dark mode (2.64–3.34:1, failing AA).
- The selected nav item was **shadcn's stock blue** (`oklch(0.488 0.243 264)`) — the one saturated blue in a product with no blue, shipped with the token set and never replaced.

### 2.4 Dark mode

**Traceability's zebra striping set a literal `white`** from an inline style, so in dark mode it struck five blinding bands across the card and painted light-on-light text over them. Unreadable.

`check_colors.py` did not catch it: its named-colour rule ran over stylesheets only, because in TSX a bare `teal` is usually a variable. A **quoted** one never is — the guard now checks that case, verified against the original line.

### 2.5 Documents that had gone false

- `docs/UI_DESIGN_SYSTEM.txt` still declared the stack as *"Pure CSS with CSS Variables (NO Tailwind)"*.
- `docs/SECURITY_MATRIX.md` property 9 restated the PDF byte-identity claim **with no caveat** — in the one class of document a reader trusts most, while OD-18 is open precisely because that claim is intermittently untrue.

### 2.6 Guards that were not looking

- **`index.css` was exempt from the dead-CSS guard.** When every page using `.btn-primary`, `.badge-gold` and `.stat-card` moved to components, the guard reported a clean tree — it was not looking at the stylesheet those classes lived in. 30 dead classes, found by hand.
- **My own `[&_.section-label]` variants** targeted a class no element carries. They looked live to a text search and styled nothing.

---

## 3. What needs work

Ordered by how much damage each does while open.

### 3.1 Yours to run — one command

| Item | Action |
|---|---|
| **Migration 0049** (`assessment_job.kind`) | `python3 scripts/db/apply_and_record.py` |

Additive, idempotent, registered in `APPLY_NOW`. **The two async endpoints
(`/admin/trigger-assessment/async`, `/admin/quarterly/build/async`) cannot run
until it lands**, and two ledger tests stay deselected. Applying a migration to a
shared database is not a call an agent makes unilaterally.

### 3.2 Before a customer sees a report

| Item | Why now |
|---|---|
| **OD-23** — the decomposer's 12-word `list_fragment` bound | **An unconfirmed threshold is live.** Its own memo said "needs expert confirmation"; the code comment dropped the caveat. It decides which clauses are `is_noise`, which feeds presence-count dimensions, which feed scores |
| **OD-18** — PDF byte-identity | **The claim is already in print**, in the report's closing line and in the Traceability copy. Narrowing it to *content*-identity is option (d) of that decision — a one-minute change once you decide |
| **Two different snapshot IDs in one Traceability panel** | The prose line carries the assembly-time id; the table carries the authoritative `report_snapshot.id`. Frozen content, so this is a data decision, not a display one |

### 3.3 Operational

| Item | Detail |
|---|---|
| **`web/.env` points at a dead Azure host** | `visentix-api.salmoncoast-…azurecontainerapps.io` returns NXDOMAIN. A production build made today ships a broken API URL. Dev is unblocked via `web/.env.local`; the deploy target of record still needs a decision |
| **`test_training_labels.py` order dependency** | Three tests fail against the live DB, and *which* three changes between a full run and an isolated one. A test whose result depends on run order cannot tell you anything. ~2h |
| **`HeatmapCell.vci` is 0–1 where every other VCI is 0–100** | Hard Rule 5's suppression threshold (`< 40`) is written on the 0–100 scale, so a `vci < 40` check against cell values would mark **every cell** suppressible. Nothing reads it today, so no live bug — reconciling the scales is a scoring change (Hard Rule 3) |
| **L-012 guard** (~1h) | An assertion covering "no cohort ⇒ no percentile" |
| **L-011 guard** (~half day) | F07 AC-11…AC-14 |

---

## 4. What is for later

### 4.1 Owner decisions — naming and structure

Eight ⬥ items from `route-and-surface-plan.md`. Mechanical once decided, ~3 days total: `/rewrite` and `/partner` and `/screening` names · `/intake` → `/assess` · four screen splits (`/workbench`, `/admin`, `/partner`, and `/clauses/:id` absorbing `/rewrite`, which closes OD-19 by removing a route rather than adding one).

### 4.2 Expert decisions

**OD-16** (must vs should — no customer surface may render a "must") · **OD-14** (dimension names and peer-position words — the research *killed* the one borrowable standard, ICD 203's likelihood lexicon, refuted 0–3) · **OD-21** (presence-count saturation) · **OD-15** (risk horizons) · **OD-10/11/12** (recommended, awaiting ratification) · **OD-17** thresholds half.

### 4.3 Product decisions

Each is a gap the language research found against every assurance-report skeleton it verified:

- **Action plans with owner + target date** — the largest structural gap. Recommendations name no owner and are due never; inventing either breaks honest-numbers.
- **Distribution list** — for an artifact designed to be forwarded, "who was this issued to" is the reader's first orientation question.
- **Criticality + condition/criteria/cause/effect** as structured fields — schema change, expert-owned wording.
- **Named dispute/appeal path** — headcount and process before it is code.
- **OD-22** — 22 SaaS crawl targets, never approved, never seeded. One reason the corpus stayed narrow.
- **OD-20** — no categorical chart palette exists; the supplied ramp is sequential, and generating hues is forbidden.

### 4.4 Queued build work

| Item | Size |
|---|---|
| **`report.css` generated from `theme.css`** — the concrete half of OD-17 | ~1 day |
| **Continuous monitoring UI** — blocked on the four `/api/monitoring/*` endpoints returning data | — |
| **Assessment history** (F07 AC-9/10) — no endpoint serves it | — |
| `explain.css` (282) and `report.css` (556) → Tailwind | ~2 days |

### 4.5 Standing constraint on all of it

Not one verified source in the language research concerns B2B SaaS privacy
reports. The evidence is UK statutory audit, internal audit, US securities
prospectuses, US intelligence analysis, UPL doctrine and cybersecurity ratings.
**Every application is analogical and must be stated as such** — including in any
spec that cites it.

---

## 5. Method notes worth keeping

Three things this session proved the hard way:

1. **Verify a guard rejects a known-bad input before trusting it.** The first validation gate passed everything for a bogus reason (wrong esbuild flag) and reported success on a broken tree. Every guard added since has been mutation-checked.
2. **Judge a flaky test on ten runs, not four.** The PDF determinism test failed 4/4 with a change and passed 4/4 clean — which reads as a clear regression. Over ten runs each it was 5/10 clean and 2/10 changed: pre-existing, and the small sample pointed confidently the wrong way.
3. **When the honest thing to write is a sentence explaining why you cannot show something, the data is usually reachable and the plumbing is the bug.** That happened twice today — the fabricated `0` and the report card's apology.
