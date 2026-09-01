# Archived records

**A dated record was true on its date. It is never authoritative afterwards.**

Everything here is filed by the month it was written. These files are kept
because they are evidence of what was known and decided at the time — not
because they describe how the system works now. For that, read
`visentix-specs/` (standing truth) and `AGENTS.md` (generated from it).

Do not "update" a file in here. If its content still matters, the current
version of that truth belongs in a spec; if a decision in it is still open, it
belongs in `visentix-specs/00-plan/open-decisions.md`.

## What was archived here on 2026-08-31, and why

Workstream 1 classified the 23 markdown files that had accumulated at the repo
root. The problem was not volume — it was that four kinds of document looked
identical sitting next to each other, so a superseded readiness report and a
live expert-owned decision were indistinguishable.

| Class | Home |
|---|---|
| Standing truth — rules that govern the build | `visentix-specs/`, `AGENTS.md` |
| Ledger — append-only history | `logs/decision-log.md`, `04-lessons/`, `00-plan/open-decisions.md` |
| **Dated record — true on its date only** | **`logs/archive/YYYY-MM/`** |
| Runbook — living operational procedure | `docs/runbooks/` |

Enforced by `scripts/check_docs_layout.py`.

### The decision memos

Four `DECISION-NEEDED` / DRAFT memos were sitting at the root. Two had since
been absorbed and are archived as their source record:

- `2026-08/DECISION-NEEDED-F005-PRESENCE-PROXY.md` → became OD-10, OD-11, OD-12
- `2026-07/F05-RELATED-OBLIGATIONS-DRAFT.md` → shipped into F05

**Two had not been absorbed, and were invisible to anyone reading the OD
register.** They are now OD-21 and OD-22:

- `2026-07/DECISION-NEEDED.md` — the rehearsal diagnosis had two independent
  causes. The segmentation half shipped; the **calibration half never did**
  (OD-21).
- `2026-07/DECISION-NEEDED-F07-CRAWL.md` — 22 SaaS crawl targets, **never
  approved and never seeded**, so the benchmark corpus stayed narrow (OD-22).

Reviewing the half that *did* ship surfaced OD-23: a threshold its own memo
marked "needs expert confirmation" is live in the decomposer with that caveat
dropped.

## Links inside archived files are not repaired

An archived record links to where things were **when it was written**. Several
files here point at repo-root paths that moved during this reorganisation.
Those links are left broken on purpose: repairing them would edit a record of
what was true on its date, which is the one thing this directory exists to
preserve. Use the table above to find the current home of anything referenced.
