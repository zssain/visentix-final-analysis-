# Owner Feedback Pass — 2026-08-31

**Branch:** `feedback/owner-report-narrative-pass` (5 commits, 43 files, +1215/−375)
**Status:** all work committed; nothing pushed, nothing merged to `main`.
**Gate at close:** `tsc -b` clean · `npm run build` succeeds · vitest **106/106** · pytest **1138 passed / 16 skipped** (two byte-identity tests deselected and documented as **OD-18**, not silently skipped).

> ⚠️ **Correction — the frontend typecheck was vacuous for most of this session.** `npx tsc --noEmit` in `web/` checks **nothing**: `tsconfig.json` is a solution-style config with `"files": []`. The real gate is **`tsc -b`** (what `npm run build` runs). Everything has since been re-verified with the correct command; two genuine type errors it exposed were fixed. Use `npm run build` or `tsc -b`, never bare `tsc --noEmit`.

This document is the single record of one session of owner feedback: what was decided, what shipped, what is blocked and on whom, and what was deliberately not done.

---

## 0. Read this first — the reproducibility claim is intermittently false

**OD-18 / L-013.** Two renders of the *same frozen snapshot* produce different PDF bytes. Measured at **6 failures in 10 runs** — and at **exactly 6/10 on the unmodified tree**, so it is long-standing and not caused by any change in this branch.

- The differing bytes sit inside a FlateDecode-compressed **font-program stream**: identical `/Length1`, identical compressed length, different content. WeasyPrint's font subsetter emits the glyph table in nondeterministic order.
- It is **not** the Python hash seed — it reproduces under `PYTHONHASHSEED=0`.
- The test suite has been reporting this as an intermittent failure that reads as flake. It is not flake.

Why it matters: the Traceability section tells the reader in plain words that *"Re-pulling this report from the same snapshot ID will produce byte-identical output."* F05 AC-1 and Hard Rule 6 assert the same thing.

> **Do not cite byte-identity to a customer or a regulator until OD-18 closes.**

Options written up, none adopted: pin/patch the subsetter · embed fonts unsubsetted · canonicalize the PDF post-render · narrow the claim to *content*-identity and reword the copy. **Owner: Engineer + Expert.**

---

## 1. Decisions the owner made this session

| # | Decision | Where it landed |
|---|---|---|
| 1 | Standing colors are **green / yellow / red**, not teal/gold/red | OD-13 **Decided** · design-system v1.7 · shipped |
| 2 | **Band leads, number follows** on customer surfaces | design-system §2 · shipped on the dashboard + score dial |
| 3 | Replace the per-surface *"Intelligence, not legal advice"* mark with **scope up front + one Disclosure at the end** | DDR-007 revised · shipped web + PDF |
| 4 | **Hide** the monitoring hero while it cannot populate | F07 surfacing rule · shipped |
| 5 | Consolidate the report **12 sections → 6 parts + appendix** | F05 · shipped |
| 6 | **Honest absence only** — no sample/mock data in customer reports | applied throughout |

---

## 2. DONE

### 2.1 Specs (source of truth changed before code, per AGENTS.md §1.3)

| File | Version | What changed |
|---|---|---|
| `01-foundation/design-system.md` | 1.4 → **1.7** | Traffic-light standing scale with adopted hexes · band-leads-number · one-name-one-number · DDR-010 the quiet rail · DDR-011 earn your place / machinery on command · revised DDR-004 ribbon · acronym rule · no-negative-framing |
| `01-foundation/intelligence-logic.md` | 1.6 → **1.7** | Band-first presentation rule · proposed plain-English dimension names · proposed peer-position vocabulary · paraphrase-but-never-fabricate · new §13 risk horizons |
| `01-foundation/business-logic.md` | 1.2 → **1.3** | Bookended disclosure · no negative framing · must-vs-should modality |
| `00-plan/open-decisions.md` | 1.1 → **1.5** | OD-13 Decided; OD-14…OD-18 added |
| `02-features/F01` | — | Determinate server-driven intake progress (AC-15/16) |
| `02-features/F05` | — | Narrative arc · band-first · paraphrased gaps · explorable heatmap · bookends · six-part presented structure (AC-9…AC-16) |
| `02-features/F07` | — | Assessment history · capability gate · dashboard composition (AC-9…AC-14) |
| `03-ideas/further-ideas.md` | — | "Living assessment" (report-vs-report comparison, improvement narrative, subscription alerts) |
| `scripts/data/hard_rules.md` | — | Hard Rule 9 extended: acronyms + framing. AGENTS.md regenerated. |

### 2.2 Code shipped

**Intake — background processing (`/intake`)**
- Single-column form. The two-column layout existed only to host a results pane.
- **The results pane is gone, and with it a false claim**: it said *"Results will appear here once processing is complete"* while the page actually navigated to the report.
- New `IntakeJobsProvider` in the app shell + floating `JobTracker` (bottom-right, collapsible, per-job dismiss). A submitted assessment keeps reporting **across route changes and a full page refresh**, and links to its report when done. Renders nothing when there is nothing to report.
- Progress advances only from `GET /assessments/{id}/status`. An unplaceable stage renders **indeterminate**, never a guessed percentage; a long-running job says so and is never reported as failed. Guard: `intake_background.test.ts`.

**Shell & dashboard** — `App.css`, `Dashboard.tsx`, `MonitoringHero.tsx`
- Quiet rail (DDR-010): filled active pill + inset left rule, grouping by spacing and a hairline, group headings screen-reader-only, one icon weight.
- Traffic-light standing scale, single source of truth in `scoreBands.ts` (`STANDING_GOOD/MID/BAD`) mirrored as `--good/--mid/--bad`. **Band thresholds unchanged** (exposure 45/70, maturity 60/75) — only colors moved. Values are ink-weight because the old pastels failed AA as text.
- Overall score is band-first; domain tiles 2-col → auto-fit 3-col; the per-card "VCI 71 / Moderate confidence" double line collapsed to one chip (it repeated an identical value six times).
- **Review Activity removed** from the customer dashboard — it rendered internal SME `training_stats`. Register violation (L-011).
- **Latest Snapshot card removed** — a truncated UUID + `Population v269382882`.
- Monitoring hero capability-gated over the *real* endpoint states; `baseline_established` deliberately **not** gated.

**Report** — `ReportView.tsx`, `ScoreDial.tsx`, `sections/*`, `renderer.py`, `report.css`
- **DDR-007 bookends live in web AND PDF.** Mark removed from all 12 sections + lineage panel; one authored `Disclosure` closes the deliverable. Guarded by `ddr007_bookends.test.tsx`.
- **ScoreDial overlap fixed** — `margin-top:-78px` had pulled a two-line caption onto the `0`/`100` hints; the figure is now absolutely centred in the arc.
- **Section 4 chart replaced by a position meter.** A one-bar bar chart is a named anti-pattern; with no peer bar it compared the score to nothing. Plus an integrity fix: the percentile is suppressed when no cohort exists — the report was printing "65.0th percentile" beside its own "cohort not yet constructed" label (L-012).
- **Section 5 no longer renders a dead grid** when no cell is evidenced; cell color now calls `scoreBandColor` instead of a local duplicate of the 70/45 thresholds.
- **Six presented parts + appendix.** The payload is deliberately **untouched** — all twelve blocks, numbers and `section-N` anchors remain, so every snapshot frozen before today still regenerates identically (Hard Rule 6).

| Part | Reader's question | Stored blocks |
|---|---|---|
| 1 Cover & Scope | What am I holding, what was assessed? | 1 |
| 2 Executive Summary | What is the short version? | 2 |
| 3 Where You Stand | How am I doing, and vs whom? | 3, 4, 5, 7 |
| 4 What We Found | What is different about this notice? | 6 |
| 5 What Peers Do, What We Recommend | **the positioning** | 8, 9, 10 |
| 6 What's Changing | What moved, what is coming? | 12 |
| Appendix · Traceability & Method | How was every figure produced? | 11 |

> ⚠️ The part list is duplicated in **exactly two places** — `web/src/report/sectionGroups.ts` and `renderer.py::_REPORT_PARTS`. They must be kept in step or PDF parity breaks.

### 2.3 Tests

| Change | Why |
|---|---|
| `ddr007_bookends.test.tsx` (new, 4 tests) | The mark can never be dropped without its replacement shipping |
| `guardrails.test.ts` — colour assertions now import `STANDING_*` constants | A palette change must not require editing a guard; that is how guards rot. +2 assertions: the scale is three distinct judgements, and teal/gold can never return as standing |
| `test_f20_partner` — comparison section rendered in its actual heading mode | The F20 guarantee (strip band ⇒ identical) is unchanged and still asserted by the stricter check below it |

### 2.4 Lessons recorded

| ID | What bit us | Status |
|---|---|---|
| L-009 | A named measure ("Overall") did not read the same across surfaces | Open until AC-12 is in the gate |
| L-010 | Bare 0–100 scores led customer surfaces; 60→70 is not actionable | Open until AC-11 ships |
| L-011 | Internal SME `training_stats` shipped on a customer dashboard | Open until AC-11…14 ship |
| L-012 | A percentile printed beside "cohort not yet constructed" | Open until an assertion covers it |
| L-013 | **PDF byte-identity intermittently false (6/10)** | **Open — OD-18** |

---

## 3. TO DO — blocked on a decision

Each governing spec explicitly **refuses to render** the affected content until its OD closes, so nothing ships on a guess.

| OD | Decision needed | Owner | Blocks |
|---|---|---|---|
| **OD-18** | PDF byte-identity is intermittently false. Pin/patch subsetter · unsubsetted fonts · canonicalize post-render · or narrow the claim and reword Traceability | **Engineer + Expert** | A reproducibility claim **already in print** |
| **OD-14** | Plain-English dimension names + peer-position words ("above average"). Percentile cut-points deliberately **not** proposed — expert calibration | **Expert + Product** | Peer-position wording everywhere; the acronym rule cannot fully land without the names |
| **OD-15** | Risk-horizon taxonomy (bill = emerging · law = current · enforcement · litigation). Proposed as context only, no scoring effect | **Expert + Engineer** | Section 12 / Part 6 horizon labels |
| **OD-16** | Where obligation modality (must vs should) lives in the schema | **Expert + Engineer** | **No customer surface may display a "must"** until this closes |
| **OD-17** | Screen↔PDF standing palette *and* band-threshold mismatch (web 45/70 vs PDF 25/50/75 over four bands) | **Expert + Engineer** | The same score can read as a different green in the PDF. Threshold half is Hard Rule 3 |
| **OD-19** | Where the clause decomposition explorer lives now that intake is a form | **Product + Engineer** | F01 AC-1/AC-4 have no surface |

Also still open from earlier work: OD-06, OD-07, OD-08, OD-09, OD-10, OD-11, OD-12.

---

## 4. TO DO — not blocked, not yet done

| Item | Notes |
|---|---|
| **Part 5 will look thin** | Owner chose honest-absence-only, so "What Peers Do" shows absence until real approved exemplar language exists. Needs SME exemplar approval, not code |
| **Decomposition explorer has no home (OD-19)** | The split-pane original-vs-clauses view left with the intake results pane, so F01 AC-1/AC-4 currently have no surface. A deliberate consequence of the single-column decision, not an oversight. Clause data and lineage are untouched server-side — only the view is gone |
| **Empty heatmap — cause undetermined** | Could not tell from code alone whether the 2026-06-18 assessment's empty clause→domain mapping is legacy data or a live gap. The display fix is correct either way; the data question is open |
| **F01 determinate progress** | Specced (AC-15/16) — **now implemented** in the JobTracker |
| **F07 assessment history** | Specced (AC-9/10), not implemented |
| **F05 explorable heatmap cell** | Specced (AC-13), not implemented |
| **Report narrative arc copy** | Specced — Cover "what this is", closing summary, one "read more" URL (AC-9/10). Authored copy not written |
| **DDR-007 on non-report surfaces** | The mark still renders on quarterly, trust, crosswalk, bulk, vendors, rewrite, ReviewQueue and in `AdvisorNote`. Deliberately out of scope — those are separate deliverables |
| **"Living assessment"** | Parked in `03-ideas`. Needs the formula/benchmark-version-drift question answered before it can be specced honestly |
| **`test_llm_runpod_serverless`** | One pre-existing asyncio teardown error, unrelated |
| **`tests/test_intake_upload.py`** | Cannot collect — `ModuleNotFoundError: docx`. Pre-existing environment gap |

---

## 5. Explicitly NOT changed

No formula, weight, threshold, band cut-point, taxonomy code, finding code, or banned term was altered in this branch. The report **payload** was not restructured. Guardrails were not relaxed: the verdict ban, VCI suppression, exposure-only vocabulary, honest-absence rules and the source-excerpt exception are all unchanged — DDR-007 moved *where* the disclosure appears, not *whether* it does.

---

## 6. Next actions

1. **Engineer + Expert: triage OD-18.** It is the only item that contradicts a promise already printed in delivered reports.
2. **Expert: OD-14 and OD-16.** These unblock the most customer-visible copy — peer-position wording and any "must".
3. **Owner: review the six-part report** end to end and confirm the part titles and ledes read the way you want.
4. Merge `feedback/owner-report-narrative-pass` once 1–3 are settled.
