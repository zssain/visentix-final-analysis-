# 00 — Remediation Baseline

**Captured:** 2026-08-04 · **By:** Claude (engineer, Prompt 0 kickoff) · **Purpose:** a clean, honest snapshot of the repo *before any fixing*, so later phases can distinguish pre-existing failures from ones they introduce. **No code was changed in this prompt** (read-only verification only; the sole writes are these remediation docs + one `logs/decision-log.md` entry).

---

## 1. Git & tree state

| Field | Value |
|---|---|
| Branch | `main` |
| HEAD commit | `8c4ed92` (`fix(quarterly): declare .pdf routes before bare {param} routes`) |
| Working tree | **DIRTY** (see below) — no branch created, no commits made (per owner instruction; see §7) |

**Uncommitted / untracked at baseline:**
```
 M app/routers/assessments.py          (pre-existing local modification, not from this prompt)
 M app/services/intake/discover.py     (pre-existing local modification, not from this prompt)
?? CODEBASE-REVIEW-2026-08-04.md       (a coarser markdown cut of the review; NOT the 36-ID source — see §5)
?? CODEBASE-REVIEW-2026-08-04.pdf
?? scripts/build_review_pdf.py
?? scripts/review_pdf.css
```
> The two ` M` files existed before this prompt began and were **not** touched here. They must be accounted for by whoever reconciles the working tree.

---

## 2. Runtime & key dependency versions

| Tool | Version |
|---|---|
| Python (system) | 3.14.6 |
| Python (`.venv`, used for tests) | 3.13.12 |
| Node | v25.3.0 |
| npm | 11.7.0 |

**Backend (from `requirements.txt`, confirmed imported):** fastapi 0.115.12 · uvicorn 0.34.3 · supabase 2.15.2 · psycopg[binary] 3.2.9 · pydantic 2.11.5 · pydantic-settings 2.14.1 · httpx 0.28.1 · weasyprint 69.0 · sentence-transformers 4.1.0 · PyMuPDF 1.27.2.3 · beautifulsoup4 4.12.3 · lxml 5.3.0 · APScheduler 3.10.4 · SQLAlchemy 2.0.36 · playwright 1.49.0 · PyJWT 2.13.0 · jinja2 3.1.6 · pytest 8.4.1 · ruff 0.11.13.

**Frontend (from `web/package.json`):** react 19.2.6 · react-dom 19.2.6 · vite ^8.0.12 (built with 8.0.16) · typescript ~6.0.2 · vitest ^4.1.9 · @vitejs/plugin-react ^6.0.1.

---

## 3. Environment variables

**Expected keys** (names only, from `.env.example` — 47 keys). No values reproduced:
`APP_ENV, CORS_ALLOWED_ORIGINS, RENDERER, SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_JWT_SECRET, DATABASE_URL, DATABASE_POOLER_URL, OLLAMA_BASE_URL, QWEN_LOCAL_MODEL, EMBEDDING_MODEL, HOSTED_QWEN_BASE_URL, HOSTED_QWEN_API_KEY, HOSTED_QWEN_MODEL, TAILSCALE_AUTHKEY, SCORING_MODEL_VERSION, SOURCE_CORPUS_VERSION, ENABLE_LIVE_F004, SCHEDULER_ENABLED, SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SMTP_FROM, PUBLIC_BASE_URL, INGESTION_POLITENESS_SECONDS, COURTLISTENER_TOKEN, OPENSTATES_API_KEY, GOVINFO_API_KEY, EDGAR_BULK_PATH, PRINCETON_EXTRACT_DIR, ADMIN_EMAIL, DOMAIN, ACME_EMAIL, GIT_TAG, OLLAMA_IMAGE, BACKUP_RCLONE_REMOTE, BACKUP_BUCKET, BACKUP_PREFIX, BACKUP_RETAIN_DAYS, RCLONE_CONFIG_BASE64.`

**On-disk `.env`:** present at repo root; correctly gitignored (`.gitignore` lines 2–3: `.env`, `.env.*`); `git log --all -- .env` returns nothing (never committed). It holds live values for `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWT_SECRET`, `DATABASE_URL` (embedded DB password), and `TAILSCALE_AUTHKEY`; `HOSTED_QWEN_API_KEY` is empty/placeholder. This is finding **SEC-007** (see matrix). No values are printed anywhere in these docs.

---

## 4. Database / migration state

- **Migration files:** `db/migrations/` contains `0001`–`0042` (49 `.sql` files including duplicate `0011_*/0012_*/0013_*` prefixes, a `0023` gap, and `APPLY_*`/`_TEMPLATE` helpers). Apply order is two **hand-maintained Python lists** in `scripts/db/apply_and_record.py` (`HISTORICAL_APPLIED` + `APPLY_NOW`), not filename sort. This is finding **DB-001**.
- **Latest checked-in schema dump:** `db/schema_dumps/live_schema_20260728T202044.sql` (plus `rls_state_pre0042_20260728T212736Z.sql`). DB-layer findings (SEC-008, DATA-004, DB-002) were verified against these committed dumps.
- **Live DB reachability:** the live Supabase **is reachable** but returned **PostgREST 500 statement-timeouts** (`Proxy-Status: PostgREST; error=57014`, ~8s upstream) under test load during the gate run — see §6. A full live schema introspection was **not** performed here. **BLOCKED (partial):** live `pg_policies` / live FK confirmation for SEC-008 & DATA-004 require a stable DB session; verified against the committed dump instead, which is conclusive for the drift/absence claims.

---

## 5. Source-of-truth reconciliation (important)

The kickoff refers to "all 36 findings in the remediation report." Two review documents exist and **use different ID taxonomies**:

- **`CODEBASE-REVIEW-2026-08-04.md`** (repo root, untracked) — a coarser ~30-finding cut using IDs like `AI-001` (single guardrail finding) and no `GRD-*`/`CRED-001`/`EVAL-001`/`FIND-001`/`AI-004`/`F14-001`.
- **`Visentix-Codebase-Review-Report-v1.0.pdf`** (`~/Downloads`, 29 pages, "Version 1.0 · 4 August 2026", baseline `main @ 8c4ed92`) — **the authoritative source**: its Full Issue Register (§12) contains **exactly** the prompt's 36-ID taxonomy (`SEC-001…011, CRED-001, GRD-001/002/003, FUNC-001, BACK-001/002/003, ARCH-001, EVAL-001, FIND-001, DATA-001…004, AI-002/003/004, FE-001, F14-001, QA-011/012/013, DB-001/002, MAINT-001`).

**Decision:** the `REMEDIATION-MATRIX.md` is built against the **PDF v1.0** register. Its register actually lists **37 rows**; the PDF's own executive summary miscounts HIGH as 9 vs the 10 rows present, hence "36." All 37 IDs are verified in the matrix; the count discrepancy is noted, not silently resolved.

---

## 6. Gate results (actual, verbatim counts)

### Backend — `./.venv/bin/python -m pytest -q`
```
3 failed, 910 passed, 15 skipped, 23 warnings in 262.72s (0:04:22)
PYTEST_EXIT=1
```
**The 3 failures are PRE-EXISTING and environmental — NOT code defects and NOT introduced here:**

| Failed test | Cause |
|---|---|
| `tests/test_embeddings.py::test_disclosure_clause_embedding_dim` | live-DB dependent; low embedding coverage (~2.8%, see EVAL-001) + PostgREST 500 statement-timeout |
| `tests/test_embeddings.py::test_nn_search_returns_results` | same — live embedding NN search |
| `tests/test_schema_p1.py::test_corpus_tables_nonempty[disclosure_clause]` | live PostgREST 500 (`error=57014`) on `disclosure_clause?select=embedding…` |

All three hit the live Supabase and failed with `PostgREST 500 (statement timeout, error 57014)`; the test's own assertion message reads *"failed after retries — transient DB, not a data problem."* The 15 skips are the CI-auto-skipped live-DB/GPU-probe suites (RLS/org-isolation among them — see the report's testing-gap note). **Any future phase that changes this 910/3/15 profile owns the delta.**

### Frontend — `web/` gate
```
npm ci        → NPMCI_EXIT=0
npm run build → BUILD_EXIT=0   (tsc -b && vite build; ✓ built, 2403 modules; one >500kB-chunk advisory only)
npx tsc --noEmit → TSC_EXIT=0
npx vitest run   → VITEST_EXIT=0   (Test Files 7 passed (7) · Tests 75 passed (75))
```
Frontend gate is **fully green**.

---

## 7. Standing-rule conflict (recorded, not resolved)

Per Prompt-0 working rule 3: this series runs **in the working tree with no branches and no commits** (owner instruction), which **conflicts with `AGENTS.md` §1.4** ("Branch + reference the feature ID … Never commit directly to main") and the §1.7 change-report/PR discipline. Logged in `logs/decision-log.md` (2026-08-04 entry) for human reconciliation; will be repeated in every `*-DONE.md`. Prompt 0 itself made no code changes, so the rule first bites at Phase 1.

---

## 8. What this baseline establishes
- **Backend green line = 910 passed / 3 failed (pre-existing, live-DB) / 15 skipped.**
- **Frontend green line = build + tsc + 75 vitest tests, all passing.**
- Anything a later phase breaks against these lines is a regression it must fix before declaring done.
