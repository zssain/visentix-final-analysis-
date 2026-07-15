# Visentix Specification Repository

**Purpose:** This is the single source of truth for building Visentix with a spec-driven, AI-assisted workflow. Every feature, schema change, formula, and screen is defined here in Markdown before code is written. AI coding agents (Claude Code, etc.) and human developers implement *from these specs*, never from memory or verbal descriptions.

---

## Repository layout

```
visentix-specs/
├── README.md                        ← you are here: how the spec system works
├── 00-plan/
│   ├── mvp-completion-plan.md       ← finish the current MVP (mock closure, gaps, gates)
│   └── full-app-roadmap.md          ← MVP → four commercial products
├── 01-foundation/                   ← cross-cutting truth; features may not contradict these
│   ├── schema.md                    ← canonical data model (tables, fields, relationships, lineage)
│   ├── business-logic.md            ← products, personas, pricing, guardrails, gate modes, SLAs
│   ├── intelligence-logic.md        ← formulas F-001–F-014, VICBNF classification, VCI, cohorts
│   └── design-system.md             ← tokens, typography, cross-screen furniture, DDR summary
├── 02-features/                     ← one spec per feature (feature-based architecture)
│   ├── _TEMPLATE.md                 ← copy this for every new feature
│   ├── F01 … F12                    ← the feature catalog
├── 03-ideas/
│   └── further-ideas.md             ← parked ideas, future-state, patent-adjacent concepts
├── 04-lessons/
│   └── lessons.md                   ← permanent ledger: every caught mistake → the guard that prevents it
└── how-we-write-specs.md            ← the playbook: spec lifecycle, developer discussions, and how this plan was made
```

## The spec-driven workflow (how AI builds from this repo)

1. **Foundation first.** Any AI agent working on Visentix loads `01-foundation/` into context before touching a feature. Foundation docs are authoritative; a feature spec that conflicts with foundation is a bug in the spec, fixed *before* implementation.
2. **One feature, one spec, one branch.** Each `02-features/Fxx-*.md` is a self-contained work unit: purpose, data touched, API contracts, UI behavior, states, acceptance criteria, and test gates. The AI implements exactly the acceptance criteria — nothing more.
3. **Specs change before code changes.** If implementation reveals the spec is wrong, the agent proposes a spec edit (PR to this repo), it's approved, then code follows. Never let code drift ahead of specs.
4. **Test gates are part of the spec.** Every feature lists what must be green before merge (unit, integration, verification tests). This continues the existing project discipline (633-test suite, phase gates).
5. **Traceability everywhere.** This mirrors the product itself: every score has lineage; every line of code has a spec ID. Commits reference feature IDs (`F04: implement VCI suppression threshold`).
6. **Versioning.** Foundation docs carry a version header. Formula or schema changes bump the version and record the change in a changelog block at the bottom of the file — matching the platform's own `formula_version` discipline.

## Prompting conventions for AI agents

When starting a work session, use this framing:

> "Load `01-foundation/schema.md`, `01-foundation/intelligence-logic.md`, and `02-features/F07-continuous-monitoring.md`. Implement acceptance criteria AC-3 and AC-4 only. Do not modify tables not listed in the feature's Data section. Run the test gate before declaring done."

Rules for agents:
- **Never invent formulas, weights, taxonomy codes, or thresholds** — they live in `intelligence-logic.md` and are versioned.
- **Never emit legal-verdict language** in generated copy (see guardrail in `business-logic.md`).
- **Never hardcode display values** — every number in the UI comes from a derived_data_item / API (DIR-008).
- **Mock data must be registered** in the feature spec's Mock section with a replacement plan (continuing the MOCK TRACKER discipline).

## Current product context (July 2026)

The MVP (FastAPI + React/TS + Postgres/Supabase + local LLM + MiniLM embeddings) is functionally complete through Phase 11: intake → decomposition → classification → profiling → normalization → scoring (F-002–F-014) → findings → SME gate → 12-section report → monitoring surfaces. 633 tests green. Remaining work is defined in `00-plan/mvp-completion-plan.md`.
