# Standardization Plan — Truth, Naming, Routes

**Date:** 2026-08-31 · **Status:** proposed, awaiting go-ahead
**Decisions taken by owner:** archive-and-guard the docs · identifiers are never labels · routes may be renamed with redirects

Every problem below is a rule that **already existed and was not enforced**. So each workstream ends in a **guard**, not a document. A document that describes the rule is what we already have, and it is what drifted.

---

## The three findings

### A. The truth model rotted once already
[`DEV_HANDOFF-docs-restructure.md`](DEV_HANDOFF-docs-restructure.md) (2026-07-15) made `visentix-specs/` the single source of truth, archived 20 old docs, and made `AGENTS.md` compiled rather than hand-written so it could not drift.

Since then **23 root-level docs have accumulated** with no rule about which wins. Three are the same document at different moments (`LAUNCH-READINESS.md`, `LAUNCH-READINESS-v2.md`, `PILOT-READINESS.md`). None of the dated audits is marked as *not* standing truth, so a reader cannot tell a July snapshot from a current rule. **I added one of these myself last turn** — which is the point: nothing stopped me.

### B. "Identifiers are not labels" is prose, not a guard
DDR-011 says machinery stays on demand. It is not testable. That is precisely why bare UUIDs were removed from the dashboard and the report ribbon and then **reappeared in the workbench rewrite two turns later**. There is also no server-side answer to "what do you call this thing", so every screen improvises one.

### C. Route drift is measurable today

| Drift | Evidence |
|---|---|
| Title mismatch | design-system maps `/bulk` → "Bulk Analysis"; code renders "Bulk Screening" |
| Duplicate nav entry | `/partner` appears twice — "Partner Workspace" and "Partner" |
| Dead route | `/intake/:assessmentId` registered; nothing has navigated to it since the intake rewrite |
| Unmapped routes | `/login`, `/privacy`, `/terms`, `/`, `/unauthorized` absent from the route map |
| No primary action | 6 of 13 routes render no `actions=` slot: Intake, Codex, Methodology, Quarterly, Rewrite, Legal |
| Invisible role rules | 7 routes are feature-flag masked **and** role-gated; the two conditions live only in `App.tsx` |

DDR-008 already requires nav ↔ eyebrow ↔ title to agree. Unenforced, so it drifted.

---

## Workstream 1 — Truth reconciliation

**Goal:** a reader (or agent) can tell in one glance whether a document is a rule, a ledger, a dated record, or dead.

**Four categories, and every file lands in exactly one:**

| Category | What it means | Where it lives |
|---|---|---|
| **Standing truth** | Rules that govern the build. Change requires the spec-update workflow | `visentix-specs/`, `AGENTS.md` (generated) |
| **Ledger** | Append-only history — never rewritten | `logs/decision-log.md`, `04-lessons/`, `00-plan/open-decisions.md` |
| **Dated record** | True on its date, never authoritative afterwards | `logs/archive/YYYY-MM/` |
| **Runbook** | Living operational procedure, not product truth | `docs/runbooks/` |

**Steps**
1. Classify all 24 root docs + 38 `docs/` files. Each dated record gets a one-line header stating its date and that it is a record, not a rule.
2. Move ~18 dated records to `logs/archive/2026-08/`. Root keeps: `README.md`, `AGENTS.md`, `STANDARDIZATION-PLAN.md` (until done), plus the four directories.
3. Move deploy/pilot procedures to `docs/runbooks/`.
4. Extract anything still *true* from a dated record into the governing spec **before** archiving it — with the spec-update workflow, so it gets a changelog entry.
5. **Guard:** `scripts/check_docs_layout.py` in CI — fails on a new root-level `.md` outside the allowlist, and on a dated record with no status header.

**Done when:** root has ≤5 files, every doc is classified, and adding a stray root doc fails CI.

---

## Workstream 2 — Naming contract

**Goal:** no screen ever shows a reader an identifier as the name of something.

**The rule (promoted to design-system, testable):**
> An identifier may never be the visible label of an entity. Every entity a surface can display resolves to a **display name** supplied by the server. Identifiers remain reachable in one gesture — hover, detail header, Traceability, copy control — and are never removed from the payload.

**Steps**
1. Define a `DisplayName` contract per entity: **assessment** → organization + submitted source + date; **snapshot** → frozen date + status; **finding** → code + Codex title; **clause** → section reference + excerpt; **exemplar** → domain + maturity note; **job** → what was submitted.
2. Backend: every list/detail endpoint returns the display fields alongside ids, read-only from existing tables, and **degrades to no labels rather than failing the request** (the pattern already shipped on `GET /review/queue`).
3. Frontend: a small `<EntityLabel>` that takes name + id and renders name-first with the id on demand. Replace ad-hoc renderings.
4. **Guard:** a vitest that renders each list surface and fails if visible text matches an id shape (UUID, `S-####`, bare hex ≥8) outside an allowlisted "reference" slot.

**Known surfaces to fix:** admin Console batch results · monitoring change feed · partner client cards · bulk rows · quarterly approve toasts. (The SME queue is already done.)

**Done when:** the id-shape test passes across every list surface, and adding a bare id to a label fails CI.

---

## Workstream 3 — Route & workflow contract

**Goal:** every route states what it is for, who it is for, and what you can do on it — and the code cannot drift from that statement.

**One registry, `web/src/routes/registry.ts`,** declaring per route: path · nav label · eyebrow · title · one-line purpose · allowed roles · feature flag · primary action · nav group. `App.tsx`, the sidebar and every `PageHeader` read from it. The design-system route map is generated from it, so the two can never disagree.

**Proposed renames** (old paths redirect permanently; nothing breaks):

| Today | Proposed | Why |
|---|---|---|
| `/assessments` | `/monitor` | The nav says Monitor, the title says Monitor, only the URL says assessments |
| `/review` | `/workbench` | Same mismatch; "review" also collides with the customer's report review |
| `/bulk` | `/screening` | Code already calls it Bulk **Screening**; the spec says Bulk Analysis |
| `/intake/:assessmentId` | *removed* | Dead since intake became a background job |

Unchanged: `/intake`, `/reports/:id`, `/codex`, `/methodology`, `/quarterly`, `/trust`, `/crosswalk`, `/rewrite`, `/vendors`, `/partner`, `/admin`, `/privacy`, `/terms`, `/login`.

**Every route gets a primary action.** The six screens with no `actions=` slot each get one obvious next step — Intake → *Submit a notice*; Codex → *Search the catalog*; Methodology → *Download the method note*; Quarterly → *Download the issue*; Rewrite → *Start a rewrite*.

**Steps**
1. Build the registry; drive routes, nav and headers from it.
2. Apply renames with permanent redirects; delete the dead route; de-duplicate the Partner nav entry.
3. Generate the design-system route map from the registry.
4. **Guard:** a test asserting every registered route appears in the registry, nav label == eyebrow == title stem (DDR-008), each route declares a primary action, and no route is registered twice.

**Done when:** adding a route without registering it fails CI, and the spec's route map is generated rather than typed.

---

## Sequence and cost

| # | Workstream | Depends on | Rough size |
|---|---|---|---|
| 1 | Truth reconciliation | — | Half a day. Mostly classification; the guard is small |
| 2 | Naming contract | — | 1–2 days. Backend display fields are the bulk |
| 3 | Route contract | Benefits from 1 (spec map generated) | 1–2 days. Renames are mechanical; the registry is the work |

**Recommended order: 1 → 3 → 2.** Workstream 1 is cheap and makes the other two auditable. Workstream 3 defines the surfaces that Workstream 2 then has to label, so doing it first avoids labelling a screen twice.

They are independent enough to run in any order if you would rather see the UI change first.

---

## What this plan deliberately does not do

- **No formula, weight, threshold, band or finding-code changes.** This is structure and language only.
- **No payload restructuring.** As with the report's six-part regrouping, presentation changes must not alter stored snapshots (Hard Rule 6).
- **Does not resolve the open decisions** OD-13…OD-19, or the byte-identity defect (**OD-18**), which remains the most serious outstanding item and is unrelated to this work.
