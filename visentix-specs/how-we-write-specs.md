# How We Write Specs — The Playbook

**Version:** 1.0 · 2026-07-15
**What this is:** the standing method for creating and evolving every future spec — how ideas become documents, how we discuss them with developers, and (Part 4) a record of exactly how the current plan and spec repo were made, so the method survives the people who used it.

---

## Part 1 — The lifecycle of a spec

Every spec moves through five stages. The stage lives in the spec's `**Status:**` header (`proposed → approved → in-progress → shipped`), and nothing skips a stage.

### Stage 0 — The trigger
Specs are born from exactly four places, and each has an entry point:
1. **The plan** (`00-plan/`) says it's next — the normal case.
2. **Feedback** — a `feedback` issue was triaged as spec-change; the triage agent drafts the edit.
3. **A lesson** — the weekly audit found a pattern; the ledger demands a guard.
4. **An idea** graduated from `03-ideas/further-ideas.md` — someone decided its time has come.
No fifth door. "We just started building it" is not a trigger; it's a process bug.

### Stage 1 — Draft (anyone writes, AI helps)
Copy `02-features/_TEMPLATE.md`. Fill every section — writing "none" or "unknown, see open questions" is fine; leaving a section absent is not, because absence hides the unknown. Use an AI agent to draft freely (it's good at this — feed it the foundation docs and the trigger), but the human proposer owns every sentence before review.

**The bar for acceptance criteria** — the heart of any spec: each AC must be *checkable by someone who didn't write the code*. "AC-3: works well on mobile" fails the bar. "AC-3: at 375px the panes stack and the lineage drawer renders as a full-screen bottom sheet" passes. If you can't phrase the AC checkably, you don't understand the feature yet — which is precisely what drafting is for discovering.

### Stage 2 — The spec discussion (the one meeting we protect)
One conversation, all three seats present (engineers + expert), 30–45 minutes, spec read *before* the meeting, never during. Each seat has a fixed job:

- **The expert** answers: Is the content true? Does anything risk the guardrail or a hard rule? Is the language right for the audience? Would a skeptical regulator accept this framing?
- **The engineers** answer: Is it buildable as written? What does it *actually* touch (tables, routes, other features)? What's the test gate? What's the smallest honest version?
- **Everyone** answers: Does it contradict a foundation doc? (If yes — the foundation doc gets amended *in the same PR*, deliberately, or the feature changes. Silent contradiction is the one unforgivable outcome.)

Disagreements end one of three ways, recorded in the spec: a decision (changelog entry), an **open question with an owner and a date**, or a deliberate deferral to `03-ideas/`. Meetings that end with vague nods get repeated; meetings that end with recorded outcomes don't.

### Stage 3 — Approval
The spec PR merges under CODEOWNERS: expert approves content, engineer approves technical feasibility (both, for foundation files). On merge, `agents-sync` regenerates AGENTS.md — approval *is* deployment of the truth.

### Stage 4 — Implementation & closure
Engineers + AI agents build to the ACs (per `AGENTS.md`); the test gate must pass; commits carry the Fxx ID. When shipped: flip the Status, mark mocks `[REPLACED]`, close open questions or move them to the plan. A spec whose status lies is worse than no spec — the weekly audit checks for this drift.

## Part 2 — Working agreements

- **Small specs beat big ones.** If a spec has more than ~8 ACs, it's probably two features. Split before discussing.
- **Foundation changes are their own event.** A weight, a table, a token, a hard rule — these get their own PR, their own changelog entry, and both approvers, even when tiny. Foundation drift is how two-person teams lose their product.
- **One open-questions list per spec, each with an owner.** Ownerless questions are decorations.
- **The spec is the meeting notes.** We don't keep separate meeting minutes; the spec's changelog and open-questions sections *are* the record. (One-line judgment calls that don't belong in any spec go to `logs/decision-log.md`.)
- **Cadence:** spec discussions happen when a draft is ready — not on a calendar. The only calendared ritual is the weekly audit review (15 min: read the audit PR, accept/decline lessons).
- **Language discipline in specs themselves:** specs about customer-facing behavior are written in the customer's register; if the spec author can't say it plainly, the screen won't either.

## Part 3 — Definition of a good spec (checklist for reviewers)

- [ ] Purpose readable by a non-engineer in one paragraph
- [ ] Data section lists only tables in `schema.md` (or amends it in the same PR)
- [ ] Every score/API payload mentions VCI + formula version + lineage
- [ ] States cover: empty, loading, error, low-confidence, draft vs approved, mobile, reduced-motion
- [ ] Guardrail section says how banned-term / suppression / de-id rules apply *here*
- [ ] Every mock registered with a removal plan
- [ ] Every AC checkable by a non-author; test gate named
- [ ] No contradiction with foundation docs (or a deliberate, co-approved amendment)
- [ ] Changelog + version updated

## Part 4 — How the current plan was made (the method, recorded)

The July 2026 plan and spec repo were produced with a five-step method. It worked; reuse it whenever we face a pile of documents and need a plan — a new product line, an acquisition of docs, a big pivot.

**Step 1 — Read everything before writing anything.** All ten source documents (VICBNF v2, Intelligence Engine Framework, Derived Intelligence Catalog, Data Model Framework, Use Case Catalog, business plan, roadmap, workplan, brand guide, website review) plus the live state (progress.md, UI spec, DDRs, screen specs, mock tracker) were read in full first. No synthesis before complete intake — early synthesis bakes in whatever you happened to read first.

**Step 2 — Separate the timeless from the current.** Everything read was sorted into two piles: *foundation truth* (data model, formulas, guardrails, design tokens, business rules — things that outlive any feature) and *current state* (what's built, what's mocked, what's decided, what's open). The foundation pile became `01-foundation/` — four consolidated files replacing scattered, partially-overlapping documents, each with a version header and changelog so it could evolve.

**Step 3 — Derive features from surfaces, gaps from trackers.** The feature list (F01–F12) wasn't invented; it was *derived*: every existing screen/engine became a shipped-status spec, every product in the business plan became a proposed-status spec, and the codebase's own MOCK TRACKER and section-gap tables became the completion plan's punch list — dependency-sorted (backend routes before frontend wiring before content). The principle: **plans built from the project's own recorded gaps are executable; plans built from ambition are decorative.**

**Step 4 — Make every plan item terminate in a check.** Each workstream got an exit gate ("grep for hardcoded S-2041 returns nothing"; "double PDF pull is byte-identical") and each feature got ACs + a test gate. Anything that couldn't be phrased as a check was either sharpened until it could be, or honestly parked as an open decision with an owner (OD-01…OD-05).

**Step 5 — Wrap the plan in a system that maintains itself.** A plan decays the day it ships, so the final step built the maintenance machinery: the onboarding pack (so the plan is teachable), compiled AGENTS.md (so agents can't work from stale truth), the feedback→triage→spec-PR loop (so reality's corrections flow back in), and the log-audit→lessons loop (so mistakes flow back in too). **The deliverable was never the plan — it was the loop that keeps the plan true.**

That's the method. When in doubt: read everything, split timeless from current, derive from recorded gaps, end every item in a check, and build the loop before declaring done.

## Changelog
- 1.0 (2026-07-15): Initial playbook; Part 4 records the founding planning method.
