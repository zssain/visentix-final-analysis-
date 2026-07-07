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
├── scripts/              # Data processing and score-generation scripts
├── tests/                # Backend pytest suite
└── AGENTS.md             # Non-negotiable MVP engineering guidelines
```

---

## ⚠️ Important Engineering Guidelines (from `AGENTS.md`)
- **Strict Phrasing Guardrail**: Never output banned legal-verdict terms like `"violation"`, `"violates"`, `"illegal"`, or `"unlawful"`. Use exposure/likelihood/confidence terminology instead.
- **Additive Migrations Only**: Do not drop tables or overwrite raw-artifact buckets. Introspect schema first.
- **Service Role Secrets**: The client must only ever use the Supabase Anon Key. Keep the service-role key server-side only.
