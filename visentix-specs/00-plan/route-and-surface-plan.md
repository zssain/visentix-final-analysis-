# Route & Surface Plan

**Version:** 1.0 · 2026-08-31 · **Status:** proposed — owner decisions marked ⬥
**Supersedes** the route half of `standardization-plan.md` Workstream 3.
**Governing spec:** `01-foundation/design-system.md` §6.

## The naming rule

> **A route names the job the reader came to do, in their words.**

Three failure modes it rules out, each of which is live today:

1. **Naming our internal process, not their job.** `/intake` is what *we* do with a notice; the reader came to *start an assessment*.
2. **Naming a capability we do not deliver.** `/monitor` was adopted this session and reverted the same session: the screen lists assessments, while the actual monitoring feature renders nothing whenever its three endpoints are unpopulated — which is structurally always, in the pilot.
3. **Naming it in house vocabulary.** `/codex` was a coinage on a public page — the same class as VCI and PGMS, removed under the acronym rule days earlier.

---

## A. Audit — what each screen actually does

Endpoints observed in the source, not inferred from the name.

| Route | Calls | Actual job | Verdict |
|---|---|---|---|
| `/` | — | Redirects by role; **renders `CustomerDashboard` for a customer** | ⚠ **duplicate of `/assessments`** |
| `/assessments` | `/assessments/`, `/findings/dashboard-stats` | List assessments + overall standing | ✅ correct (reverted from `/monitor`) |
| `/intake` | `/assessments/async`, `/config/intake-options` | Submit a notice, hand off to a background job | ⬥ rename — names our process |
| `/workbench` | `/review/queue`, `/review/{id}/findings`, `/review/{id}/approve`, `/review/exemplars`, `/review/exemplar/{id}/clean`, `/review/exemplar/{id}/approve`, **`/admin/training-stats`** | **Three jobs in one screen** | ⬥ split |
| `/rewrite` | **`/assessments/{id}/clauses`**, `/assessments/{id}/clauses/{cid}/rewrite` | Lists extracted clauses, then rewrites one | ⬥ **already half the missing OD-19 surface** |
| `/screening` | `/bulk/jobs*` | Draft-grade triage of many notices | ✅ correct |
| `/vendors` | **none** | Pure mock (M-28) | ✅ name fine; capability absent |
| `/partner` | `/partner/workspaces`, `/partner/branding`, `/partner/api-keys`, `/partner/industries` | **Four jobs**: clients, branding, keys, cohort config | ⬥ split |
| `/admin` | `/admin/training-stats`, `/admin/trigger-assessment`, `/review/gate-mode` | **Four jobs**: health, policy, batch ops, quality stats | ⬥ split |
| `/reports/:id` | `/reports/{id}`, `/reports/{id}/pdf` | The forwarded artifact | ✅ correct |
| `/finding-codes` | `/findings/codex` | Code definitions | ✅ correct (renamed) |
| `/methodology`, `/crosswalk`, `/quarterly`, `/trust` | — / real | Reference + editorial | ✅ correct |

**`crosswalk` is kept deliberately:** unlike `codex`, it is standard GRC vocabulary (NIST publishes "crosswalks"), so it is the reader's word, not ours.

---

## B. Screens doing more than one job

Splitting is not tidiness. Each of these has a concrete cost today.

### B1. `/workbench` → three jobs ⬥
Reviewing findings and de-identifying exemplars are different tasks, done at different times, gated by different rules. They share a screen only because both are "SME work". It also pulls `/admin/training-stats` — **the same call the Admin Console makes**, so one number has two homes and can disagree.

**Proposed:** `/review/findings` · `/review/exemplars` · training-stats removed from here (it belongs in B3).

### B2. `/partner` → four jobs ⬥
Client list, branding, API keys and cohort config on one screen. API keys in particular are a credential surface sitting inside a browsing screen.

**Proposed:** `/partner/clients` (the work) · `/partner/settings` (branding, keys, industries).

### B3. `/admin` → four jobs ⬥
Health, gate-mode policy, batch operations, and training-label quality. The first three are operations; the fourth is measurement, and it is **the natural home for the F17 evaluation harness, which has a full backend and no UI at all** (§C4).

**Proposed:** `/admin` (health + operations) · `/admin/policy` (gate mode) · `/admin/quality` (training labels + F17 precision panel).

### B4. `/` duplicates `/assessments`
For a customer these render the identical component. Keep `/` as a redirect only; it should never render a screen of its own.

---

## C. Capabilities with no surface

### C1. Continuous monitoring — endpoints exist, nothing renders
`/api/monitoring/{trend,events,alerts,deliveries}` are all live. `MonitoringHero` returns `null` unless one of three independent blocks populates, and in the pilot none does. **The word `/monitor` is now reserved for this and deliberately unused.** Until it can populate, no route should claim it.

### C2. Clause decomposition explorer — **OD-19, and half-solved already**
F01 AC-1/AC-4 lost their surface when Intake became single-column. But **`/rewrite` already calls `/assessments/{id}/clauses`** — it lists extracted clauses in order to rewrite one. The explorer does not need building from nothing; it needs the existing screen widened.

**Proposed:** `/clauses/:assessmentId` — "Clause Explorer": the extracted clauses with their lineage and `is_noise` flags, **with rewrite as an action on a clause** rather than its own destination. This closes OD-19 and removes a route rather than adding one.

### C3. Assessment history — specced, no endpoint, no surface
F07 AC-9/AC-10. Nothing serves it and nothing shows it. Belongs on `/assessments` (per-org timeline), not a route of its own.

### C4. F17 evaluation harness — full backend, **no UI**
`app/routers/eval.py`'s own docstring names "the Admin finding-precision panel". That panel does not exist. Gold labels can be round-tripped by CSV only. → `/admin/quality` (B3).

### C5. Dispute / appeal path — nothing, anywhere
From the language research: published ratings vendors operate a named dispute process open **even to non-customers**, with published resolution times. We have no endpoint, no screen, and no process. This is the one item here that is **staffing before it is code**.

### C6. Action plans with owner + target date
Every assurance-report structure in the research carries them; our recommendations name no owner and are due never. Needs a schema decision first (does assignment exist at all?), so it is not a route question yet.

### C7. `feed` router — correctly has no UI
`/feed/white-label` is a partner **machine** API with key auth. Listed here so a future audit does not mistake it for a missing screen.

---

## D. Proposed route table

⬥ = needs an owner decision. Everything else is mechanical.

| Route | Nav label | Title | Job |
|---|---|---|---|
| `/` | — | — | Redirect by role only |
| `/assessments` | Assessments | Your Assessments | See standing + every assessment (+ history, C3) |
| `/assess` ⬥ | New Assessment | Submit a Privacy Notice | Start one *(was `/intake`)* |
| `/clauses/:id` ⬥ | — | Clause Explorer | What we extracted, with lineage; rewrite from here *(absorbs `/rewrite`)* |
| `/reports/:id` | — | Report | The forwarded artifact |
| `/review/findings` ⬥ | Review Findings | Findings Review | Approve/edit/dismiss findings |
| `/review/exemplars` ⬥ | De-identify | Exemplar De-identification | Clean + approve exemplars |
| `/screening` | Screening | Bulk Screening | Draft-grade triage |
| `/vendors` | Vendors | Vendor Due Diligence | Screen a vendor *(mock)* |
| `/finding-codes` | Finding Codes | Finding Code Definitions | Look up a code |
| `/methodology` | Methodology | How Visentix Works | Understand the method |
| `/crosswalk` | Crosswalk | Framework Crosswalk | Map to external frameworks |
| `/quarterly` | Quarterly | Quarterly Intelligence Report | Read the quarter |
| `/trust` | Trust Center | Trust Center | Public trust statement |
| `/admin` | Admin | Admin Console | Health + operations |
| `/admin/policy` ⬥ | — | Gate Mode Policy | Who sees drafts |
| `/admin/quality` ⬥ | — | Label Quality | Training labels + F17 precision |
| `/partner/clients` ⬥ | Partner | Partner Workspace | Client list + delivery |
| `/partner/settings` ⬥ | — | Partner Settings | Branding, API keys, cohorts |
| `/monitor` | — | — | **Reserved, unbuilt** (C1) |

**Every renamed path keeps a permanent redirect.** A bookmark or a link inside an already-delivered report must not 404 because we renamed a screen. `/intake/:assessmentId` is the one exception: deleted, not redirected — it has had no caller since intake became a background job.

### Three still-open name conflicts ⬥
Spec §6, the code, and the nav each carry a different name:

| Route | Spec §6 | Code | Recommendation |
|---|---|---|---|
| `/rewrite` | Trust Language Studio | Illustrative Clause Rewrite | **"Illustrative Rewrite"** — "illustrative" is load-bearing: it stops a reader thinking we drafted their notice, which matters while OD-16 is open |
| `/partner` | Partner Portal | Partner Workspace | **"Partner Workspace"** — you do work there |
| `/screening` | Bulk Analysis | Bulk Screening | **"Bulk Screening"** — the output is explicitly draft-grade. "Analysis" claims the rigour of a full assessment |

---

## D2. Background work — one pattern, not three

### The problem

There are **three unrelated job concepts** in the product today, and none of them can be reused for a fourth thing:

| System | Table | Drives | Reusable? |
|---|---|---|---|
| Scheduled jobs (`jobs/framework.py`) | `job_run` | cron: monitor_notices, pull_regulators, refresh_benchmarks | No — cron-shaped, no user waiting |
| Intake jobs (`intake/jobs.py`) | `assessment_job` | one thing: intake | No — columns are intake-shaped |
| Bulk jobs | `/bulk/jobs` | one thing: bulk screening | No |

Meanwhile **two user-triggered operations still block the HTTP request end to end**:

- `POST /admin/trigger-assessment` re-scores *every notice in an organization* inline. On a real org this is a long request that a proxy may cut before it finishes — and the user watches a disabled button the whole time.
- `POST /admin/quarterly` builds a quarterly snapshot inline, same shape.

Two more are slow but bounded, and worth queueing rather than blocking: **report PDF render** (WeasyPrint, and OD-18 already shows it is not fast or deterministic) and **clause rewrite** (an LLM round-trip).

### The rule

> **If an operation can outlive a reader's patience, it hands off and reports back. There is one way to hand off, one place to watch it, and one vocabulary for its states.**

Intake already works this way and is the pattern to generalize — not to copy a fourth time.

### Backend

One additive migration puts a `kind` on `assessment_job` (`intake` | `reassessment` | `quarterly_build` | `report_pdf` | `rewrite`); `assessment_id` is already nullable, so a non-intake task simply leaves it null. `intake/jobs.py` generalizes to `app/services/tasks.py` — `create` · `set_stage` · `complete` · `fail` · `get` — and the async endpoints become thin wrappers that return a task id immediately.

`job_run` is **left alone**. Cron jobs have no user waiting on them, and merging the two would give a scheduled job a progress bar nobody is watching.

### Frontend

`IntakeJobsProvider` / `JobTracker` generalize to `TasksProvider` / `TaskTracker`: `track({ kind, label, poll })` accepts any operation. Same resume-on-mount, same backoff, same honest `still_running` after the wall-clock budget.

### The four rules that keep this from confusing people

1. **One tracker, one place.** Every background task appears in the same floating panel, bottom-right, whatever started it. A second progress affordance somewhere else is how a user loses track of what is running.
2. **The button says what will happen.** "Start — runs in the background", not "Run". A reader should never learn an operation was async by watching the page not change.
3. **The screen never traps you.** Handing off means you can navigate away immediately. Anything that must be watched was mis-classified and should have been synchronous.
4. **A finished task offers exactly one next action** — open the report, open the snapshot — and can be dismissed. A completed task that just sits there is noise.

### What stays synchronous

Sign-in, filter changes, gate-mode toggles, exemplar clean/approve, notification settings. These are sub-second, and putting a task card behind an instant action is its own kind of confusion.

---

## E. Sequence

| # | Work | Depends on | Size |
|---|---|---|---|
| 1 | Route guard: registry ↔ design-system §6 ↔ page titles must agree | registry (done) | ~2h |
| 2 | `/` stops rendering; redirect only | — | ~1h |
| 3 | Settle the three name conflicts ⬥ + update §6 | owner | ~1h |
| 4 | `/intake` → `/assess` ⬥ | 3 | ~2h |
| 5 | Split `/workbench` → `/review/{findings,exemplars}` ⬥; drop its duplicate training-stats call | 1 | ~half day |
| 6 | Split `/admin` ⬥; build `/admin/quality` over the existing F17 backend (C4) | 5 | ~1 day |
| 7 | `/clauses/:id` absorbing `/rewrite` ⬥ — closes **OD-19** | 4 | ~1 day |
| 8 | Split `/partner` ⬥ | — | ~half day |
| 9 | Assessment history (C3) — needs an endpoint first | — | ~1 day |

**Not sequenced:** C5 (dispute path — a process decision), C6 (action plans — a schema decision), C1 (monitoring — blocked on the data actually populating).

## What this plan will not do

- Rename `/crosswalk`, `/methodology`, `/quarterly`, `/trust`, `/vendors`, `/reports` — they already say what they do.
- Touch any score, formula, threshold, or finding code.
- Build a screen for `feed` (C7) — it is a machine API by design.
- Reuse the word "monitor" for anything until continuous monitoring can populate.
