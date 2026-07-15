# Visentix MVP — Privacy Intelligence Platform

Visentix turns public privacy notices into benchmark-driven privacy **INTELLIGENCE**. It maps notice clauses, benchmarks organizations, and exposes maturity and risk findings without making legal verdicts.

---

## 🚀 How to Run the App

The project contains a **FastAPI backend** (Python) and a **React + TypeScript + Vite frontend**.

### 1. Run the Backend (FastAPI)

1. **Verify Configuration**:
   Ensure you have a `.env` file in the project root with the correct Supabase, DB, and local LLM URLs. (A `.env` has already been populated in this workspace).

2. **Start the FastAPI Server**:
   From the repository root, run:
   ```bash
   ./.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
   ```
   The backend will start and listen on [http://127.0.0.1:8000](http://127.0.0.1:8000). 
   - Interactive API documentation (Swagger UI) is available at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).
   - Health check endpoint is at [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health).

3. **Running Backend Tests**:
   To run the test suite, execute:
   ```bash
   ./.venv/bin/pytest
   ```

---

### 2. Run the Frontend (React + Vite)

1. **Navigate to the Web Directory**:
   ```bash
   cd web
   ```

2. **Verify Configuration**:
   Ensure there is a `web/.env` pointing to the backend API and Supabase endpoints (already populated).

3. **Start the Dev Server**:
   Run the Vite development server:
   ```bash
   npm run dev
   ```
   The frontend application will boot up at [http://localhost:5173](http://localhost:5173).

4. **Running Frontend Tests**:
   Vitest is configured for unit/integration testing. To run tests:
   ```bash
   npx vitest
   ```

---

## 📁 Repository Structure

```
├── app/                  # FastAPI backend source code
│   ├── models/           # Pydantic schemas and database models
│   ├── routers/          # API endpoints (assessments, health, reports, etc.)
│   ├── services/         # Formula engines, OpenAI/Qwen clients, PDF parsers
│   └── main.py           # FastAPI entrypoint
├── web/                  # React + TypeScript + Vite frontend
│   ├── src/              # React source code (components, hooks, pages)
│   ├── package.json      # Frontend package definitions
│   └── vite.config.ts    # Vite configurations
├── db/                   # Database migrations and seed data
├── scripts/              # Data/score scripts + build_agents_md.py (AGENTS.md compiler)
├── tests/                # Backend pytest suite
└── AGENTS.md             # Non-negotiable engineering rules (COMPILED — do not edit generated blocks)
```

---

## 📚 Documentation

Documentation is **spec-driven**: the specs are the source of truth, and `AGENTS.md`
is compiled from them so it can never drift. See `AUTOMATION.md` for the feedback loop.

| Location | For | What's there |
|---|---|---|
| `visentix-specs/` | Builders | Technical source of truth — `00-plan/`, `01-foundation/` (schema · business-logic · intelligence-logic · design-system), `02-features/` (F01–F12), `03-ideas/`, `04-lessons/` |
| `visentix-onboarding/` | People | Plain-language onboarding (what it is, how it works, glossary, the rules, journeys, checklists) |
| `AGENTS.md` | AI agents | Standing rules. Generated sections (`<!-- BEGIN GENERATED … -->`) are rebuilt by `scripts/build_agents_md.py` from the foundation specs — **never hand-edit inside the markers**; edit the source spec and regenerate |
| `AUTOMATION.md` + `logging-and-audit.md` | Maintainers | The self-maintaining feedback loop: `spec-update` skill (`.claude/skills/spec-update/`), `.github/` workflows, `logs/` |
| `docs/` | Operators | Live operational docs: `SETUP.md`, `DEMO_RUNBOOK.md`, `DB_GROUND_TRUTH.md` |
| `docs/old-docs/` | Reference | Pre-restructure docs, archived 2026-07-15 — superseded by `visentix-specs/`; see its `README.md` |

**Feedback flow:** relay any verbal feedback in a Claude session in this repo → the
`spec-update` skill classifies it, edits the specs (with version bumps + changelogs),
regenerates `AGENTS.md`, and drafts a PR for expert approval. Details in `AUTOMATION.md`.

---

## ⚠️ Important Engineering Guidelines (from `AGENTS.md`)
- **Strict Phrasing Guardrail**: Never output banned legal-verdict terms like `"violation"`, `"violates"`, `"illegal"`, or `"unlawful"`. Use exposure/likelihood/confidence terminology instead.
- **Additive Migrations Only**: Do not drop tables or overwrite raw-artifact buckets. Introspect schema first.
- **Service Role Secrets**: The client must only ever use the Supabase Anon Key. Keep the service-role key server-side only.
