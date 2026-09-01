# Remaining Work — what is left, and who unblocks it

**Version:** 2.0 · 2026-09-01 · Branch `feat/shadcn-ui-system`

**This file holds only open items.** Nothing here is done. When something
closes, delete its row — a list that only grows stops being read. What was
built, and every defect it uncovered, is in
`logs/archive/2026-09/SESSION-REPORT-2026-09-01.md`; that is a dated record and
does not belong here.

**A decision goes in `open-decisions.md`, not in a plan.** This file names what
a decision *blocks*; the register owns the decision itself (L-018).

---

## 1. Can be done now

Nothing below needs anyone's approval.

| Item | Size | Note |
|---|---|---|
| **`report.css` generated from `theme.css`** | ~1 day | The concrete half of **OD-17**. WeasyPrint parses no `oklch()` and Tailwind does not reach it, so the PDF keeps its own stylesheet (owner-confirmed 2026-08-31) — but its values must be **generated**, or screen and print drift again. The palette half is a design call; the *threshold* half is Hard Rule 3 and expert-owned |
| **`test_training_labels.py` order dependency** | ~2h | Three tests fail against the live DB, and *which* three changes between a full run and an isolated one. A test whose result depends on run order cannot tell you anything |
| **L-012 guard** | ~1h | An assertion covering "no cohort ⇒ no percentile" |
| **L-011 guard** | ~half day | F07 AC-11…AC-14 |
| **`explain.css` (282) + `report.css` (556) → Tailwind** | ~2 days | The last two stylesheets. Every route is already converted; this is the report surface, and `report.css` is entangled with OD-17 above — do them together |

---

## 2. Needs you — one command

| Item | Action |
|---|---|
| **Migration 0049** (`assessment_job.kind`) | `python3 scripts/db/apply_and_record.py` |

Additive, idempotent, registered in `APPLY_NOW`. **The two async endpoints
(`/admin/trigger-assessment/async`, `/admin/quarterly/build/async`) cannot run
until it lands.** Two ledger tests stay deselected meanwhile — the same test name
exists in `tests/test_migrations.py` *and* `tests/test_f02_ingestion_foundation.py`,
so deselecting one leaves the other failing. They are deselected, never weakened:
the guard is working, and it should keep failing until the ledger is real.

---

## 3. Needs the expert

Ordered by how much damage each does while open.

| OD | What is blocked | Why it matters now |
|---|---|---|
| **OD-23** | The decomposer's 12-word `list_fragment` bound | **An unconfirmed threshold is live.** Its own memo said "needs expert confirmation"; the code comment dropped the caveat. It decides which clauses are `is_noise`, which feeds presence-count dimensions, which feed scores |
| **OD-18** | The PDF byte-identity guarantee | **The claim is already in print** — the report's closing line and the Traceability copy. Narrowing it to *content*-identity is option (d) of that decision and a one-minute change once you rule |
| **OD-16** | Obligation modality (must vs should) | **No customer surface may render a "must".** The surviving legal test is "applying law to a specific party's facts" — which is what a "must" does in a per-customer report |
| **OD-14** | Dimension names + peer-position words | **No comparative word renders.** The research killed the one borrowable standard (ICD 203's likelihood lexicon, refuted 0–3), so there is nothing off-the-shelf left |
| **OD-21** | Presence-count saturation calibration | Presence-count dimensions saturate on a modest notice, so a mid-quality notice can max a dimension |
| **OD-15** | Risk-horizon taxonomy | No horizon label renders |
| **OD-10/11/12** | F-005 semantics, F-002 severity, Section 4 measure | Marked *Recommended*, awaiting ratification |
| **OD-17** (thresholds half) | Screen ↔ PDF band cut-points | Hard Rule 3 — bands come only from `intelligence-logic.md` |

---

## 4. Needs the owner — naming and structure

The ⬥ items from `route-and-surface-plan.md`. Mechanical once decided; none is
technically hard. ~3 days in total.

| # | Decision | Recommendation | Cost |
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

## 5. Needs a product decision

Each is a gap the language research found against every assurance-report
skeleton it verified. None can be built without the decision, because building
it would mean inventing the missing value.

| Item | The question | Why it cannot just be built |
|---|---|---|
| **Action plans with owner + target date** (IIA 15.1) | Does assignment exist in the product at all? | **The largest structural gap in the research.** Recommendations name no owner and are due never; inventing either to satisfy a format breaks honest-numbers (Hard Rule 7) |
| **Distribution list** (IIA) | Do we record who a report was issued to? | For an artifact designed to be forwarded, "who was this issued to" is the reader's first orientation question |
| **Criticality + condition/criteria/cause/effect** (IIA) | Do observations carry *criteria* (what was expected) and *effect* (what follows) as structured fields? | Schema change; the wording is expert-owned |
| **Named dispute / appeal path** (Bitsight) | Do we commit to a process, open to non-customers, with published resolution times? | Headcount and process before it is code. It is how a published score survives third-party scrutiny |
| **OD-22** — 22 SaaS crawl targets | Approve, amend, or reject | The crawler must not touch unapproved domains. Never approved, never seeded — one reason the corpus stayed narrow |
| **OD-20** — categorical chart palette | The supplied ramp is sequential (one hue) | Nothing can tell entities apart by colour, and generating hues is forbidden (design-system §1.3) |
| **Quantified band-to-outcome validation** | Do the bands predict anything? | We assert bands mean something; nothing measures it. Needs data we do not have |
| **Source-summary placement** | Appendix head, or front matter? | **Not settled by evidence** — the research found nothing on placement. Currently at the appendix head |

---

## 6. Blocked on a dependency we own

| Item | Blocked on |
|---|---|
| **Continuous monitoring UI** | The four `/api/monitoring/*` endpoints returning populated data. `MonitoringHero` is correct; it has nothing to draw. `/monitor` is reserved and deliberately unused until then |
| **Assessment history** (F07 AC-9/10) | No endpoint serves it |

---

## 7. Known-failing, and not remaining work

Recorded so a green-run claim is never made on a tree that is not.

| Test | Cause |
|---|---|
| `test_pdf_determinism.py::test_frozen_snapshot_pdf_is_byte_identical` and `test_report_design.py::test_pdf_byte_identical_across_simulated_date_change` | **OD-18.** Pre-existing and intermittent: **5 failures in 10 runs on an unmodified tree**, measured 2026-09-01. Which of the two manifests varies between runs, so one full run names one and a re-run names the other. Judge it on ten runs, never on one — four consecutive results once pointed the wrong way |

---

## 8. Loose ends worth closing

Small, and each is a real inconsistency rather than a preference.

| Item | Detail |
|---|---|
| **Two snapshot IDs in one Traceability panel** | The prose line carries the assembly-time id; the table carries the authoritative `report_snapshot.id`. Frozen content, so this is a data decision, not a display one |
| **`web/.env` points at a dead Azure host** | `visentix-api.salmoncoast-…azurecontainerapps.io` returns NXDOMAIN. A production build made today ships a broken API URL. Dev is unblocked via `web/.env.local`; the deploy target of record needs a decision |
| **`HeatmapCell.vci` is 0–1 where every other VCI is 0–100** | Hard Rule 5's suppression threshold (`< 40`) is written on the 0–100 scale, so a `vci < 40` check against cell values would mark **every cell** suppressible. Nothing reads it today, so no live bug — reconciling the scales is a scoring change (Hard Rule 3) |
| **`beams-background.tsx`** | Pre-existing decorative canvas animation on `/login`, never reviewed against design-system §7's reduced-motion rule |
| **No categorical chart palette** | Carried debt behind OD-20 above: a surface needing to distinguish entities by colour must raise a decision, not generate hues |

---

## Standing constraint on all of it

Not one verified source in the language research concerns B2B SaaS privacy
reports. The evidence is UK statutory audit, internal audit, US securities
prospectuses, US intelligence analysis, UPL doctrine and cybersecurity ratings.
**Every application is analogical and must be stated as such** — including in any
spec that cites it.

## Changelog

- 2.0 (2026-09-01): Trimmed to open items only. Removed the completed UI-migration
  ledger (every route is on the component system; legacy CSS 2,562 → 276 lines),
  the guard inventory, and the closed-item history — all of it now lives in
  `logs/archive/2026-09/SESSION-REPORT-2026-09-01.md`. Added §1 "can be done now"
  at the top, because the previous version opened with what was blocked and buried
  what was actionable.
- 1.0 (2026-09-01): Created, merging `blocked-work.md` and `ui-migration-status.md`.
