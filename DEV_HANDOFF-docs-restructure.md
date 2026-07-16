# Dev Handoff — Documentation is now spec-driven

**Date:** 2026-07-15
**Branch:** `docs/spec-driven-restructure` (not merged yet — please review)
**Who this is for:** everyone building on this repo, human or AI agent

---

## TL;DR

We replaced our scattered `docs/` folder and hand-written `AGENTS.md` with a
**spec-driven documentation system**. The specs are now the single source of truth,
and `AGENTS.md` is **compiled from them** so agent instructions can't drift. Old docs
weren't deleted — they were reviewed, archived to `docs/old-docs/`, and their still-useful
content was folded into the specs. Nothing is pushed; review the branch before merging.

**What you need to change in your habits:**
1. Product/technical truth lives in `visentix-specs/` — read it there, change it there.
2. **Never hand-edit the generated blocks in `AGENTS.md`** — edit the source spec and run `python scripts/build_agents_md.py`.
3. Branches are named after the feature spec (e.g. `F07-...`), not the phase. Never commit to `main`.

---

## Why we did this

Feedback (from expert audits, customers, our own dogfooding) used to live only in chat
messages. That let the specs and `AGENTS.md` rot while agents kept building yesterday's
product. The new system makes the loop automatic: **the specs are the truth, `AGENTS.md`
is compiled from them, and feedback flows back in through a skill + CI guards.**

Design principle: **automation drafts, humans approve.** The machine does the bookkeeping
(classifying, editing, versioning, regenerating); humans make the decisions.

---

## The new layout

```
repo root/
├── AGENTS.md                 # COMPILED. Generated blocks come from the foundation specs.
├── AUTOMATION.md             # How the self-maintaining feedback loop works
├── logging-and-audit.md      # Logging discipline + weekly AI audit
├── README.md                 # App run guide + a new "Documentation" map
│
├── visentix-specs/           # ★ SOURCE OF TRUTH (for builders)
│   ├── 00-plan/              # mvp-completion-plan.md · full-app-roadmap.md
│   ├── 01-foundation/        # schema · business-logic · intelligence-logic · design-system
│   ├── 02-features/          # F01–F12 feature specs + _TEMPLATE
│   ├── 03-ideas/             # parked / future ideas
│   ├── 04-lessons/           # lessons ledger
│   ├── README.md             # the spec-driven workflow
│   └── how-we-write-specs.md # the spec lifecycle + playbook — READ THIS before writing a spec
│
├── visentix-onboarding/      # plain-language docs (for non-engineers / new joiners)
│
├── .claude/skills/spec-update/   # the feedback → spec-update skill (project-wide)
├── .github/                  # spec-guard · log-audit · feedback-triage (async fallback) + CODEOWNERS
├── logs/                     # decision-log · incidents/ · audits/ · session log
├── scripts/build_agents_md.py    # regenerates AGENTS.md's generated blocks
│
└── docs/                     # trimmed to live operational docs only
    ├── SETUP.md · DEMO_RUNBOOK.md · DB_GROUND_TRUTH.md
    └── old-docs/             # 19 archived legacy docs + a README index (see below)
```

---

## How work happens now

### Giving/relaying feedback
Feedback reaches us in **Teams** (from the expert, customers, our own review). Whoever
heard it just relays it to a Claude session in this repo — e.g. *"the GC said the
Recommendations section reads like legal advice."* The **`spec-update` skill** classifies
it, makes the smallest correct spec edit (with version bump + changelog), regenerates
`AGENTS.md`, logs the decision, and opens a draft PR with a plain-English summary. We paste
that summary back into the Teams thread; the expert approves there; we record the yes and
merge. The expert never touches GitHub. (Async fallback, no Claude handy: the GitHub
feedback issue form → the `feedback-triage` workflow drafts the same PR.)

### Editing a spec
- Read `visentix-specs/how-we-write-specs.md` first — it defines the spec lifecycle
  (`proposed → approved → in-progress → shipped`) and the bar for acceptance criteria.
- **Foundation changes** (`01-foundation/*`) get their own PR, a changelog entry, and a
  version bump — even tiny ones. Foundation drift is how small teams lose their product.
- After changing a foundation spec, run `python scripts/build_agents_md.py` and commit
  the regenerated `AGENTS.md` in the same branch.

### Regenerating AGENTS.md
```bash
python scripts/build_agents_md.py          # rewrite in place
python scripts/build_agents_md.py --check  # CI mode: exits 1 if stale
```
The generated blocks (`<!-- BEGIN GENERATED … -->`) hold the guardrail vocabulary,
current spec versions, hard rules, and spec index. **If you hand-edit inside those
markers, CI fails and tells you to regenerate instead.** Everything outside the markers
is hand-written and edited normally.

### The hard rules (unchanged, still absolute)
- **No legal verdicts.** Banned terms ("violation", "violates", "illegal", "unlawful",
  "non-compliant", "breach of law", "guilty", "liable", …) never appear in customer-facing
  text. Use exposure/likelihood/confidence language. The guardrail hard-fails the build.
- **The model classifies and phrases — it never invents** a number, score, finding, or
  recommendation.
- **Additive migrations only**; never touch existing rows or the `raw-artifacts` bucket.
- **Feature-named branches** (`F07-...`); never commit to `main`.
- Full set: `AGENTS.md` + `scripts/data/hard_rules.md` (the hard-rules source).

---

## What happened to the old docs

23 legacy files were reviewed one by one (old-vs-new coverage analysis).

**Kept live in `docs/`** (operational, no new equivalent):
`SETUP.md`, `DEMO_RUNBOOK.md`, `DB_GROUND_TRUTH.md`.

**Archived to `docs/old-docs/`** via `git mv` (history preserved, nothing hard-deleted):
19 superseded or point-in-time docs. See `docs/old-docs/README.md` for the full index —
it marks each as superseded / migrated / historical and maps it to its replacement.

**Content folded into the specs** (verified against the code first):

| Legacy doc | Now lives in |
|---|---|
| `LANGUAGE.md` (approved-alternative table, exposure pattern, caveats) | `business-logic.md` v1.2 §2 |
| `DATA_HANDLING.md` (hosted-endpoint zero-retention policy, `HOSTED_QWEN_*`) | `business-logic.md` v1.2 §6 |
| `SECURITY_MATRIX.md` (route access-control + RLS matrices) | `F10-auth-and-tenancy.md` |
| v2 reclassification columns (`category_v2`, …) | `schema.md` v1.1 + `intelligence-logic.md` v1.1 §4 |
| test count (was 453) | updated to **633** across specs |

**Two things the analysis got wrong** (caught by checking the code — don't "re-fix" these):
- **JWT is not ES256-only.** `app/auth.py` verifies ES256 (Supabase JWKS) with an **HS256
  fallback**, and local seed auth issues HS256. F10 now says exactly that.
- **Table naming:** `legal_reference` / `finding_legal_reference` are real tables the code
  queries — they do **not** "resolve to `finding_enforcement`." Schema naming left unchanged.

Also removed: 54 Windows `:Zone.Identifier` cruft files that came with the bundle.

---

## Action items for the team

1. **Review & merge** the `docs/spec-driven-restructure` branch. All decisions are in
   `logs/decision-log.md`.
2. **Set up the GitHub automation** before relying on it (it doesn't run until configured):
   - Run `/install-github-app` (or install the Claude app + add the `ANTHROPIC_API_KEY` secret).
   - Confirm the two handles in `.github/CODEOWNERS` (`@Asad-333`, `@zssain`) are your exact
     GitHub logins. There is no expert account — the expert approves in Teams (see the file header).
   - Create the labels: `feedback`, `spec-change`, `code-bug`, `guardrail`, `needs-expert`,
     `auto-drafted`, `from-audit`.
   - Protect `main`: require PR review + the `spec-guard` check. (No `agents-sync` step — spec-guard
     forces the regenerated `AGENTS.md` into the PR, so there's nothing to push post-merge.)
3. **Install the skill** if you work locally — it's already at `.claude/skills/spec-update/`
   (project-wide), so it should just work in a repo session.
4. New joiners start at `visentix-onboarding/README.md`, then
   `visentix-specs/00-plan/mvp-completion-plan.md`.

## Known caveat

The suite is now **633 tests**, but a DB-less local run was **610 pass / 23 fail** — the 23
failures need a live Supabase connection (row-count + export tests). So "633 green" holds
only with the DB connected; it was not fully verified green in the restructure environment.

---

*Questions on the doc system → `AUTOMATION.md`. Questions on how to write a spec →
`visentix-specs/how-we-write-specs.md`.*
