# Visentix MVP — Progress Summary

_Last updated: 2026-07-15 (62 commits, 2026-06-16 → 2026-07-09)_

Visentix turns public privacy notices into benchmark-driven privacy **intelligence**: it ingests notices, decomposes them into clauses, scores organizations against peers, and produces explainable maturity/risk reports — without making legal verdicts.

**Stack:** FastAPI (Python) backend · React + TypeScript + Vite frontend · Postgres (Supabase-hosted DB) · local LLM (Ollama) + `all-MiniLM-L6-v2` embeddings · custom JWT auth.

---

## What has been built, phase by phase

### Phase 0 — Scaffolding & toolchain
- Project scaffold, database inventory, hardened `.gitignore` for secrets hygiene.
- Python venv, Ollama local LLM, embedding model, FastAPI health endpoint.

### Phase 1 — Database schema
- Migration plan, applied migrations, seed stubs, schema documentation ([SCHEMA.md](SCHEMA.md), [DB_GROUND_TRUTH.md](DB_GROUND_TRUTH.md)).
- Test gate: 31 passing schema verification tests.

### Phase 2 — Backend API & auth
- Structured FastAPI skeleton: routers, services, config.
- JWT verification, role enforcement, RLS policies (later fixed for infinite recursion / NULL `auth.uid()`).
- Security gate: removed JWT error detail leakage.

### Phase 3 — Embeddings & exemplars
- Backfilled all NULL clause embeddings with `all-MiniLM-L6-v2`.
- Auto-seeded exemplar candidates from high-maturity clauses.
- Test gate: embedding verification tests.

### Phase 4 — Scoring & findings engines
- **4.0A:** Deterministic Organization Intelligence Profiler.
- **4.0B:** Normalization engine — per-peer similarity weights.
- **4.1 / 4.3:** Formula engine for scoring factors F-002–F-014 + VCI confidence engine with low-confidence suppression.
- **4.4:** Deterministic findings engine with snapshots and reproducibility guarantees.

### Phase 5 — Notice intake & LLM pipeline
- Intake pipeline: URL / PDF / raw text → decomposed clauses.
- LLM client wired into an end-to-end live pipeline; data-handling policy documented ([DATA_HANDLING.md](DATA_HANDLING.md)).

### Phase 6 — Report generation
- Guardrail: banned-term filter with source-excerpt handling.
- Narrative engine: LLM rephrasing with verification and deterministic fallback.
- 12-section report assembly + PDF renderer.

### Phase 7 — SME review
- SME review gate: status model, finding actions, gate modes.
- Training label capture from SME corrections.

### Phase 8 — Frontend (React app)
- React app with auth, role-based routing, API client.
- Interactive 12-section report view with charts and PDF parity.

### Phase 10 — Hardening
- Verification passes, documentation, test fixes.

### Phase 11 — Gap closure (G1–G11)
- F-004 Enforcement Correlation Score — full implementation.
- LLM classification wired into live intake; corpus reclassification plan.
- Regulator heatmap (9×8 grid) wired into report Section 5.
- Obligation embeddings + clause–obligation matcher (Part B).
- F-012 Trend Delta and F-013 Alert Escalation.
- Login redirect fix (AuthProvider context + declarative routing); report route `/reports/:assessmentId`.
- Exemplar SME review: de-identification + approval flow.
- Final audit: **all gaps closed, 453 tests green**.

### Auth migration (throughout)
- Replaced Supabase Auth with a custom **local JWT-based auth system** (ES256 support, session persistence, role loading, profile persisted in localStorage, `local_users.json` seed data).

### UI & branding (recent work)
- Full spec-driven UI rebuild against [UI_SPEC.md](UI_SPEC.md) — Phases 2–4 of the UI track.
- Professional Visentix branding: static brand logos, animated beams, PageHeader component, standardized notice boxes, accessibility-aware reduced motion, score formatting.
- New Assessment page + full end-to-end real-data reports.
- Removed **all mock data** from the frontend — every page now reads from real backend APIs.
- VICBNF v2 spec alignment: full scoring pipeline, taxonomy, profiling, explainability, products ([VICBNF_ALIGNMENT.md](VICBNF_ALIGNMENT.md)).
- Document title updated to "Visentix Intelligence".

### Deployment (latest commit)
- Production API URL configuration and Cloudflare Pages deploy script.

---

## Current state

- Backend: FastAPI at `:8000` (`/docs` Swagger, `/health`), run via `./.venv/bin/uvicorn app.main:app`.
- Frontend: Vite dev server at `:5173` (`cd web && npm run dev`).
- Tests: `./.venv/bin/pytest` (453 green as of the Phase 11 audit) and `npx vitest` for the frontend.
- Uncommitted: edits to `docs/UI_SPEC.md`, `docs/visentix-design.md`, `docs/visentix-screens.md`.

## Key documents

| Doc | Purpose |
| --- | --- |
| [PRODUCT_OVERVIEW.md](PRODUCT_OVERVIEW.md) | What Visentix is and does |
| [UI_SPEC.md](UI_SPEC.md) | Unified screen and component spec |
| [VICBNF_ALIGNMENT.md](VICBNF_ALIGNMENT.md) / [VICBNF_VERIFICATION.md](VICBNF_VERIFICATION.md) | Scoring spec alignment and verification |
| [SCHEMA.md](SCHEMA.md) / [DB_GROUND_TRUTH.md](DB_GROUND_TRUTH.md) | Database schema |
| [DATA_HANDLING.md](DATA_HANDLING.md) / [SECURITY_MATRIX.md](SECURITY_MATRIX.md) | Data & security policy |
| [DEMO_RUNBOOK.md](DEMO_RUNBOOK.md) / [SETUP.md](SETUP.md) | Running and demoing the app |
