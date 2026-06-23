# Release Notes — Visentix MVP v1.0

**Date:** 2026-06-23

## What Shipped

### Phase 0: Foundation
- Supabase schema inventory (13 pre-existing tables cataloged)
- AGENTS.md engineering rulebook
- Python venv + Ollama (qwen3:8b) + sentence-transformers (all-MiniLM-L6-v2)
- FastAPI health endpoint with live row counts

### Phase 1: Schema Extension
- 5 new tables: finding_type, recommendation_library, exemplar,
  organization_intelligence_profile, report_snapshot
- 14 nullable columns added to 4 existing tables
- 8 finding_type stubs + 8 recommendation stubs + 3 exemplar stubs

### Phase 2: Backend + Auth
- Structured API: config, DB client, routers, models, services
- JWT verification (Supabase HS256) + 3-role enforcement (customer/sme/admin)
- RLS policies on 5 customer-specific tables
- Profiles table with auto-profile trigger on signup

### Phase 3: Embeddings
- 3,655 disclosure_clause embeddings (384-dim) backfilled
- 172 enforcement_record embeddings backfilled
- ivfflat cosine indexes on both
- 40 auto-seeded exemplar candidates (sme_cleaned=false)

### Phase 4: Scoring Engine
- Organization Intelligence Profiler (7 dimensions: IC, RSS, PGMS, OSI, DSI, EHP, AIGMS)
- Normalization Engine (per-peer similarity weights, small-cohort relaxation)
- Formula Engine: F-002 through F-014 implemented
- VCI (Visentix Confidence Index) with labels and suppression
- Deterministic findings from fixed catalog + report snapshots

### Phase 5: Pipeline
- Notice intake: URL (SSRF-safe) / PDF (PyMuPDF) / raw text
- Decomposition: sections → clauses → 8 taxonomy domains
- LLM client: local Ollama + hosted OpenAI-compatible (env-driven)
- End-to-end scoring reusing Phase 4 engine

### Phase 6: Report
- Guardrail: 16 banned terms, source-excerpt exemption, GuardrailError
- Narrative engine: LLM rephrasing with number verification + fallback
- 12-section report assembly + weasyprint PDF rendering
- Approved language guide (docs/LANGUAGE.md)

### Phase 7: SME Review Gate
- Status model: draft → in_review → approved
- Finding actions: confirm / edit / dismiss
- Gate modes: strict / instant_draft / client_reviews
- Training label capture for fine-tuning

### Phase 8: React Frontend
- Vite + TypeScript + React + Supabase Auth (anon key only)
- Role-based routing (customer / sme / admin)
- 12-section interactive report view (recharts)
- Same component drives portal and Playwright PDF

## Phase 2 Deferrals (Not in MVP)

| Feature | Reason | Target |
|---|---|---|
| Per-company trend line (F-012) | Requires monitoring history over time | Phase 2 Q4 |
| GRC dashboard integration | Enterprise feature, needs customer feedback | Phase 2 |
| White-label / multi-tenant | Single-tenant for MVP; architecture supports it | Phase 2 |
| Quarterly automated reports | Requires scheduled jobs + monitoring | Phase 2 |
| Non-US jurisdictions (EU/GDPR, APAC) | US-only corpus for MVP | Phase 2 Q3 |
| Production volumes (>1000 orgs) | MVP cohort is ~30; scaling needs infra | Phase 2 |
| Real-time monitoring | Requires hash-change detection at scale | Phase 2 |
| Client review workflow | gate_mode=client_reviews stubbed but not full UI | Phase 2 |

## Data Summary

| Metric | Count |
|---|---|
| Organizations | 30 |
| Privacy notices | 26 |
| Disclosure clauses | 3,655 (all embedded) |
| Enforcement records | 172 (all embedded) |
| Obligations | 154 |
| Regulators | 9 |
| Formula versions | 14 (F-001 through F-014) |
| Derived data items | 500+ |
| Risk findings | 140+ |
| Report snapshots | 52+ |
| Exemplar candidates | 43 |

## Test Coverage

| Test File | Tests |
|---|---|
| test_schema_p1.py | 31 |
| test_app_boot.py | 5 |
| test_auth.py | 12 |
| test_embeddings.py | 7 |
| test_profile.py | 29 |
| test_normalization.py | 20 |
| test_f002_f007.py | 21 |
| test_vci.py | 8 |
| test_f008_f014.py | 23 |
| test_findings_reproducible.py | 13 |
| test_intake.py | 31 |
| test_live_pipeline.py | 12 |
| test_guardrail.py | 31 |
| test_narrative.py | 16 |
| test_report_assembly.py | 15 |
| test_review_gate.py | 21 |
| test_training_labels.py | 12 |
| **Backend total** | **307** |
| web AuthGuard.test.tsx | 9 |
| web api.test.ts | 3 |
| web Report.test.tsx | 14 |
| **Frontend total** | **26** |
| **Grand total** | **333** |
