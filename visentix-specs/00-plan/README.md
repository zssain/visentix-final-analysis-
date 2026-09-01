# Plans — which document is authoritative for what

Eleven plan documents once accumulated here, which is the same failure truth
reconciliation fixed at the repo root: when several documents could answer the
same question, none of them does. There are now seven, each authoritative for
one thing.

## Live

| Document | Authoritative for |
|---|---|
| **`open-decisions.md`** | Every decision awaiting a human. **The register — if a decision is not here, it does not exist** |
| **`remaining-work.md`** | Everything left to build, and who unblocks each item. **Open items only** — nothing completed is kept, so its length tracks what is actually outstanding |
| **`route-and-surface-plan.md`** | Routes, screen splits, missing surfaces, and background-task policy (§D2) |
| **`research-to-plan.md`** | What the language research changed, requires, forbids, and did **not** settle |
| **`mock-tracker.md`** | Every mock in the product; the badge on each surface names its row here. Guarded by `check_mocks.py` |
| **`version-ladder.md`** | Which surface ships with which product version |
| **`full-app-roadmap.md`** | Long-horizon view: MVP → four commercial products. Not a work queue |

## Not a plan, but read it first

`logs/archive/2026-09/SESSION-REPORT-2026-09-01.md` — what was built on
`feat/shadcn-ui-system`, the bug pattern it kept finding, and the three method
notes that came out of it. A dated record, not a live list.

## Reading order for someone new

1. `open-decisions.md` — what is undecided
2. `remaining-work.md` — what that blocks, and what is merely queued
3. `route-and-surface-plan.md` — where the product is going

## Retired

`standardization-plan.md`, `mvp-completion-plan.md`, `blocked-work.md` and
`ui-migration-status.md` were deleted on 2026-09-01: the first two were
superseded, the last two are folded into `remaining-work.md`. Git history keeps
them (`git log --diff-filter=D --name-only`).

## The one rule

**A decision goes in `open-decisions.md`, not in a plan.** Two expert-owned
decisions once sat in memos at the repo root for five weeks because writing the
memo felt like recording the decision. It was not (L-018).
