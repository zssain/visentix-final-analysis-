# Standardization Plan — Truth, Naming, Routes

**Date:** 2026-08-31 · **Status:** proposed, awaiting go-ahead
**Decisions taken by owner:** archive-and-guard the docs · identifiers are never labels · routes may be renamed with redirects · one consistent component system · purposeful motion, including numbers that count to their value · mock data badged in the UI

Every problem below is a rule that **already existed and was not enforced**. So each workstream ends in a **guard**, not a document. A document that describes the rule is what we already have, and it is what drifted.

---

## The three findings

### A. The truth model rotted once already
[`../../logs/archive/2026-07/DEV_HANDOFF-docs-restructure.md`](../../logs/archive/2026-07/DEV_HANDOFF-docs-restructure.md) (2026-07-15) made `visentix-specs/` the single source of truth, archived 20 old docs, and made `AGENTS.md` compiled rather than hand-written so it could not drift.

Since then **23 root-level docs have accumulated** with no rule about which wins. Three are the same document at different moments (`../../logs/archive/2026-07/LAUNCH-READINESS.md`, `../../logs/archive/2026-07/LAUNCH-READINESS-v2.md`, `../../logs/archive/2026-07/PILOT-READINESS.md`). None of the dated audits is marked as *not* standing truth, so a reader cannot tell a July snapshot from a current rule. **I added one of these myself last turn** — which is the point: nothing stopped me.

### B. "Identifiers are not labels" is prose, not a guard
DDR-011 says machinery stays on demand. It is not testable. That is precisely why bare UUIDs were removed from the dashboard and the report ribbon and then **reappeared in the workbench rewrite two turns later**. There is also no server-side answer to "what do you call this thing", so every screen improvises one.

### C. UI inconsistency is mechanical, and measurable
**522 inline `style={{…}}` objects against 758 `className` uses.** Every screen re-declares its own padding, font size and color inline rather than composing from the token layer — `admin/Console.tsx` alone carries 87. That is the whole reason the app looks like several products: there is a design system in `index.css` and most screens route around it.

Two useful facts: **`motion` v12 is already a dependency and entirely unused**, so animation costs no new package; and there is no Tailwind, Radix or cva in the project, so adopting shadcn wholesale would mean a Tailwind migration across 522 inline styles — the philosophy is worth taking, the toolchain is not.

### D. Mock data is invisible to anyone looking at the app
The mock tracker lists **4 live mocks** (M-18, M-25, M-27, M-28) and three `mockData.ts` modules still ship to `/crosswalk`, `/trust` and `/vendors`. AGENTS.md rule 8 requires registering them; nothing requires **showing** them. A viewer cannot tell a real trust metric from a placeholder, which is the "status that lies" problem `how-we-write-specs.md` warns about — moved from the spec into the product.

### E. Route drift is measurable today

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
2. Move ~18 dated records to `logs/archive/2026-08/`. Root keeps: `README.md`, `AGENTS.md`, `../../visentix-specs/00-plan/standardization-plan.md` (until done), plus the four directories.
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

## Workstream 4 — One component system

**Goal:** the app looks like one product, and a new screen composes rather than improvises.

**shadcn's philosophy, not its toolchain.** What we take: **own your components** (they live in our repo, not behind a package), **variant-driven APIs** instead of stringly-typed class soup, **composable primitives with slots**, and a single token layer everything reads from. What we do not take: Tailwind. Migrating 522 inline styles to utility classes is a rewrite with no user-visible payoff, and our tokens already exist in `index.css`.

**Steps**
1. Build `web/src/components/ui/`: `Button` · `Badge` · `Card` · `Field` · `Tabs` · `Dialog` · `Tooltip` · `Table` · `EmptyState` · `StatTile`. Variant-driven — `<Button variant="primary" size="sm">`, not `className="btn btn-primary btn-sm"`.
2. Every component reads tokens only. **No component may define a color.**
3. Migrate screens in dependency order — shared furniture, then the report, then each route. Each migration deletes inline styles rather than adding a wrapper around them.
4. **Guard:** a lint rule capping inline `style={{}}` per file (ratchet: the count may fall, never rise), and a test that no component file contains a raw hex outside the token layer.

> **Open decision — accessibility primitives.** `Dialog`, `Tooltip` and dropdowns are where hand-rolled a11y usually fails (focus traps, escape handling, ARIA wiring). Adopting **`@radix-ui/react-*`** for those three would be one new dependency and is the one place I would take a library. Flagging rather than assuming.

**Done when:** every route renders from `components/ui`, the inline-style count is ratcheting down, and no screen defines its own color.

---

## Workstream 5 — Motion with a purpose

> ⚠️ **This amends a stated brand principle.** design-system §1 reads: *"legal-and-regulator 'premium' is confident stillness plus evidence everywhere. Motion exists only to reveal evidence."* Count-up numbers are decorative motion under that rule. The owner has asked for them, so the principle becomes: **motion reveals evidence or arrival — never decoration, never anything that implies a change that did not happen.** Recorded as a DDR so the reversal is deliberate and attributable, not drift.

**What animates**
- **Numbers count to their value on first reveal** — score dial, stat tiles, exposure counts. From a neutral origin to the true figure, once.
- **Charts draw in** — the benchmark meter fills, sparklines trace, heat cells fade up in sequence.
- **Surfaces settle** — drawers, dialogs and the job tracker ease rather than snap.

**Four constraints, all binding**
1. **Never in the PDF.** `ScoreDial` is explicitly "pure static SVG… deterministic for the Playwright PDF". Animation is interactive-only and must not touch a rendered byte — **OD-18 already has PDF determinism failing intermittently**; nothing here may make that worse.
2. **`prefers-reduced-motion` lands instantly** on the final value (design-system §5 quality floor).
3. **The final value is in the DOM from the first frame.** Screen readers, tests and copy-paste see the true number; the animation is presentation over settled content. A count-up that only *ends* correct is unreadable to assistive tech.
4. **Animate arrival, never transition between two real values.** A score easing from 62 to 71 reads as improvement that did not occur. Deltas stay discrete.

`motion` v12 is already installed and unused — no new dependency.

**Guard:** a test asserting each animated component renders its final value immediately under `prefers-reduced-motion` and in the test environment, plus the existing PDF byte-identity tests.

---

## Workstream 6 — Mock data wears a badge

**Goal:** nobody — customer, SME, or us in a demo — can mistake placeholder data for real intelligence.

**The rule:** any value not sourced from the live pipeline renders inside a surface carrying a visible **`MOCK`** badge naming its tracker id. This is Hard Rule 7 ("never fake data") extended from *don't fabricate* to *label what is provisional*.

**Steps**
1. `<MockBadge id="M-27" />` — gold, register-appropriate, with a tooltip stating what is placeholder and what it will be replaced by.
2. Apply at the **surface** level (card/section/page), not per number — a badge on every figure is noise; a badge on the panel is a fact.
3. Cover the live mocks: **M-18** (F12 Benchmark Spotlight), **M-25** (F13 Crosswalk), **M-27** (F15 Trust metrics), **M-28** (F16 Vendors).
4. `/trust` is **public** — a mock badge there is a trust statement, so its wording needs sign-off before it ships publicly.
5. **Guard:** a test importing every `mockData.ts` and asserting its consuming route renders a `MockBadge`; adding a mock module without a badge fails CI. Removing the mock removes the badge — the tracker and the UI stay in step.

**Done when:** every live mock is visibly badged, and a new mock cannot reach a screen unbadged.

---

## Sequence and cost

| # | Workstream | Depends on | Rough size |
|---|---|---|---|
| 1 | Truth reconciliation | — | Half a day. Mostly classification; the guard is small |
| 2 | Naming contract | — | 1–2 days. Backend display fields are the bulk |
| 3 | Route contract | Benefits from 1 (spec map generated) | 1–2 days. Renames are mechanical; the registry is the work |
| 4 | Component system | 3 (routes define the surfaces) | 3–4 days. The largest piece; migration is per-screen and can ship incrementally |
| 5 | Motion | 4 (animates the new primitives) | Half a day once 4 exists; days if bolted onto inline styles |
| 6 | Mock badges | 4 (uses the Badge primitive) | Half a day |

**Recommended order: 1 → 3 → 6 → 4 → 5.**

Workstream 1 is cheap and makes everything after it auditable. **3 before 4** because routes define which surfaces exist — otherwise screens get restyled twice. **6 early and cheap**, because unbadged mock data is the most misleading thing currently on screen and a badge does not need the full component system. **5 last**, because animating primitives that already exist is half a day, while animating 522 inline styles is a week.

Workstream 2 (naming) folds naturally into 4 — both rewrite the same list surfaces — so in practice: **1 → 3 → 6 → (4 + 2 together) → 5.**

---

## What this plan deliberately does not do

- **No formula, weight, threshold, band or finding-code changes.** This is structure and language only.
- **No payload restructuring.** As with the report's six-part regrouping, presentation changes must not alter stored snapshots (Hard Rule 6).
- **No Tailwind migration.** The shadcn philosophy is adopted; the toolchain is not.
- **No motion in any PDF path.** Interactive surfaces only.
- **Does not resolve the open decisions** OD-13…OD-19, or the byte-identity defect (**OD-18**), which remains the most serious outstanding item and is unrelated to this work.
