# Blocked Work — what cannot proceed, and who unblocks it

**Version:** 1.0 · 2026-08-31
**Rule:** nothing on this list is "not done yet". Each item is stopped on a
specific decision or dependency, named here so it stays visible instead of
drifting into the background. When an item unblocks, delete it from this file
and put it in a plan.

---

## A. Blocked on the owner — naming and structure

Seven route decisions from `route-and-surface-plan.md` (⬥ items). They are
mechanical once decided; none is technically hard.

| # | Decision | Recommendation | Cost once decided |
|---|---|---|---|
| A1 | `/rewrite` name — spec says "Trust Language Studio", code says "Illustrative Clause Rewrite" | **"Illustrative Rewrite"** — "illustrative" is load-bearing while OD-16 is open: it stops a reader thinking we drafted their notice | ~1h |
| A2 | `/partner` name — "Partner Portal" vs "Partner Workspace" | **"Partner Workspace"** | ~15m |
| A3 | `/screening` name — "Bulk Analysis" vs "Bulk Screening" | **"Bulk Screening"** — the output is draft-grade; "Analysis" claims the rigour of a full assessment | ~15m |
| A4 | `/intake` → `/assess`? | Yes — "intake" names our process, not the reader's job | ~2h |
| A5 | Split `/workbench` → `/review/findings` + `/review/exemplars` | Yes — two tasks, different times, different gates; it also duplicates the Console's training-stats call | ~half day |
| A6 | Split `/admin` → `/admin` + `/admin/policy` + `/admin/quality` | Yes — and `/admin/quality` gives the F17 evaluation backend its missing UI | ~1 day |
| A7 | Split `/partner` → `/partner/clients` + `/partner/settings` | Yes — API keys are a credential surface inside a browsing screen | ~half day |
| A8 | `/clauses/:id` absorbing `/rewrite` | Yes — closes **OD-19** by removing a route rather than adding one | ~1 day |

---

## B. Blocked on the expert

Ordered by how much damage each does while open.

| OD | What is blocked | Why it matters now |
|---|---|---|
| **OD-23** | Confirming the decomposer's 12-word `list_fragment` bound | **An unconfirmed threshold is live.** Its own memo marked it "needs expert confirmation"; the code comment dropped the caveat. It decides which clauses are flagged `is_noise`, which feeds presence-count dimensions, which feed scores |
| **OD-18** | The PDF byte-identity guarantee | **The claim is already in print.** Two tests show it failing ~4–6 runs in 10 on an unmodified tree. Until it closes, byte-identity must not be cited to a customer or regulator |
| **OD-16** | Obligation modality (must vs should) | **No customer surface may render a "must".** The surviving legal test is "applying law to a specific party's facts" — which is what a "must" does in a per-customer report |
| **OD-14** | Dimension names + peer-position words | **No comparative word renders.** The research killed the one borrowable standard (ICD 203's likelihood lexicon, refuted 0-3), so there is nothing off-the-shelf left |
| **OD-21** | Presence-count saturation calibration | The half of the rehearsal diagnosis that never shipped. Sat outside the register for five weeks |
| **OD-15** | Risk-horizon taxonomy | No horizon label renders |
| **OD-10/11/12** | F-005 semantics, F-002 severity, Section 4 measure | Marked *Recommended*, awaiting ratification |
| **OD-17** (thresholds half) | Screen↔PDF band cut-points | Hard Rule 3 — score bands come only from `intelligence-logic.md` |

---

## C. Blocked on a product decision, not a technical one

| Item | The question | Source |
|---|---|---|
| **Action plans with owner + target date** | Does assignment exist in the product at all? Inventing an owner or a date to satisfy a format would break the honest-numbers rule | Language research — every assurance-report structure carries them; ours name no owner and are due never |
| **Dispute / appeal path** | Do we commit to a named process, open even to non-customers, with published resolution times? This is headcount and process before it is code | Language research — it is how a published score survives third-party scrutiny |
| **OD-22** — 22 SaaS crawl targets | Approve, amend, or reject. The crawler must not touch unapproved domains | Never approved, never seeded; one reason the corpus stayed narrow |
| **OD-20** — categorical chart palette | The supplied ramp is sequential (one hue). Nothing can tell entities apart by colour, and generating hues is forbidden | Raised while adopting the token set |

---

## D. Blocked on a dependency we own

| Item | Blocked on |
|---|---|
| **Migration 0049** (`assessment_job.kind`) | An out-of-band apply to the shared database. The file is written, registered in `APPLY_NOW` per the runner's own rule, and additive + idempotent — but `test_schema_migrations_rows_match_file_checksums` compares against the LIVE ledger, so it fails until applied. Applying to a shared DB is not a call to make unilaterally. **The two async endpoints cannot run until this lands.** |
| **Continuous monitoring UI** | The four `/api/monitoring/*` endpoints returning populated data. `MonitoringHero` is correct; it has nothing to draw. `/monitor` is reserved and deliberately unused until then |
| **Assessment history** (F07 AC-9/10) | No endpoint serves it |
| **Explorable heatmap cell** (F05 AC-13) | Specced, unbuilt — not blocked, just unqueued |
| **Source summary placement** | Currently at the head of the appendix. Whether a condensed form belongs in the Cover is **not settled by evidence** — the research found nothing on placement |

---

## E. Known-open guard debt

| Lesson | What is still missing |
|---|---|
| **L-012** | An assertion covering "no cohort ⇒ no percentile" |
| **L-011** | F07 AC-11…AC-14 |

---

## What is NOT on this list

Work that is merely unfinished, and needs no decision: the backend async
endpoints, the route guard, `/` redirect-only, the literal-colour lint, and the
eleven routes still on page-scoped CSS. Those are tracked in
`route-and-surface-plan.md` and `ui-migration-status.md`.
