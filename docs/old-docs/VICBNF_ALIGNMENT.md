# VICBNF v2 Alignment Map

**Generated:** 2026-07-08
**Branch:** phase-4-ui-login
**Purpose:** Gap analysis between the current visentix-v2-MVP repo and the VICBNF v2 specification. Every later prompt targets a known gap. NO functional code was changed for this document.

---

## 1. Organization Dimensions (7)

| Spec Element | VICBNF Ref | Status | Repo Location | Gap Description | Fix Prompt |
|---|---|---|---|---|---|
| IC (Industry Classification) | org_dim.IC | **Present** | `app/services/profiling/profile.py:compute_ic` | Maps 8 industries to canonical VICBNF categories. Stored as `hash(ic) % 100` numeric proxy in DB — spec expects categorical enum, not random hash. | #2 |
| RSS (Regulatory Scrutiny Score) | org_dim.RSS | **Partial** | `profile.py:compute_rss` | Implements volume + sensitivity + industry + enforcement signals. Formula differs from spec: spec uses `IC_weight x Σ(Regulator_Priority)` with DB-stored weights; repo uses hardcoded additive signals (30+25+25+20 pts). | #2 |
| PGMS (Privacy Governance Maturity) | org_dim.PGMS | **Partial** | `profile.py:compute_pgms` | Checks governance category presence. Spec formula: `Σ(category_weight x depth) x 0.7 + breadth_pct x 0.3`. Repo implements this but with hardcoded weights (not loaded from formula_version). | #2 |
| OSI (Organizational Sophistication) | org_dim.OSI | **Partial** | `profile.py:compute_osi` | Only uses size + public/private + geography. Spec requires additional signals: revenue band, employee count, regulatory filing history. Thin data acknowledged in code. | #2 |
| DSI (Data Sensitivity Index) | org_dim.DSI | **Present** | `profile.py:compute_dsi` | Weighted sum across clause categories. Category weights are hardcoded in-file, not loaded from formula_version. | #2 |
| EHP (Enforcement History Profile) | org_dim.EHP | **Partial** | `profile.py:compute_ehp` | Uses jurisdiction-level enforcement as proxy (all orgs share same enforcement count). Spec requires per-org enforcement linkage. | #2 |
| AIGMS (AI Governance Maturity) | org_dim.AIGMS | **Present** | `profile.py:compute_aigms` | Depth-based scoring from AI clause count. Spec formula matches. Weights hardcoded. | #2 |
| Org dimension tiers (4-tier: low/moderate/elevated/high) | org_dim.tiers | **Present** | `profile.py:TIER_THRESHOLDS, score_to_tier` | 4-tier system (0-24/25-49/50-74/75-100). Spec uses same thresholds. | — |
| Profile stored as first-class DB table | org_dim.storage | **Present** | `db/migrations/0001:organization_intelligence_profile` | Table has all 7 dimensions + profile_version + confidence_score + generated_at. | — |

---

## 2. Notice Scores (8 formulas) + 5 Score Bands

| Spec Element | VICBNF Ref | Status | Repo Location | Gap Description | Fix Prompt |
|---|---|---|---|---|---|
| F-001 Source Reliability | notice.F001 | **Present** | `app/services/scoring/f001.py` | 4-component weighted sum. Correct formula. Not wired into live pipeline (pipeline.py doesn't call it). | #3 |
| F-002 Regulatory Exposure | notice.F002 | **Present** | `formulas.py:compute_f002` | Σ(JW x RPW x DS x EFW) normalized. Matches spec. | — |
| F-003 Benchmark Deviation | notice.F003 | **Present** | `formulas.py:compute_f003` | Weighted 75th-percentile deviation. Matches spec. | — |
| F-004 Enforcement Correlation | notice.F004 | **Present** | `formulas.py:compute_f004` | ES x RPW x EFW per match, weighted-mean aggregate. Matches spec. | — |
| F-005 Disclosure Maturity | notice.F005 | **Present** | `formulas.py:compute_f005` | (present/expected) x 100 - penalties. Matches spec. | — |
| F-006 Transparency | notice.F006 | **Present** | `formulas.py:compute_f006` | Completeness x Clarity x Specificity x Explainability. Matches spec. | — |
| F-007 AI Transparency Maturity | notice.F007 | **Present** | `formulas.py:compute_f007` | (AI clauses / expected controls) x 100 - penalty. Matches spec. | — |
| 5 Score Bands (Leading/Mature/Developing/Lagging/Deficient) | notice.bands | **Missing** | Not implemented | Repo uses 4-tier (low/moderate/elevated/high). Spec defines 5 bands: Leading (80-100), Mature (60-79), Developing (40-59), Lagging (20-39), Deficient (0-19). | #3 |

---

## 3. Clause Taxonomy (30 types across 8 domain IDs)

| Spec Element | VICBNF Ref | Status | Repo Location | Gap Description | Fix Prompt |
|---|---|---|---|---|---|
| 8 domain IDs | taxonomy.domains | **Present** | `decompose.py:DOMAIN_KEYWORDS` | 8 domains: data_sharing, tracking_cookies, consumer_rights, cross_border, sensitive_data, retention, children_teens, ai_automated_decisions. Plus "other" catch-all. | — |
| 30 clause_type sub-classifications | taxonomy.clause_types | **Missing** | Not implemented | Repo classifies to domain only (9 flat slugs). Spec requires 30 clause_types within domains (e.g., data_sharing has: third_party_categories, sharing_purposes, opt_out_mechanism, data_categories_shared). `element_checklist.csv` lists 34 elements but they're only used for F-005 maturity counting — not stored as clause_type on each clause. | #4 |
| domain_id + clause_type compound key | taxonomy.key | **Missing** | `disclosure_clause.category` | DB column `category` stores domain slug only. No `clause_type` column exists. | #4 |
| Keyword classification (9 slugs) | taxonomy.classifier | **Divergent** | `decompose.py:classify_clause` | Uses keyword matching (8 domain keyword lists). Spec expects NLP-backed classification to 30 clause_types. Current LLM classifier in `assessments.py:create_assessment` classifies to domains only. | #4 |
| Clause-level ambiguity score | taxonomy.ambiguity | **Present** | `decompose.py:compute_ambiguity` | Heuristic: vague_words/total_words ratio. | — |
| Clause-level readability score | taxonomy.readability | **Present** | `decompose.py:compute_readability` | Simplified avg-sentence-length based. | — |
| Clause-level NLP confidence | taxonomy.confidence | **Present** | `decompose.py:DecomposedClause.nlp_confidence` | Stored per clause. | — |

---

## 4. Derived Intelligence Objects (9)

| Spec Element | VICBNF Ref | Status | Repo Location | Gap Description | Fix Prompt |
|---|---|---|---|---|---|
| F-008 Compound Risk | derived.F008 | **Present** | `formulas_advanced.py:compute_f008` | Σ(risk x CM x RPW) normalized. Matches spec. | — |
| F-009 Confidence-Weighted | derived.F009 | **Present** | `formulas_advanced.py:compute_f009` | Score x Confidence. Matches spec. | — |
| F-010 Overall Privacy Intelligence | derived.F010 | **Present** | `formulas_advanced.py:compute_f010` | 100 - weighted risk aggregate. Matches spec. | — |
| F-011 Benchmark Percentile | derived.F011 | **Present** | `formulas_advanced.py:compute_f011` | Weighted percentile rank. Matches spec. Attaches cohort size + small-n label. | — |
| F-012 Trend Delta | derived.F012 | **Present** | `formulas_advanced.py:compute_f012` | (current - prior) / prior. Returns 0 with "no_prior_history" when no prior. | — |
| F-013 Alert Escalation | derived.F013 | **Present** | `formulas_advanced.py:compute_f013` | Risk Δ x Enforcement x Priority x Confidence. Low VCI without monitoring. | — |
| F-014 Report Confidence Index | derived.F014 | **Present** | `formulas_advanced.py:compute_f014` | (Validated/Total) x SR x NC. | — |
| Product mapping (which scores map to which report sections) | derived.product_map | **Partial** | `report/assembly.py` | Assembly maps f002-f011 to report sections. F-012/013/014 not wired into report sections (trend section shows mock data). | #5 |

---

## 5. VCI (Visentix Confidence Index)

| Spec Element | VICBNF Ref | Status | Repo Location | Gap Description | Fix Prompt |
|---|---|---|---|---|---|
| 5-component formula | VCI.formula | **Present** | `scoring/vci.py:compute_vci` | NLP 30% + Benchmark 25% + Regulatory 15% + Enforcement 15% + Source 15%. Matches spec exactly. | — |
| 5 labels | VCI.labels | **Present** | `vci.py:VCI_LABELS` | very_high (80-100), high (60-79), moderate (40-59), low (20-39), very_low (0-19). Matches spec. | — |
| Suppression threshold | VCI.suppress | **Present** | `vci.py:SUPPRESSION_THRESHOLD = 40` | VCI < 40 flags do-not-present. Matches spec. | — |
| Per-derived-value VCI | VCI.per_value | **Partial** | `FormulaResult.confidence_score` | Each formula returns a confidence_score. But it's a single float, not the 5-component VCI. Spec requires per-value VCI with component breakdown. | #6 |
| VCI stored per derived_data_item | VCI.storage | **Partial** | `derived_data_item.confidence_score` + `confidence_index` | DB has confidence_score (float) and confidence_index (float). Spec's `confidence_components` (JSONB with 5 components) column exists in SCHEMA.md but may not be populated by the live pipeline. | #6 |

---

## 6. Dynamic Benchmark Population

| Spec Element | VICBNF Ref | Status | Repo Location | Gap Description | Fix Prompt |
|---|---|---|---|---|---|
| Population key (IC + tier-band similarity) | bench.key | **Present** | `normalization/engine.py:compute_peer_similarity` | Industry + 5 tier dimensions + freshness, weighted per VICBNF spec (20/20/15/15/15/10/5). | — |
| Size rules (cohort relaxation bands) | bench.size_rules | **Present** | `engine.py:determine_relaxation_band` | >=100 full, 50-99 minor, 20-49 adjacent, <20 broad. Matches spec. | — |
| Normalization score formula | bench.norm_score | **Present** | `engine.py:compute_peer_similarity` | Weighted tier similarity. Matches spec. | — |
| Benchmark weight formula | bench.bw_formula | **Present** | `engine.py:compute_benchmark_weight` | norm_score x band_factor. Matches spec. | — |
| Dynamic cohort computation | bench.dynamic | **Divergent** | `reports.py:_assemble_from_stored` | Report hardcodes `cohort_size=30` and `cohort_date="2026-06-19"`. The normalization engine EXISTS and CAN compute dynamic cohorts, but the report assembly never calls it — it uses hardcoded mock values. | #7 |
| Population version tracking | bench.version | **Present** | `benchmark_membership.population_version` column | Column exists. `NormalizationResult` includes it. | — |

---

## 7. Developer Data Model Objects (10)

| Spec Element | VICBNF Ref | Status | Repo Location | Gap Description | Fix Prompt |
|---|---|---|---|---|---|
| organization | ddm.org | **Present** | DB table `organization` (pre-existing) | Has organization_id, name, industry, size, geography, public_private, entity_type. | — |
| privacy_notice | ddm.notice | **Present** | DB table `privacy_notice` (pre-existing) | Has notice_id, organization_id, url, notice_type, effective_date, content_hash, etc. | — |
| notice_section | ddm.section | **Present** | DB table `notice_section` (pre-existing) | Has section_id, notice_id, title, section_type, sequence, extracted_text. | — |
| disclosure_clause | ddm.clause | **Partial** | DB table `disclosure_clause` (pre-existing) | Has clause_id, section_id, category, raw_text, normalized_text, ambiguity_score, readability_score, nlp_confidence. Missing: `clause_type` (30-type taxonomy), `domain_id` FK. | #4 |
| derived_data_item | ddm.derived | **Partial** | DB table + migration 0002 | Has object_type, organization_id, notice_id, score, confidence_score, confidence_index, source_lineage, formula_version_id, generated_at. Missing: `value_label` stored column (tier label — exists in some queries but unclear if DB column). | #8 |
| risk_finding | ddm.finding | **Present** | DB table + migration 0002 | Has finding_id, severity, score, domain, organization_id, notice_id, finding_type_code, snapshot_id, generated_at. | — |
| report_snapshot | ddm.snapshot | **Present** | DB table + migration 0001 | Has snapshot_id, organization_id, notice_id, payload (JSONB), formula_version_set, benchmark_population_version, source_corpus_version. | — |
| formula_version | ddm.formula_ver | **Present** | DB table (pre-existing) | Stores formula definitions, weights, thresholds. Referenced by FormulaResult. | — |
| benchmark_membership | ddm.bench_member | **Present** | DB table + migration 0002 | Has normalization_score, benchmark_weight, inclusion_reason, population_version. | — |
| explainability_reference | ddm.explain_ref | **Missing** | Not in schema | Spec defines a dedicated `explainability_reference` table storing per-value provenance (formula sentence, inputs, VCI components). Repo uses ad-hoc `explain.py` and in-memory dict. No DB table. | #9 |

---

## 8. Cross-Cutting Metadata

| Spec Element | VICBNF Ref | Status | Repo Location | Gap Description | Fix Prompt |
|---|---|---|---|---|---|
| formula_version_id on every derived value | meta.fv_id | **Present** | `FormulaResult.formula_version_id`, `derived_data_item.formula_version_id` | Every formula returns version ID; stored in DB. | — |
| source_lineage JSONB on every derived value | meta.lineage | **Present** | `FormulaResult.source_lineage`, `derived_data_item.source_lineage` | Rich lineage dict with all input refs. | — |
| confidence_score on every derived value | meta.confidence | **Present** | `FormulaResult.confidence_score`, `derived_data_item.confidence_score` | Per-value confidence. | — |
| generated_at timestamp | meta.timestamp | **Present** | `derived_data_item.generated_at`, `report_snapshot.created_at` | Timestamps on all derived values. | — |
| source_id / clause_id refs in lineage | meta.source_refs | **Present** | `source_lineage.matches[].clause_id` (F-004), `source_lineage.domains_scored` (F-002) | Lineage includes clause/source references where applicable. | — |
| benchmark_population_id | meta.bench_pop | **Partial** | `derived_data_item.benchmark_population_id` column listed in SCHEMA.md | Column referenced in schema doc; unclear if actually populated by live code. Normalization engine produces `population_version` but pipeline doesn't write it to derived_data_item. | #8 |

---

## 9. Versioning Quintet

| Spec Element | VICBNF Ref | Status | Repo Location | Gap Description | Fix Prompt |
|---|---|---|---|---|---|
| formula_version_id | ver.formula | **Present** | `formula_version` table, `FormulaResult`, `derived_data_item.formula_version_id` | Stored and used everywhere. | — |
| benchmark_population_version | ver.bench_pop | **Partial** | `benchmark_membership.population_version`, `report_snapshot.benchmark_population_version` | Columns exist; normalization engine produces it. Report snapshot has the column. But pipeline doesn't always populate it on derived_data_item rows. | #8 |
| source_corpus_version | ver.corpus | **Missing** | `report_snapshot.source_corpus_version` column exists but never populated | Column exists in schema. No code writes to it. No mechanism to track corpus version changes. | #8 |
| snapshot_id | ver.snapshot | **Present** | `report_snapshot.snapshot_id`, `risk_finding.snapshot_id` | Snapshots created (when approve_assessment runs in some branches). | — |
| generated_at | ver.timestamp | **Present** | `derived_data_item.generated_at`, `report_snapshot.created_at` | Everywhere. | — |

---

## 10. Acceptance Criteria (VICBNF-001 through VICBNF-010)

| Criterion | VICBNF Ref | Status | Evidence | Gap Description | Fix Prompt |
|---|---|---|---|---|---|
| VICBNF-001: 30-type clause taxonomy with domain_id + clause_type | AC-001 | **Missing** | `decompose.py` classifies to 9 flat slugs (8 domains + "other") | No clause_type sub-classification. DB has only `category` column. Spec requires 30 types. | #4 |
| VICBNF-002: 7 org dimensions computed and stored | AC-002 | **Present** | `profile.py:compute_profile` → `organization_intelligence_profile` | All 7 dimensions computed and stored. Formula accuracy partially divergent (see section 1). | #2 |
| VICBNF-003: Dynamic benchmark population with relaxation bands | AC-003 | **Divergent** | `normalization/engine.py` exists but reports use hardcoded n=30 | Engine is built and correct. But the live report path hardcodes `cohort_size=30, cohort_date="2026-06-19"` instead of computing dynamically. | #7 |
| VICBNF-004: Normalization score + benchmark weight per peer | AC-004 | **Present** | `normalization/engine.py:normalize_cohort` | Correct implementation. `scripts/compute_normalization.py` runs batch. | — |
| VICBNF-005: All 14 formulas compute and store with lineage | AC-005 | **Partial** | `formulas.py`, `formulas_advanced.py`, `f001.py` | All 14 formulas exist as pure functions. But: (1) F-001 not wired into pipeline. (2) pipeline.score_notice exists but is never called from the live assessment route — `assessments.py:create_assessment` decomposes + classifies but NEVER scores. Reports use hardcoded mock scores. | #3 |
| VICBNF-006: VCI 5-component with suppression | AC-006 | **Present** | `vci.py:compute_vci` | Correct 5-component formula, correct labels, correct suppression at VCI < 40. | — |
| VICBNF-007: Live intake → decompose → score end-to-end | AC-007 | **Missing** | `assessments.py:create_assessment` → `decompose()` + LLM classify, but no scoring | Live intake decomposes and classifies clauses into the DB, but NEVER calls `pipeline.score_notice`. The scoring pipeline exists but is dead code on the live path. Reports serve hardcoded mock data. | #3 |
| VICBNF-008: Report snapshot reproducibility | AC-008 | **Partial** | `report_snapshot` table, `assembly.py` | Table exists. Snapshot creation is attempted in some branches on approve. But the live report route (`reports.py:_assemble_from_stored`) returns hardcoded mock data, not snapshot-driven data. | #3 |
| VICBNF-009: 5 score bands (Leading/Mature/Developing/Lagging/Deficient) | AC-009 | **Missing** | Repo uses 4-tier (low/moderate/elevated/high) | Spec defines 5 bands with different names and boundaries. Repo has 4 tiers used everywhere (profile, formulas, heatmap, report). | #3 |
| VICBNF-010: Explainability reference stored per derived value | AC-010 | **Missing** | No `explainability_reference` table | Spec requires a DB table with formula_plain, methodology, inputs, VCI components per derived value. Repo has `explain.py` with in-memory descriptions but no persistent DB storage. | #9 |

---

## 11. Known Divergences (Critical — Do Not Lose Sight Of)

### D1: Clause taxonomy is 9 flat slugs; spec requires domain_id + clause_type (30)

- **Repo:** `decompose.py:DOMAIN_KEYWORDS` classifies to 8 domains + "other" = 9 slugs. `disclosure_clause.category` stores one slug.
- **Spec:** 8 domain IDs, each with 2-6 clause_types (30 total). `element_checklist.csv` lists 34 elements but they're only used as a maturity checklist, not as clause-level classifications.
- **Impact:** F-005 maturity scoring works at domain level. But clause-level granularity (which specific disclosure elements are present vs. missing) is lost. This weakens finding specificity and maturity gap detection.

### D2: Report route serves hardcoded mock scores — live pipeline is dead

- **Repo:** `reports.py:_assemble_from_stored` returns hardcoded `scores = {"f002": {"score": 45.0, ...}, ...}` for EVERY assessment. `pipeline.score_notice` exists but is never called from any route.
- **Spec:** Reports must render from real derived_data_item rows. VICBNF-005/007/008 require live scoring → snapshot → report.
- **Impact:** Every report shows the same scores regardless of the assessed notice. The entire scoring pipeline is functional but disconnected.

### D3: Cohort size hardcoded to n=30 / 2026-06-19

- **Repo:** `reports.py:_assemble_from_stored` and `assembly.py:assemble_report` default to `cohort_size=30, cohort_date="2026-06-19"`.
- **Spec:** Cohort must be dynamically computed from the normalization engine, with real population_version, real cohort date, and relaxation band documentation.
- **Impact:** Violates VICBNF-003 (dynamic benchmarking) and honest-numbers principle. Current cohort label is mock data.

### D4: No 5-band score labels

- **Repo:** Uses 4-tier (low/moderate/elevated/high) everywhere.
- **Spec:** Requires 5 bands: Leading (80-100), Mature (60-79), Developing (40-59), Lagging (20-39), Deficient (0-19).
- **Impact:** Reports, UI, and tier assignments all use wrong label set.

### D5: Org dimension formulas use hardcoded weights, not formula_version

- **Repo:** `profile.py` hardcodes `INDUSTRY_SENSITIVITY`, `DSI_CATEGORY_WEIGHTS`, `GOVERNANCE_SIGNALS`, `SIZE_SCORES` in-file.
- **Spec:** All weights must be loaded from `formula_version` table at runtime.
- **Impact:** Weight changes require code deployment instead of DB update.

### D6: derived_data_item lacks full versioning quintet population

- **Repo:** `source_corpus_version` column exists on report_snapshot but is never written. `benchmark_population_id` column referenced in SCHEMA.md but pipeline doesn't populate it on derived_data_item rows.
- **Spec:** Every derived value must carry the full quintet (formula_version_id, benchmark_population_version, source_corpus_version, snapshot_id, generated_at).

### D7: No explainability_reference table

- **Repo:** `app/services/report/explain.py` builds explanation bundles in memory. No DB persistence.
- **Spec:** Requires `explainability_reference` table storing per-value formula_plain, methodology, inputs, VCI components, and provenance.

### D8: URL intake stores raw HTML — no structured extraction

- **Repo:** `extract.py:extract_from_url` fetches HTML and passes `response.text` to decompose. No HTML-to-text cleaning, no tag stripping, no boilerplate removal.
- **Spec:** Extraction should produce clean text from the notice content only, not the full HTML page (nav bars, footers, cookie banners, etc.). This pollutes clause classification with non-notice content and degrades NLP confidence.

### D9: IC stored as hash(ic) % 100 — non-deterministic

- **Repo:** `profile.py:scores_dict` uses `hash(self.ic) % 100`. Python's `hash()` is randomized per process (`PYTHONHASHSEED`).
- **Note:** This was fixed in the `fix/security-correctness-p1` branch with `IC_NUMERIC` stable mapping, but that fix is NOT on the current `phase-4-ui-login` branch.

---

## Fix Prompt Index

| # | Scope | Key Gaps Addressed |
|---|---|---|
| #2 | Org profiling accuracy | RSS/PGMS/OSI formula alignment, load weights from formula_version |
| #3 | Live scoring pipeline | Wire pipeline.score_notice into create_assessment, store results in derived_data_item, serve real scores in reports, adopt 5-band labels |
| #4 | 30-type clause taxonomy | Add clause_type column, expand classifier from 9→30, update F-005 to use clause-level maturity |
| #5 | Report product mapping | Wire F-012/013/014 into report sections 10/12, replace mock trend data |
| #6 | Per-value VCI components | Store 5-component VCI breakdown per derived_data_item, not just scalar |
| #7 | Dynamic benchmarking | Replace hardcoded n=30 with live normalization engine output in report path |
| #8 | Versioning quintet | Populate source_corpus_version, benchmark_population_id on every derived row |
| #9 | Explainability table | Create explainability_reference DB table, persist explain bundles on score write |
