# Open Decisions (OD) Register

**Version:** 1.0 · 2026-07-16
**Authority:** the live register of product/content decisions that block MVP completion. Each OD has a recommendation to unblock, an owner, and a status. When an OD is decided, set Status = **Decided** with the date and the outcome, and reflect it in the feature spec(s) it governs. `mvp-completion-plan.md` Workstream C references this file.

**Status values:** **Open** (undecided) · **Recommended** (a recommendation is on the table, awaiting sign-off) · **Decided** (outcome recorded; propagate to specs).

| ID | Decision needed | Recommendation to unblock | Owner | Status | Governs |
|---|---|---|---|---|---|
| OD-01 | Framework Crosswalk copy | Approve **descriptive-only** language ("relates to CCPA §1798.120"); ship the shell now, copy later | Product | Recommended | F13 (shell shipped on mock citations), F05 |
| OD-02 | Reader-register names | **Executive / Practitioner / Plain-language**; ship flag-gated behind a feature flag | Product | Recommended | F05 (ExecutiveSummary reader toggle) |
| OD-03 | Advisor-hero-on-mobile default | Approve with the two specced mitigations (thumb-tap switch, full-screen lineage sheet) | Product | Recommended | F05, design-system §3 |
| OD-04 | Real SME names in attribution | Keep house persona **"The Visentix Privacy Desk"** for MVP; revisit at first paying client | SME team | Recommended | F06, design-system DDR-003 |
| OD-05 | Low-confidence cohort `n` | Confirm **n = 10** as `LOW_CONFIDENCE_COHORT_N` (conservative vs VICBNF <20 caution band) | Data | Recommended | design-system §2, intelligence-logic §8 |

## How an OD closes
1. Owner approves the recommendation (in Teams, per our feedback method).
2. Set Status = **Decided (YYYY-MM-DD)** here with the chosen outcome.
3. Update every spec in the **Governs** column, and remove any flag-gating / placeholder the recommendation introduced.
4. Record one line in `logs/decision-log.md`.

## Changelog
- 1.0 (2026-07-16): Promoted the OD table out of `mvp-completion-plan.md` Workstream C into a standalone register with an explicit Status column and a close-out procedure, so decided/undecided state is tracked rather than static.
