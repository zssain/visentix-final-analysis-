# Plans — which document is authoritative for what

Ten plan documents accumulated here, which is the problem truth reconciliation
just fixed at the repo root: when several documents could answer the same
question, none of them does. This index says which one is authoritative for
what, and marks the ones that are now history.

## Live

| Document | Authoritative for | Status |
|---|---|---|
| **`open-decisions.md`** | Every decision awaiting a human. **The register — if a decision is not here, it does not exist** | Live · 13 open, 4 awaiting ratification |
| **`blocked-work.md`** | Everything stopped on a decision or dependency, split by who unblocks it | Live |
| **`route-and-surface-plan.md`** | Routes, screen splits, missing surfaces, **and background-task policy (§D2)** | Live · supersedes standardization-plan W3 |
| **`ui-migration-status.md`** | Which screens are on the component system and which are not | Live · 10 routes remaining |
| **`research-to-plan.md`** | What the language research changed, requires, forbids, and did **not** settle | Live |
| **`mock-tracker.md`** | Every mock in the product; the badge on each surface names its row here | Live · guarded by `check_mocks.py` |
| **`version-ladder.md`** | What ships in which version | Live |

## Superseded or complete

| Document | Why it is still here |
|---|---|
| `standardization-plan.md` | W1 (truth) and W6 (mock badges) **done**; W3 **superseded** by `route-and-surface-plan.md`; W4/W5 (component system, motion) largely done — see `ui-migration-status.md`; **W2 (naming contract) is the only part not started**. Kept as the record of why this work began |
| `mvp-completion-plan.md` | Predates the current sequencing. Its Workstream A (mocks) is now driven by `mock-tracker.md` |
| `full-app-roadmap.md` | Long-horizon feature view; not a work queue |

## Reading order for someone new

1. `open-decisions.md` — what is undecided
2. `blocked-work.md` — what that blocks
3. `route-and-surface-plan.md` — where the product is going
4. `ui-migration-status.md` — how far the rebuild got

## The one rule

**A decision goes in `open-decisions.md`, not in a plan.** Two expert-owned
decisions once sat in memos at the repo root for five weeks because writing the
memo felt like recording the decision. It was not (L-018).
