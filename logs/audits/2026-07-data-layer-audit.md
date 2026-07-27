# Data-Layer Audit — 2026-07-20

**Scope:** read-only audit of migrations, live Supabase schema, corpus census, service state, ingestion scripts, and storage. No INSERT/UPDATE/DELETE/DDL was issued. No secrets, connection strings, or keys appear in this report.

**Method note.** The direct Postgres host in `DATABASE_URL` (`db.<ref>.supabase.co:5432`) is IPv6-only and does not resolve/route from this machine, so `information_schema` could not be queried over a direct connection. Live schema was introspected instead via the **PostgREST OpenAPI reflection** (`GET /rest/v1/`) and per-column probes using the server-side service-role key loaded from `.env`. Row counts and grouped counts use PostgREST `count=exact` and single-column pagination. One caveat applies throughout §1: PostgREST reflects its own schema cache and does not see objects that exist but have had API privileges revoked (e.g. a password table). Where that matters it is called out.

---

## 1. Migrations

### 1a. Inventory (applied order)

Files live in `db/migrations/`. There is **no migration runner or `schema_migrations` tracking table** — migrations are applied by manually pasting SQL into the Supabase dashboard (the `APPLY_*.sql` bundles and in-file comments confirm this). Nothing enforces that every file was actually run; this is the root cause of the drift in §1c. Note the **duplicated sequence numbers** (two `0011`, two `0012`, two `0013`), which a lexical runner would order as below.

| # | File | Tables created | Columns / objects added | Destructive? |
|---|---|---|---|---|
| 0001 | `0001_phase1_new_tables.sql` | `finding_type`, `recommendation_library`, `exemplar`, `organization_intelligence_profile`, `report_snapshot` | + indexes; `exemplar.embedding vector(384)` & ivfflat | No (CREATE IF NOT EXISTS) |
| 0002 | `0002_phase1_alter_existing.sql` | — | `risk_finding`(+organization_id, notice_id, finding_type_code, snapshot_id, generated_at); `clause_obligation`(+match_method, similarity); `benchmark_membership`(+normalization_score, benchmark_weight, inclusion_reason, population_version); `derived_data_item`(+score, confidence_index, source_lineage) | No (ADD COLUMN IF NOT EXISTS) |
| 0003 | `0003_phase1_seed_stubs.sql` | — | Seeds 8 `finding_type` stubs, 8 `recommendation_library` stubs, 3 `exemplar` stubs (all `sme_authored/sme_cleaned=false`), ON CONFLICT DO NOTHING | No (idempotent INSERT) |
| 0004 | `0004_phase2_profiles_rls.sql` | `profiles` | `user_role` enum; `handle_new_user()` trigger; ENABLE RLS + SELECT policies on profiles/risk_finding/report_snapshot/derived_data_item/organization_intelligence_profile | No (DROP POLICY/TRIGGER IF EXISTS only — no data/tables dropped) |
| 0005 | `0005_phase2_rls_fix.sql` | — | Recreates the same 5 policies to deny on NULL `auth.uid()` | No (policy DROP/CREATE) |
| 0006 | `0006_phase2_rls_fix_recursion.sql` | — | `get_my_role()` SECURITY DEFINER fn; recreates 5 policies to avoid recursion | No (policy/fn replace) |
| 0007 | `0007_phase3_vector_indexes.sql` | — | ivfflat indexes on `disclosure_clause.embedding` & `enforcement_record.embedding`; `ANALYZE` | No |
| 0008 | `0008_phase7_training_label.sql` | `training_label` | + 3 indexes | No |
| 0009 | `0009_obligation_embedding.sql` | — | `obligation.embedding vector(384)` + ivfflat | No |
| 0010 | `0010_category_v2.sql` | — | `disclosure_clause`(+category_v2, nlp_confidence_v2, classifier_version) | No |
| 0011a | `0011_live_assessment_isolation.sql` | — | ENABLE RLS + SELECT policies on privacy_notice/notice_section/disclosure_clause; **`ALTER TABLE privacy_notice ALTER COLUMN organization_id DROP NOT NULL`** | **Non-additive but non-destructive** — see note below |
| 0011b | `0011_local_users.sql` | `local_users` | + email index | No |
| 0011c | `0011_reference_corpus.sql` | `legal_reference`, `finding_legal_reference`, `explainability_reference`, `ingestion_run` | `enforcement_record`(+17 cols: jurisdiction, regulator_id, entity_name, entity_industry, action_date, fine_amount_usd, violation_types, laws_cited, domains, remedies, summary, official_url, source_name, retrieved_at, content_hash, source_type, verified) | No |
| 0012a | `0012_finding_content.sql` | — | `finding_type.definition` | No |
| 0012b | `0012_versioning_metadata.sql` | — | `derived_data_item`(+scoring_model_version, source_corpus_version, benchmark_population_version); `risk_finding`(+scoring_model_version, source_corpus_version) | No |
| 0013a | `0013_clause_taxonomy_v2.sql` | — | `disclosure_clause`(+domain_id, clause_type, transparency_score) | No |
| 0013b | `0013_enforcement_extra_cols.sql` | — | `enforcement_record`(+source_type, verified) — overlaps 0011c | No |
| 0014 | `0014_org_profile_fields.sql` | — | `organization`(+industry_id, sub_industry, public_company_flag, size_metadata, revenue_metadata, jurisdiction_presence); `organization_intelligence_profile`(+industry_id, sub_industry, rss_tier, pgms_tier, osi_tier, dsi_tier, ehp_tier, aigms_tier) | No |
| 0015 | `0015_explainability_reference.sql` | `explainability_reference` (re-CREATE IF NOT EXISTS, superset of 0011c) | + 2 indexes | No |
| 0016 | `0016_legal_reference.sql` | `legal_reference`, `finding_legal_reference` (re-CREATE IF NOT EXISTS) | Seeds ~24 real `legal_reference` rows + ~15 `finding_legal_reference` junctions (ON CONFLICT DO NOTHING) | No |
| 0017 | `0017_snapshot_rendered_report.sql` | — | `report_snapshot`(+rendered_report, content_hash, report_version, scoring_model_version, glossary_version, template_version) | No |
| 0018 | `0018_intake_columns.sql` | — | `privacy_notice.extraction_confidence`; `disclosure_clause`(+domain_id, transparency_score, specificity_score) | No |
| 0019 | `0019_versioning_columns.sql` | — | `derived_data_item`(+scoring_model_version, source_corpus_version, benchmark_population_version); `risk_finding`(+scoring_model_version, source_corpus_version) — re-run of 0012b | No |

Also present (not sequence migrations): `APPLY_0009_0010.sql`, `APPLY_ALL_PHASE1.sql`, `APPLY_PHASE2_AUTH.sql` — copy/paste bundles that duplicate the content of 0001–0010 and the Phase-2 auth migrations for the Supabase SQL editor.

### 1b. Destructiveness

**No `DROP TABLE`, `TRUNCATE`, `DELETE`, `DROP COLUMN`, or `DROP CONSTRAINT` on any table exists in any migration.** Every table uses `CREATE TABLE IF NOT EXISTS`, every column uses `ADD COLUMN IF NOT EXISTS`, every seed uses `ON CONFLICT DO NOTHING`. The only `DROP`s are `DROP POLICY IF EXISTS` / `DROP TRIGGER IF EXISTS` (RLS management — recreated in the same file) and one **`ALTER COLUMN organization_id DROP NOT NULL`** in 0011a. That single statement is technically a non-additive ALTER, but it only *loosens* a constraint (allows public seed notices with NULL org) and cannot lose or corrupt data. Conclusion: **migrations are effectively additive and safe**; the one constraint-loosening ALTER is worth noting per AGENTS.md §2 but is not destructive.

### 1c. Drift — migrations vs. live schema

Live schema was read from PostgREST reflection (29 exposed tables). Comparing every migration-declared object against live:

**All migration-created corpus/versioning columns are present in live** for `risk_finding`, `clause_obligation`, `benchmark_membership`, `derived_data_item`, `obligation`, `disclosure_clause`, `enforcement_record`, and `privacy_notice`. The following are **missing from the live database** (migration authored but evidently never applied):

| Migration | Table | Missing in live | Impact |
|---|---|---|---|
| **0017** | `report_snapshot` | `rendered_report`, `content_hash`, `report_version`, `glossary_version`, `template_version` (only `scoring_model_version` landed) | This is the VICBNF-008 / DIR-010 **immutable-rendered-report** foundation. Without `rendered_report` + `content_hash`, byte-identical snapshot re-pull (Hard Rule 6) is **not physically backed** by the schema. |
| **0014** | `organization` | `industry_id`, `sub_industry`, `public_company_flag`, `size_metadata`, `revenue_metadata`, `jurisdiction_presence` | Live `organization` instead carries the pre-existing corpus columns (`industry`, `public_private`, `size`, `geography`, `sector_tags`, `entity_type`, `slug`, `tenant_id`). Profiling code expecting `industry_id` must be falling back to `industry`. Schema.md §2.3 names `industry_id`, so **schema.md is also out of sync with live**. |
| **0014** | `organization_intelligence_profile` | `industry_id`, `sub_industry`, `rss_tier`, `pgms_tier`, `osi_tier`, `dsi_tier`, `ehp_tier`, `aigms_tier` | The 7-dimension **tier labels** (§2 intelligence-logic) have no column to live in; tier bands cannot be persisted per profile. |
| **0011b** | `local_users` | Entire table not visible to PostgREST (404 `PGRST205`) | Ambiguous: either unapplied, or applied then had API grants revoked (a password-hash table *should* be hidden from the API). `local_users.json` at repo root + `setup_local_auth.py` strongly suggest local JWT auth (F10) actually runs off the **JSON file**, and the DB table is unused/unapplied. Cannot be confirmed without direct DB access. |

Other structural notes: live has `benchmark_cluster` (8 cols) where schema.md §2.6 names `benchmark_population`; live has `finding_clause` / `finding_enforcement` junctions not named in schema.md. These predate the migrations (mid-flight corpus) but widen the schema.md-vs-reality gap.

---

## 2. Corpus census

Read-only counts via service-role REST, 2026-07-20:

| Table | Rows |
|---|---|
| organization | **37** |
| source_record | 303 |
| privacy_notice | 50 |
| notice_section | 1,564 |
| disclosure_clause | **6,145** |
| obligation | 273 |
| enforcement_record | 649 |
| regulator | 9 |
| litigation_event | 14 |
| benchmark_membership | 30 |
| training_label | **0** |
| monitoring_event | 5 |
| report_snapshot | 69 |

**`disclosure_clause` by `category`** (legacy base classification; sums to 6,145):

| category | count |
|---|---|
| other | **3,864** (62.9%) |
| data_sharing | 887 |
| consumer_rights | 424 |
| tracking_cookies | 358 |
| cross_border | 207 |
| sensitive_data | 155 |
| retention | 145 |
| ai_automated_decisions | 53 |
| children_teens | 52 |

**`disclosure_clause` by `category_v2`** (additive v2 reclassification; sums to 6,145):

| category_v2 | count |
|---|---|
| **NULL (unclassified)** | **3,754** (61.1%) |
| data_sharing | 731 |
| other | 728 |
| consumer_rights | 384 |
| sensitive_data | 206 |
| retention | 146 |
| cross_border | 86 |
| tracking_cookies | 49 |
| ai_automated_decisions | 36 |
| children_teens | 25 |

- Only **2,391 / 6,145 (38.9%)** of clauses have any `category_v2` value. The v2 reclassifier (`reclassify_other.py`, `classifier_version=qwen3-8b-local-v1`) has **not been run to completion** across the corpus — intelligence-logic §4 claims it "reduced the 'other' bucket from ~65% toward ~20%," but with 3,754 rows still `category_v2 IS NULL`, the effective downstream "other" rate (prefer `category_v2`, fall back to `category`) is nowhere near 20%.

**`disclosure_clause` with NULL `embedding`: 2,490 / 6,145 (40.5%).**
This directly contradicts the header comment on migration 0007 ("Applied after embedding backfill (0 NULLs remaining)"). The ivfflat vector index exists, but ~40% of clauses are invisible to any cosine/embedding search (benchmark normalization, clause↔obligation matching). Consistent with new notices ingested *after* the one-time backfill never being embedded (see §3 — the embeddings service is a stub).

**`organization` by `industry`** (sums to 37):

| industry | count |
|---|---|
| fintech | 10 |
| logistics | 10 |
| manufacturing | 10 |
| unknown | 7 |

Only **3 real industries + "unknown"** across 37 orgs — against a documented 10-industry taxonomy (intelligence-logic §2). Benchmark cohorts (`benchmark_membership` = 30) are thin and industry breadth is narrow; `<20`-cohort low-confidence rules (§5) will apply almost everywhere.

---

## 3. Services — state held in module-level Python variables instead of the database

| Service | Holds DB-belonging state in memory? | Exact definitions |
|---|---|---|
| **`app/services/training.py`** | **YES — critical.** SME correction "flywheel" labels are appended to a module list, never written to the `training_label` table. Corroborated by the census: `training_label` = **0 rows** despite reviews having occurred in-process. Lost on every restart. | Line 22: `_labels: list[dict] = []` |
| **`app/services/review.py`** | **YES — critical.** Assessment review state, gate mode, and the VCI analyst-review queue are all in-memory. `gate_mode` should be a `platform_setting` row (schema §2.1); review actions/approvals should persist. All evaporate on restart. | Line 63: `_reviews: dict[str, AssessmentReview] = {}`  ·  Line 64: `_gate_mode: GateMode = DEFAULT_GATE_MODE`  ·  Line 205: `_low_vci_objects: dict[str, list[dict]] = {}  # assessment_id → [{object_type, vci_score, ...}]`  ·  Line 206: `_analyst_cleared: dict[str, set[str]] = {}    # assessment_id → {cleared object_types}` |
| **`app/services/embeddings.py`** | No module state — but the service is an **unimplemented stub** that raises. This is why NULL embeddings (§2) are never backfilled at ingest time. | Lines 11–13: `async def embed_clauses(...) -> int:` → `raise NotImplementedError("Embedding service not yet implemented")` |
| **`app/services/llm.py`** | No *data* state. Holds only a cached client singleton (config/transport, not business data) — acceptable. | Line 201: `_client: LLMClient | None = None` (memoized in `get_llm_client()`) |

Note the gate-mode enum also **diverges** between spec and code: business-logic §5 defines gate modes `instant_draft` / `expert_review`, whereas `review.py` defines `STRICT` / `INSTANT_DRAFT` / `CLIENT_REVIEWS` — a second, unrelated drift in the same in-memory subsystem.

---

## 4. Ingestion inventory — scripts that load or fetch external data

**Fetch from external networks/APIs:**

| Script | External source(s) | Populated |
|---|---|---|
| `scripts/batch_assess.py` | Live peer privacy-policy **URLs** (airbnb, uber, lyft, expedia, booking, …) run through the full intake pipeline | `organization`, `privacy_notice`, `notice_section`, `disclosure_clause` (+ downstream scoring) — builds the benchmark population from real peer notices |
| `scripts/ingest/ingest_enforcement.py` | **FTC** cases/proceedings (scrape) + **CourtListener** API (`COURTLISTENER_TOKEN`) | `enforcement_record` (upsert on enforcement_id; leaves `embedding=NULL` for later backfill) |
| `scripts/ingest/ingest_legal_refs.py` | **eCFR** (COPPA/HIPAA/GLBA), **EUR-Lex** + gdpr-info (GDPR), 11 state legislature sites | `legal_reference`, `finding_legal_reference` |
| `scripts/ingest/ingest_state_laws.py` | **OpenStates** API (`OPENSTATES_API_KEY`) + hardcoded state bill URLs | `obligation` (14 requirement_types/law), `legal_reference` |

**Load local/seed data (no external network):** `seed_cleaned_exemplars.py`, `seed_exemplar_candidates.py`, `seed_trend_baseline.py` → `exemplar` / snapshot demo rows; `setup_local_auth.py` → local auth users.

**Compute/transform from existing DB rows or local models (not external ingest):** `compute_f001/f004/scores/advanced_scores/normalization/profiles.py`, `generate_findings.py`, `rescore_all.py`, `match_clause_obligations.py` → `derived_data_item` / `risk_finding` / `report_snapshot`; `embed_backfill.py`, `embed_obligations.py`, `scripts/ingest/embed_enforcement_new.py` → embeddings via local all-MiniLM-L6-v2; `reclassify_other.py`, `reclassify_taxonomy_v2.py` → `category_v2` / `domain_id` via local Qwen; `update_findings.py` → replaces `finding_type` stubs (DB-only PATCH).

**Doc drift:** `scripts/ingest/README.md` lists `ingest_ecfr.py`, `ingest_eurlex.py`, `ingest_ftc.py` as separate files — none exist; their functionality was consolidated into `ingest_legal_refs.py` and `ingest_enforcement.py`. The README omits the present `ingest_legal_refs.py`, `embed_enforcement_new.py`, and `update_findings.py`.

---

## 5. Storage — `raw-artifacts` bucket

Bucket `raw-artifacts` (private, `public=false`). Read-only top-level listing (no files fetched, nothing modified):

```
raw-artifacts/
├── ag_actions/     (state AG enforcement)
├── cfpb/           (CFPB materials)
├── cppa/           (California Privacy Protection Agency)
├── frameworks/     (NIST/ISO/framework docs)
├── ftc/            (FTC enforcement source docs)
├── litigation/     (litigation-event source docs)
├── notices/        (captured privacy-notice artifacts — cf. privacy_notice.storage_path)
└── state_laws/     (state privacy-law texts)
```

8 top-level prefixes, organized by source family — matching the tiered source model in F02 / schema §2.2.

---

## Summary — the three biggest gaps

**1. Live schema has silently drifted from the migrations, and nothing catches it.** With no migration runner or tracking table (migrations are hand-pasted into the Supabase SQL editor), migration **0017** (`report_snapshot.rendered_report` + `content_hash` + versioning) and **0014** (the `organization` / `organization_intelligence_profile` profiling and tier columns) were never applied to the live database, and `local_users` is not present in the API schema. The most serious consequence is that the **immutable-snapshot / byte-identical-reproducibility guarantee (Hard Rule 6, VICBNF-008, DIR-010) is not physically backed** — there is no `rendered_report`/`content_hash` column to freeze a report into — and schema.md itself no longer matches live (`industry_id` vs `industry`, `benchmark_population` vs `benchmark_cluster`).

**2. Core stateful subsystems live in process memory, not the database.** The SME training flywheel (`training.py._labels`) and the entire review/gate/VCI-queue subsystem (`review.py._reviews`, `_gate_mode`, `_low_vci_objects`, `_analyst_cleared`) hold data in module-level Python variables — proven by `training_label` = **0 rows** in the DB despite the table existing since migration 0008. Every SME confirm/edit/dismiss, every approval, and the platform gate mode are lost on restart, so the "flywheel for model improvement" (business-logic §5) is currently capturing nothing durable, and gate-mode names diverge from spec on top of it.

**3. The embedding and reclassification corpus is only partially built.** **40.5%** of `disclosure_clause` rows (2,490/6,145) have a NULL embedding — flatly contradicting migration 0007's "0 NULLs remaining" — because the embeddings service (`embeddings.py`) is an unimplemented stub, so notices ingested after the one-time backfill are never vectorized, silently degrading benchmark normalization and clause↔obligation matching. In parallel, the v2 reclassifier has only labeled 38.9% of clauses (3,754 still `category_v2 IS NULL`), well short of the "~20% other" the specs claim, and the benchmark corpus itself is thin (37 orgs spanning only 3 industries).
