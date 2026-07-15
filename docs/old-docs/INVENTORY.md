# Visentix MVP — Phase 0 Inventory

**Date:** 2026-06-16
**Method:** Read-only introspection via Supabase REST API (PostgREST) using anon key.
**Branch:** `phase-0-inventory`

---

## 1. Repository File Tree

```
v2(visentix)/
├── AGENTS.md              # Engineering rules for the Visentix MVP (read by Claude Code)
├── .env                   # Real secrets (gitignored, never committed)
├── .env.example           # Template with dummy values for onboarding
├── .gitignore             # Ignores .env, __pycache__, node_modules, IDE files
└── docs/
    └── INVENTORY.md       # This file — Phase 0 inventory
```

**Note:** The repo is currently scaffolding-only. No application code, config/targets.yaml,
config/obligations.csv, or config/element_checklist.csv exist yet. These will be created in
later phases.

---

## 2. Supabase Schema — All Tables

| # | Table                | Rows  | ALL-NULL Columns                          |
|---|----------------------|------:|-------------------------------------------|
| 1 | organization         |    30 | `public_private`, `sector_tags`           |
| 2 | source_record        |   303 | `update_date`                             |
| 3 | privacy_notice       |    26 | (none)                                    |
| 4 | notice_section       |   767 | (none)                                    |
| 5 | disclosure_clause    | 3,655 | `subdomain`, `embedding`                  |
| 6 | obligation           |   154 | `effective_date`                          |
| 7 | enforcement_record   |   172 | `target_industry`, `remedy`, `embedding`  |
| 8 | regulator            |     9 | (none)                                    |
| 9 | litigation_event     |    14 | `industry`, `settlement_value`            |
|10 | monitoring_event     |     5 | (none)                                    |
|11 | formula_version      |    14 | (none — `thresholds` is NULL on 12 of 14) |
|12 | benchmark_membership |    30 | (none)                                    |
|13 | derived_data_item    |     0 | (empty table — no rows)                   |

**Total tables:** 13 (all expected tables present, zero unexpected tables found)

---

## 3. Column Detail per Table

### 3.1 organization (30 rows)

| Column           | Type   | Notes                   |
|------------------|--------|-------------------------|
| organization_id  | uuid   | PK                      |
| name             | text   |                         |
| slug             | text   |                         |
| domain           | text   |                         |
| industry         | text   |                         |
| size             | text   | e.g. "large"            |
| geography        | text   | e.g. "US"               |
| public_private   | text   | **ALL NULL**            |
| entity_type      | text   | e.g. "peer", "target"   |
| sector_tags      | jsonb  | **ALL NULL**            |
| tenant_id        | text   | e.g. "proto"            |
| created_at       | timestamptz |                    |

### 3.2 source_record (303 rows)

| Column                    | Type    | Notes                     |
|---------------------------|---------|---------------------------|
| source_id                 | text    | PK, e.g. "SRC-REG-STATE-0053" |
| family                    | text    | e.g. "SRC-REG-STATE"      |
| jurisdiction              | text    |                            |
| regulator                 | text    |                            |
| source_type               | text    | e.g. "enforcement"         |
| title                     | text    |                            |
| url                       | text    |                            |
| effective_date            | date    | sparse NULLs               |
| update_date               | date    | **ALL NULL**               |
| retrieval_ts              | timestamptz |                        |
| storage_path              | text    |                            |
| sha256                    | text    |                            |
| authority_weight          | float8  |                            |
| freshness_weight          | float8  |                            |
| completeness_weight       | float8  |                            |
| extraction_confidence     | float8  |                            |
| source_reliability_score  | float8  | Pre-computed F-001 score   |
| nlp_processing_status     | text    | e.g. "pending"             |
| version_id                | int4    |                            |
| notes                     | text    |                            |

### 3.3 privacy_notice (26 rows)

| Column                        | Type    | Notes              |
|-------------------------------|---------|---------------------|
| notice_id                     | uuid    | PK                  |
| organization_id               | uuid    | FK → organization   |
| notice_type                   | text    |                     |
| url                           | text    |                     |
| effective_date                | date    |                     |
| retrieval_date                | date    |                     |
| content_hash                  | text    |                     |
| version_id                    | int4    |                     |
| jurisdiction_scope            | jsonb   | e.g. ["US"]         |
| storage_path                  | text    |                     |
| ai_disclosure_presence        | bool    |                     |
| tracking_disclosure_presence  | bool    |                     |
| consumer_rights_presence      | bool    |                     |
| retention_disclosure_presence | bool    |                     |
| cross_border_indicator        | bool    |                     |
| sensitive_data_indicator      | bool    |                     |

### 3.4 notice_section (767 rows)

| Column         | Type | Notes             |
|----------------|------|-------------------|
| section_id     | uuid | PK                |
| notice_id      | uuid | FK → privacy_notice |
| title          | text |                   |
| section_type   | text | e.g. "general"    |
| sequence       | int4 |                   |
| extracted_text | text |                   |

### 3.5 disclosure_clause (3,655 rows)

| Column           | Type    | Notes                     |
|------------------|---------|---------------------------|
| clause_id        | uuid    | PK                        |
| section_id       | uuid    | FK → notice_section       |
| raw_text         | text    |                           |
| normalized_text  | text    |                           |
| category         | text    | See distribution below    |
| subdomain        | text    | **ALL NULL**              |
| ambiguity_score  | float8  |                           |
| readability_score| float8  |                           |
| nlp_confidence   | float8  |                           |
| states_mentioned | jsonb   | sparse NULLs              |
| embedding        | vector  | **ALL NULL** (pgvector)   |

### 3.6 obligation (154 rows)

| Column           | Type | Notes                          |
|------------------|------|--------------------------------|
| obligation_id    | uuid | PK                             |
| source_id        | text | FK → source_record             |
| jurisdiction     | text |                                |
| law              | text | e.g. "CCPA/CPRA"              |
| domain           | text |                                |
| requirement_type | text | e.g. "notice_requirement"      |
| applicability    | text |                                |
| effective_date   | date | **ALL NULL**                   |

### 3.7 enforcement_record (172 rows)

| Column          | Type    | Notes                         |
|-----------------|---------|-------------------------------|
| enforcement_id  | uuid    | PK                            |
| source_id       | text    | FK → source_record            |
| regulator_id    | text    | FK → regulator                |
| target_company  | text    |                               |
| target_industry | text    | **ALL NULL**                  |
| issue_tags      | jsonb   |                               |
| remedy          | text    | **ALL NULL**                  |
| penalty_usd     | float8  | sparse NULLs                  |
| action_date     | date    | sparse NULLs                  |
| jurisdiction    | text    |                               |
| summary         | text    | sparse NULLs                  |
| embedding       | vector  | **ALL NULL** (pgvector)       |

### 3.8 regulator (9 rows)

| Column                       | Type   | Notes                |
|------------------------------|--------|----------------------|
| regulator_id                 | text   | PK                   |
| name                         | text   |                      |
| jurisdiction                 | text   |                      |
| authority                    | text   |                      |
| priority_weights             | jsonb  | domain → weight map  |
| enforcement_frequency_weight | float8 |                      |

### 3.9 litigation_event (14 rows)

| Column           | Type   | Notes                |
|------------------|--------|----------------------|
| litigation_id    | uuid   | PK                   |
| source_id        | text   | FK → source_record   |
| claim_type       | text   | e.g. "bipa"          |
| issue_tags       | jsonb  |                      |
| jurisdiction     | text   |                      |
| industry         | text   | **ALL NULL**         |
| defendant        | text   |                      |
| settlement_value | float8 | **ALL NULL**         |
| filed_date       | date   |                      |

### 3.10 monitoring_event (5 rows)

| Column                    | Type        | Notes               |
|---------------------------|-------------|----------------------|
| event_id                  | uuid        | PK                   |
| trigger_type              | text        | e.g. "hash_change"   |
| source_id                 | text        | FK → source_record   |
| prior_value               | text        |                      |
| current_value             | text        |                      |
| material_change_indicator | int4        |                      |
| severity                  | text        | e.g. "medium"        |
| ts                        | timestamptz |                      |

### 3.11 formula_version (14 rows)

| Column             | Type | Notes                |
|--------------------|------|----------------------|
| formula_version_id | text | PK, e.g. "F-001_v1" |
| formula_id         | text | e.g. "F-001"        |
| name               | text |                      |
| definition         | text | Human-readable       |
| weights            | jsonb| NULL on most rows    |
| thresholds         | jsonb| NULL on most rows    |
| effective_date     | date |                      |

### 3.12 benchmark_membership (30 rows)

| Column          | Type | Notes              |
|-----------------|------|--------------------|
| cluster_id      | text | e.g. "fintech-large-US" |
| organization_id | uuid | FK → organization  |

### 3.13 derived_data_item (0 rows)

Empty table. Column schema could not be inspected via REST API (no rows returned).
This table is expected to be populated by the formula engine in later phases.

---

## 4. Disclosure Clause Category Distribution

| Category              | Count | Percentage |
|-----------------------|------:|------------|
| other                 | 2,391 | 65.4%      |
| data_sharing          |   439 | 12.0%      |
| tracking_cookies      |   276 |  7.6%      |
| consumer_rights       |   165 |  4.5%      |
| cross_border          |   162 |  4.4%      |
| sensitive_data        |    84 |  2.3%      |
| retention             |    60 |  1.6%      |
| children_teens        |    47 |  1.3%      |
| ai_automated_decisions|    31 |  0.8%      |
| **Total**             | **3,655** | **100%** |

---

## 5. Formula Version Catalog (14 rows)

| ID        | Name                              | Weights                                                             | Thresholds                                                        |
|-----------|-----------------------------------|---------------------------------------------------------------------|-------------------------------------------------------------------|
| F-001_v1  | Source Reliability Score           | authority:0.25, freshness:0.25, completeness:0.25, extraction:0.25  | NULL                                                              |
| F-002_v1  | Regulatory Exposure Score          | NULL                                                                | low:[0,24], moderate:[25,49], elevated:[50,74], high:[75,100]     |
| F-003_v1  | Benchmark Deviation Score          | NULL                                                                | NULL                                                              |
| F-004_v1  | Enforcement Correlation Score      | NULL                                                                | NULL                                                              |
| F-005_v1  | Disclosure Maturity Score          | NULL                                                                | NULL                                                              |
| F-006_v1  | Transparency Score                 | NULL                                                                | NULL                                                              |
| F-007_v1  | AI Transparency Maturity           | NULL                                                                | NULL                                                              |
| F-008_v1  | Compound Risk Score                | NULL                                                                | NULL                                                              |
| F-009_v1  | Confidence Weighted Score          | NULL                                                                | NULL                                                              |
| F-010_v1  | Overall Privacy Intelligence Score | regulatory:0.25, benchmark:0.2, disclosure:0.2, enforcement:0.15, ai:0.1, compound:0.1 | NULL                          |
| F-011_v1  | Benchmark Percentile               | NULL                                                                | NULL                                                              |
| F-012_v1  | Trend Delta                        | NULL                                                                | NULL                                                              |
| F-013_v1  | Alert Escalation                   | NULL                                                                | NULL                                                              |
| F-014_v1  | Report Confidence Index            | NULL                                                                | NULL                                                              |

**Note:** Only F-001 and F-010 have weights defined. Only F-002 has thresholds defined.
Remaining formulas (F-003 through F-009, F-011 through F-014) need weights/thresholds
populated in a future phase.

---

## 6. pgvector Status

**Confirmed enabled.** Evidence:
- `disclosure_clause.embedding` column exists (type: vector) — currently ALL NULL (0 / 3,655 populated)
- `enforcement_record.embedding` column exists (type: vector) — currently ALL NULL (0 / 172 populated)

Embeddings have not yet been computed. This is expected and will be done in Phase 3.

---

## 7. Embedding NULL Confirmation

| Table               | Column    | Non-NULL count | Total rows | Status     |
|---------------------|-----------|---------------:|-----------:|------------|
| disclosure_clause   | embedding |              0 |      3,655 | ALL NULL   |
| enforcement_record  | embedding |              0 |        172 | ALL NULL   |

---

## 8. derived_data_item Confirmation

The `derived_data_item` table exists but contains **0 rows**. It is empty as expected —
no scores have been computed yet. This table will be populated by the formula engine.

---

## 9. Unexpected Tables / Columns

**No unexpected tables found.** All 13 tables match the expected list from AGENTS.md.

Additional probed table names that do NOT exist:
profiles, users, report, report_snapshot, finding, recommendation, benchmark_score,
score_history, audit_log, data_flow, data_category, element_checklist, risk_score,
clause_category, sector, jurisdiction, regulation, notice_version, batch_job,
embedding_run, classification_run, policy, alert, notification, webhook, api_key,
tenant, report_template, finding_type, recommendation_library, score_snapshot,
clause_embedding, vector_store, data_element, processing_purpose, third_party,
data_subject_type.

---

## 10. Summary of ALL-NULL Columns Across All Tables

These columns exist but have no data populated:

| Table               | Column           | Rows in table |
|---------------------|------------------|---------------|
| organization        | public_private   | 30            |
| organization        | sector_tags      | 30            |
| source_record       | update_date      | 303           |
| disclosure_clause   | subdomain        | 3,655         |
| disclosure_clause   | embedding        | 3,655         |
| obligation          | effective_date   | 154           |
| enforcement_record  | target_industry  | 172           |
| enforcement_record  | remedy           | 172           |
| enforcement_record  | embedding        | 172           |
| litigation_event    | industry         | 14            |
| litigation_event    | settlement_value | 14            |

---

## 11. Nothing Modified

This inventory was produced via **read-only** REST API queries. No tables, rows, columns,
files, or bucket objects were created, altered, or deleted.
