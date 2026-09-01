# Remaining Work — the single list of what is left

**Version:** 1.0 · 2026-09-01 · Branch `feat/shadcn-ui-system`
**Replaces:** `blocked-work.md` and `ui-migration-status.md`, both folded in here.
**Rule:** nothing on this list is "not done yet". Every item is either stopped on
a named decision or dependency, or queued with its cost stated. When an item
closes, delete its row — a list that only grows stops being read.

**A decision goes in `open-decisions.md`, not here.** This file names what a
decision *blocks*; the register owns the decision itself (L-018).

---

## 0. The one thing stopping the branch

| Item | Who | Action |
|---|---|---|
| **Migration 0049** (`assessment_job.kind`) | Owner | Run `python3 scripts/db/apply_and_record.py` |

The file is written, additive, idempotent, and registered in `APPLY_NOW` per the
runner's own rule. **The two async endpoints (`/admin/trigger-assessment/async`,
`/admin/quarterly/build/async`) cannot run until this lands.** Applying a
migration to a shared database is not a call an agent makes unilaterally.

**Two tests fail until it is applied,** both comparing against the **live**
ledger — `test_schema_migrations_rows_match_file_checksums` exists under that
same name in *both* `tests/test_migrations.py` and
`tests/test_f02_ingestion_foundation.py`, and deselecting one leaves the other
failing. They are deselected, never weakened: the guard is working as designed,
and it should keep failing until the ledger is real.

## Known-failing outside this list

Two suites fail for reasons that are not remaining work, recorded so a green-run
claim is never made on a tree that is not:

| Test | Cause |
|---|---|
| `test_report_design.py::test_pdf_byte_identical_across_simulated_date_change` | **OD-18** — pre-existing, measured 4–6 failures in 10 runs on an unmodified tree |
| `tests/test_training_labels.py` (3 tests) | Environmental: they hit the live database, and *which* three fail changes between a full run and an isolated one — an order/state dependency in the fixtures, not a regression |

---

## 1. Blocked on the expert

Ordered by how much damage each does while open.

| OD | What is blocked | Why it matters now |
|---|---|---|
| **OD-23** | The decomposer's 12-word `list_fragment` bound | **An unconfirmed threshold is live.** Its own memo said "needs expert confirmation"; the code comment dropped the caveat. It decides which clauses are `is_noise`, which feeds presence-count dimensions, which feed scores |
| **OD-18** | The PDF byte-identity guarantee | **The claim is already in print.** Two tests fail ~4–6 runs in 10 on an unmodified tree. Until it closes, byte-identity must not be cited to a customer or a regulator |
| **OD-16** | Obligation modality (must vs should) | **No customer surface may render a "must".** The surviving legal test is "applying law to a specific party's facts" — which is what a "must" does in a per-customer report |
| **OD-14** | Dimension names + peer-position words | **No comparative word renders.** The research killed the one borrowable standard (ICD 203's likelihood lexicon, refuted 0–3), so there is nothing off-the-shelf left |
| **OD-21** | Presence-count saturation calibration | The half of the rehearsal diagnosis that never shipped |
| **OD-15** | Risk-horizon taxonomy | No horizon label renders |
| **OD-10/11/12** | F-005 semantics, F-002 severity, Section 4 measure | Marked *Recommended*, awaiting ratification |
| **OD-17** (thresholds half) | Screen ↔ PDF band cut-points | Hard Rule 3 — bands come only from `intelligence-logic.md` |

---

## 2. Blocked on the owner — naming and structure

The ⬥ items from `route-and-surface-plan.md`. Mechanical once decided; none is
technically hard.

| # | Decision | Recommendation | Cost once decided |
|---|---|---|---|
| A1 | `/rewrite` name — spec says "Trust Language Studio", code says "Illustrative Clause Rewrite" | **"Illustrative Rewrite"** — "illustrative" is load-bearing while OD-16 is open: it stops a reader thinking we drafted their notice | ~1h |
| A2 | `/partner` name — "Portal" vs "Workspace" | **"Partner Workspace"** | ~15m |
| A3 | `/screening` name — "Bulk Analysis" vs "Bulk Screening" | **"Bulk Screening"** — the output is draft-grade; "Analysis" claims the rigour of a full assessment | ~15m |
| A4 | `/intake` → `/assess`? | Yes — "intake" names our process, not the reader's job | ~2h |
| A5 | Split `/workbench` → `/review/findings` + `/review/exemplars` | Yes — two tasks, different times, different gates; it also duplicates the Console's training-stats call | ~half day |
| A6 | Split `/admin` → `/admin` + `/admin/policy` + `/admin/quality` | Yes — `/admin/quality` gives the F17 evaluation backend its missing UI | ~1 day |
| A7 | Split `/partner` → `/partner/clients` + `/partner/settings` | Yes — API keys are a credential surface inside a browsing screen | ~half day |
| A8 | `/clauses/:id` absorbing `/rewrite` | Yes — closes **OD-19** by removing a route rather than adding one | ~1 day |

---

## 3. Blocked on a product decision, not a technical one

Every row here comes from the language research (`research-to-plan.md`). Each is
a gap against an assurance-report skeleton the research verified.

| Item | The question | Why it cannot just be built |
|---|---|---|
| **Action plans with owner + target date** (IIA 15.1) | Does assignment exist in the product at all? | **The largest structural gap in the research.** Recommendations name no owner and are due never. Inventing either to satisfy a format breaks honest-numbers (Hard Rule 7) |
| **Distribution list** (IIA) | Do we record who a report was issued to? | For an artifact designed to be forwarded, "who was this issued to" is the reader's first orientation question, and its absence is conspicuous to an audit-literate reader |
| **Criticality + condition/criteria/cause/effect** (IIA) | Do observations carry *criteria* (what was expected) and *effect* (what follows) as structured fields? | Schema change; the wording is expert-owned |
| **Named dispute / appeal path** (Bitsight) | Do we commit to a process, open to non-customers, with published resolution times? | Headcount and process before it is code. It is how a published score survives third-party scrutiny |
| **OD-22** — 22 SaaS crawl targets | Approve, amend, or reject | The crawler must not touch unapproved domains. Never approved, never seeded — one reason the corpus stayed narrow |
| **OD-20** — categorical chart palette | The supplied ramp is sequential (one hue) | Nothing can tell entities apart by colour, and generating hues is forbidden (§1.3) |
| **Quantified band-to-outcome validation** | Do the bands predict anything? | We assert bands mean something; nothing measures it. Needs data we do not have |
| **Source-summary placement** | Appendix head, or front matter? | **Not settled by evidence** — the research found nothing on placement. Currently at the appendix head |

---

## 4. Blocked on a dependency we own

| Item | Blocked on |
|---|---|
| **Continuous monitoring UI** | The four `/api/monitoring/*` endpoints returning populated data. `MonitoringHero` is correct; it has nothing to draw. `/monitor` is reserved and deliberately unused until then |
| **Assessment history** (F07 AC-9/10) | No endpoint serves it |

---

## 5. Queued — unblocked, just not done

Nothing here needs a decision.

| Item | Size | Note |
|---|---|---|
| **Explorable heatmap cell** (F05 AC-13) | ~half day | Specced, unbuilt |
| **`report.css` generated from `theme.css`** | ~1 day | The concrete half of **OD-17**. WeasyPrint does not parse `oklch()` and Tailwind does not reach it, so the PDF keeps its own stylesheet (owner-confirmed 2026-08-31) — but its values must be **generated**, not hand-copied, or screen and print drift again |
| **Remaining page stylesheets → Tailwind** | ~3 days | See §6. Stylistic uniformity only |
| **`tests/test_training_labels.py` order dependency** | ~2h | Three of its tests fail against the live DB, and *which* three changes between a full run and an isolated one. A test whose result depends on run order cannot tell you anything |
| **L-012 guard** | ~1h | An assertion covering "no cohort ⇒ no percentile" |
| **L-011 guard** | ~half day | F07 AC-11…AC-14 |

---

## 6. UI migration — what is left, and why it is optional

The component-system rebuild is **complete for every surface a customer or an
operator uses daily**. What remains is page-scoped CSS on surfaces that already
adopted the palette through the legacy token bridge (`design-system.md` §1.4).

**Done:** app shell · theme toggle (light/dark/system) · dashboard · login ·
admin Console · Methodology · Finding Codes · Intake · 18 primitives ·
11 bespoke components folded into primitives · `MockBadge`/`StatTile`/`AnimatedNumber`.

**Deleted:** `furniture.css` (631) · `App.css` (431) · `advisor-note.css` (234) ·
`multiselect.css` (83) · `intake.css` (413) · `IntelligenceMark.tsx` · 117 dead
classes across the rest.

**Legacy CSS: 2,562 → 1,873 lines.**

| Stylesheet | Lines | Note |
|---|---|---|
| `index.css` | 443 | The legacy bridge + base element rules. Cannot go until every row below does |
| `explain.css` | 282 | |
| `report.css` | 274 | **Shared with the PDF renderer** — do this as OD-17, not as cleanup (§5) |
| `bulk.css` | 122 | |
| `workbench.css` | 107 | |
| `partner.css` | 107 | |
| `trust.css` | 94 | |
| `vendors.css` | 88 | |
| `quarterly.css` | 75 | |
| `crosswalk.css` | 48 | |
| `rewrite.css` | 43 | |

**The recommendation is to stop here.** These files are now token-based,
dead-code-free, and scoped; converting them changes nothing a reader sees. The
exception is `report.css`, which is worth doing *as OD-17* because screen and
print drifting apart is a correctness problem, not a tidiness one.

### Carried debt

- **The chart ramp is sequential only.** No categorical palette exists (OD-20). A
  surface needing to distinguish entities by colour must raise a decision, not
  generate hues.
- **`beams-background.tsx`** on `/login` is pre-existing decorative canvas
  animation, never reviewed against §7's reduced-motion rule.

---

## 7. Standing guards — what is now mechanically enforced

Ten CI guards, all green. Listed because the useful half of this work was
discovering that each one caught something a review had already missed.

| Guard | What it caught |
|---|---|
| `check_contrast.mjs` | `--mid` shipping at 4.07:1 as text; light standing values at 2.64–3.34:1 on dark |
| `check_colors.py` | 272 hard-coded colours, and `.badge-moderate`/`.badge-low` rendering the *same* colour |
| `check_routes.py` | Routes with no registry entry |
| `check_masking.py` | The IDENT list in `release.sh` had gone stale after renames — the gate would have passed while real identifiers leaked |
| `check_mocks.py` | Mocked surfaces shipping unbadged |
| `check_acronyms.py` | House acronyms as reader-facing labels |
| `check_docs_layout.py` | Two expert-owned decisions sitting at the repo root for five weeks, outside the register (L-018) |
| `check_hedging.py` | Sentences stacking two or more qualifiers — stacking, not hedging |
| `check_dead_css.py` | 117 dead classes; `quarterly.css` was 47 live rules out of 310 |
| `check_labels.py` | `FindingCodex.tsx` defining its *own* `domainLabel` — the public Codex rendered "Ai Automated Decisions" where the report rendered "AI & Automated Decisions" |

---

## Changelog

- 1.0 (2026-09-01): Created, merging `blocked-work.md` 1.0 and
  `ui-migration-status.md` 1.0 into one list. Removed the items closed on branch
  `feat/shadcn-ui-system`: the naming contract (W2), the dead-CSS sweep, Intake,
  significance ordering, the source summary (RPT-007), the acronym purge, the
  mock badges, the task system, and the route registry.
