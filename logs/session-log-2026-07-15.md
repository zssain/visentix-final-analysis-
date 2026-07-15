# Session Log — Visentix Planning & Documentation Sprint

**Date:** 2026-07-15 · **Participants:** Founder + Claude · **Output:** `visentix-docs.zip` (50 files, 3 bundles + master README)

A compressed record of what was asked, what was decided, and what was produced — in order.

---

## 1. Inputs reviewed

Ten uploaded documents were read in full: VICBNF v2 Enterprise Developer Specification, Visentix Intelligence Engine Framework, Derived Intelligence Catalog v1, Data Model & Intelligence Mapping Framework v1, US Use Case Catalog v1, Business Plan, Strategic Roadmap, Execution Workplan (Phases 1–3), Brand Identity Guide, Website/Product Experience Review — plus the live project state: progress summary (Phase 11 complete, 453 tests green), UI_SPEC (incl. the 14-item MOCK TRACKER and OD-01–OD-05 open decisions), the DDRs, and the screen specs.

**Project context established:** FastAPI + React/TS/Vite + Supabase Postgres + local Ollama LLM + MiniLM embeddings + custom ES256 JWT auth. Pipeline functionally complete end-to-end (intake → decompose → classify → profile → normalize → score F-002–F-014 → findings → SME gate → 12-section reproducible report → monitoring surfaces). Remaining: mock closure, section gaps, open decisions, hardening, first pilot delivery.

## 2. Request 1 — Plan + spec-driven architecture → `visentix-specs/`

Asked: review docs, plan to finish MVP, plan the full app, and create a spec-driven, AI-buildable architecture (schema, business logic, intelligence logic, features, ideas as md files).

Delivered:
- **`00-plan/mvp-completion-plan.md`** — 3 sprints, 4 workstreams: (A) mock closure, dependency-sorted — 6 new backend routes first (monitoring trend/events/alerts, codex, gate-mode, batch trigger), then 8 frontend wirings, then content prerequisites; (B) the 11 report-section gaps; (C) recommendations to unblock OD-01–OD-05; (D) auth hardening, deploy, pilot delivery. Definition of done: MOCK TRACKER empty, all sections real-data, first expert-approved pilot report delivered.
- **`00-plan/full-app-roadmap.md`** — 5 releases mapping to the 4 products: R1 Assessment (finish MVP, Tier 1 revenue) → R2 corpus ingestion + GRC monitoring at scale (Tier 2) → R3 white-label portal + Intelligence APIs (Tier 3) → R4 quarterly report + bulk analysis → R5 predictive/knowledge-graph moats. Five cross-release invariants (reproducibility, VCI everywhere, guardrail, single intelligence source, spec-first).
- **`01-foundation/`** — four authoritative consolidations: `schema.md` (full entity catalog + lineage/versioning hard rules), `intelligence-logic.md` (7-dimension profile, F-001–F-014 with weights, VCI bands, cohort ladder, normalization, LLM task boundaries), `business-logic.md` (products, guardrail, gate modes, SLAs, personas, IP posture), `design-system.md` (tokens, DDR summary, cross-screen furniture, route map).
- **`02-features/`** — F01–F12 specs (intake, corpus pipelines, profiling/benchmarking, scoring engine, report generation, SME workbench, monitoring dashboard, codex/methodology, admin, auth/tenancy, white-label/APIs, quarterly/bulk) each with data, API contracts, states, guardrails, ACs, test gates — plus `_TEMPLATE.md`.
- **`03-ideas/further-ideas.md`** — parked ideas with a promotion path (idea → spec → build).

## 3. Request 2 — Plain-language onboarding → `visentix-onboarding/`

Asked: a separate, layman bundle for teaching future hires and closing the gap between the 2 engineers, the 1 expert, and customers.

Delivered ten files: README (reading paths per role) · app brief · pipeline-as-a-story · glossary (incl. "words we avoid") · deliverables (customer-shareable) · **who-does-what** (the expert's three hats — Reviewer / Business-Logic Owner / Auditor — plus a decision-rights table and the rule "the expert reviews specs and screens, never code") · the ten rules we never break · four customer journeys (incl. the expert's review morning) · week-one checklists per role · how-we-build (spec-driven AI development, explained plainly). Governance rule stated in both bundles: specs win on detail, onboarding wins on understanding.

## 4. Request 3 — Automated feedback → spec/AGENTS.md updates → `visentix-automation/`

Asked: when feedback arrives, ensure AGENTS.md and specs update — automated.

Design decision: **automation drafts, humans approve** — and **AGENTS.md is compiled, not written**, so it cannot drift. Delivered:
- **`AGENTS.md`** with GENERATED sections (hard rules, current versions, spec index) built by **`scripts/build_agents_md.py`** from the foundation/feature specs (smoke-tested against the real spec files; `--check` mode for CI).
- **`feedback.yml` issue form** — one front door for expert audits, customer, and internal feedback.
- **Workflows** (verified against current `anthropics/claude-code-action@v1` mechanics): `feedback-triage` (classifies issues; drafts spec-only PRs with version bumps + plain-English explanations; code bugs routed to engineers; issue bodies treated as untrusted data) · `agents-sync` (regenerates AGENTS.md on any specs merge) · `spec-guard` (required PR check: banned-term scan, Fxx spec-reference check, AGENTS.md freshness, hand-edit-in-generated-block detection).
- **`CODEOWNERS`** — expert approves specs; expert + engineer jointly approve intelligence-logic, schema, and hard rules. Setup ≈15 min via `/install-github-app`.

## 5. Request 4 — Log everything + AI audits + spec playbook

Asked: (a) logs of every action with periodic AI audit/code review so caught errors feed future specs; (b) an md describing how future specs get made, dev discussions, and how this plan was made.

Delivered:
- **`logging-and-audit.md`** + **`logs/`** — three logs (decision log, incident files from template, agent-run trail via existing GitHub conventions) + `exports/` for machine dumps.
- **`log-audit.yml`** — weekly (Mon 06:00 UTC + manual): AI auditor reads incidents, decision-log diffs, CI failures, merged PRs; hunts patterns; opens an audit-report PR; files ≤5 lessons as `feedback` issues that flow into the **existing** triage loop (one loop, two inlets); chases stalled lessons via a "Ledger check."
- **`visentix-specs/04-lessons/lessons.md`** — permanent ledger; a lesson isn't Closed until linked to its guard; guard ladder: CI guard > spec change > checklist. Seeded with 5 real historical lessons (RLS recursion, JWT detail leak, delta-color inversion, static n=30, SSRF-badge near-miss).
- **`visentix-specs/how-we-write-specs.md`** — spec lifecycle (4 legitimate triggers, no fifth door), the spec-discussion meeting format (fixed jobs per seat; every disagreement ends as decision / owned question / deferral), reviewer checklist, and **Part 4: the recorded five-step method used to make this plan** (read everything first → split timeless from current → derive from recorded gaps not ambition → every item terminates in a check → build the maintenance loop before declaring done).

## 6. Request 5 — Merge the legacy AGENTS.md

The old AGENTS.md was provided; asked to keep the good, discard the rest.

**Kept (near-verbatim):** the mid-flight data-protection block (additive-only migrations, introspect first, never re-run NLP over classified clauses, read-only table list — matches schema.md), the full secrets/SSRF/RLS/zero-retention/upload-validation section, STOP-and-ask, announce-before-touch preamble, change reports, pinned deps, egress rule.
**Absorbed into the source of truth (not just AGENTS.md):** the stronger banned-term list (+ unlawful, breach of law, guilty, liable), "the model classifies and phrases — it never invents," and the no-fabricated-scale rule → updated `hard_rules.md`, `spec-guard` regex, and `business-logic.md` (bumped to **v1.1** with changelog); AGENTS.md regenerated and re-verified.
**Made durable:** literal counts ("3,655 clauses", "~30 orgs") → principle-level phrasing.
**Discarded:** phase-named branches (superseded by Fxx-named branches tied to feature specs).
The merge itself was recorded as a decision-log entry — practicing the discipline on the discipline.

## 7. Request 6 — One combined zip

All three bundles unified under `visentix-docs/` with a master README (bundle map, how they connect, install order). Delivered as **`visentix-docs.zip`**.

---

## Key decisions register (the ones to remember)

1. One intelligence engine, four products; presentation never recalculates (DIR-008).
2. Guardrail is absolute: comparative/exposure language only; enforced by filter + expert + CI scan.
3. Spec-first: specs change before code; expert reviews specs and screens, never code.
4. AGENTS.md is compiled from specs — drift is structurally impossible.
5. Automation drafts, humans approve (CODEOWNERS gates; nothing auto-merges).
6. One feedback loop, two inlets: humans (issue form) and logs (weekly AI audit).
7. Lessons close only when linked to a guard; prefer CI guard > spec > checklist.
8. Success metric #1 unchanged from the business plan: deliver the first production-quality report to a pilot customer.

## Immediate next steps

1. Drop the bundle into the repo; run the 15-min automation setup; fill CODEOWNERS names; protect `main`.
2. Trigger `log-audit` once manually (dry run) to verify permissions/labels.
3. Lock OD-01–OD-05 using the recommendations in the MVP plan.
4. Execute Sprint 1: the six backend routes + content prerequisites (formula descriptions can be lifted from intelligence-logic.md §7).

## 8. Addendum — Prototype review & report-spec updates (same day)

Appendix H (One-Time Assessment PDF prototype) and Appendix I (Quarterly Report prototype) were reviewed against the specs. Coverage was near-complete; deliberate improvements over the prototypes noted (no fabricated scale, no faked trend history, DDR-era furniture). Gaps fixed: **F05** gained closing matter (Next Steps page + back cover, AC-5, guardrail-filtered, frozen in snapshot); **F12** gained a full publication section manifest — the five named Intelligence Indicators, Benchmark Spotlight (de-id + suppression gated), descriptive-only Strategic Outlook, real-count cover rule, and AC-5–AC-8; **design-system.md v1.1** extends `trendColor` with a per-metric polarity flag (maturity vs exposure indices). Post-MVP priority recommendation recorded: (1) corpus ingestion F02 → (2) monitoring productization → (3) portfolio/remediation GRC V1 → (4) white-label F11 → (5) quarterly F12 gated on corpus scale. AGENTS.md regenerated; decision logged.

## 9. Addendum — Verbal feedback becomes a skill (same day)

Recognized that feedback is usually verbal, not filed. Built the **`spec-update` skill** (`visentix-automation/skills/spec-update/` — SKILL.md + classification rubric with worked examples): relay feedback in plain words in any Claude session and it runs the full discipline — classify (guardrail > lesson > spec-change > code-bug > idea > question precedence), locate, smallest-correct-edit with version bumps/changelogs, AGENTS.md regeneration, decision-log + lessons-ledger entries, branch/draft-PR, and a plain-English approval summary for the expert. Hard limits preserved: never edits code, never invents weights/codes (marks them PROPOSED), never softens hard rules without joint approval. Automation README reframed: skill = primary inlet; feedback-triage workflow = optional async path; spec-guard/agents-sync/log-audit unchanged. Skill also packaged as an installable `.skill` file.
