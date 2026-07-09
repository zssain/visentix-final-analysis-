# Database Ground Truth — Live Supabase Schema

Introspected on 2026-07-09 via PostgREST service-role key. **Read-only — no data modified.**

## Table Summary

| Table | Exists? | Row Count | Notes |
|-------|---------|-----------|-------|
| `legal_reference` | MISSING | — | Must be created |
| `explainability_reference` | MISSING | — | Must be created |
| `finding_type` | Yes | 8 | |
| `finding_legal_reference` | MISSING | — | PostgREST hinted `finding_enforcement` exists instead |
| `recommendation_library` | Yes | 8 | |
| `enforcement_record` | Yes | 172 | Embedding col = `embedding`, 384-dim (MiniLM-L6-v2) |
| `obligation` | Yes | 154 | Has `embedding` col, 384-dim |
| `regulator` | Yes | 9 | |
| `disclosure_clause` | Yes | 3655 | Has `embedding`, plus v2 reclassification cols |
| `derived_data_item` | Yes | 883 | |
| `risk_finding` | Yes | 140 | |
| `report_snapshot` | Yes | 52 | |
| `organization` | Yes | 30 | |
| `organization_intelligence_profile` | Yes | 30 | |
| `benchmark_membership` | Yes | 30 | |

### Also discovered (not in original list)

| Table | Exists? | Row Count | Notes |
|-------|---------|-----------|-------|
| `finding_enforcement` | Yes | 352 | Join table: `finding_id`, `enforcement_id`, `similarity` |

---

## Per-Table Column Details

### legal_reference — MISSING
Returned PostgREST error: `Could not find the table 'public.legal_reference' in the schema cache`

### explainability_reference — MISSING
Returned PostgREST error: `Could not find the table 'public.explainability_reference' in the schema cache`

### finding_legal_reference — MISSING
Returned PostgREST error: `Could not find the table 'public.finding_legal_reference' in the schema cache`.
PostgREST hint: "Perhaps you meant the table 'public.finding_enforcement'"

### finding_type (8 rows)
| Column | Observed Python Type | Sample |
|--------|---------------------|--------|
| `code` | str | PK |
| `title` | str | |
| `default_severity` | str | |
| `domain` | str | |
| `regulator_relevance` | dict (jsonb) | |
| `linked_recommendation_id` | NoneType (nullable) | |
| `sme_authored` | bool | |

### recommendation_library (8 rows)
| Column | Observed Python Type |
|--------|---------------------|
| `id` | str (uuid) |
| `finding_type_code` | str |
| `severity_bucket` | str |
| `title` | str |
| `body_template` | str |
| `source_note` | str |
| `sme_authored` | bool |
| `version` | int |

### enforcement_record (172 rows)
| Column | Observed Python Type |
|--------|---------------------|
| `enforcement_id` | str (uuid) |
| `source_id` | str |
| `regulator_id` | str |
| `target_company` | str |
| `target_industry` | NoneType (nullable str) |
| `issue_tags` | list (jsonb array) |
| `remedy` | NoneType (nullable str) |
| `penalty_usd` | NoneType (nullable numeric) |
| `action_date` | str (date) |
| `jurisdiction` | str |
| `summary` | str |
| `embedding` | str (vector(384)) |

**Confirmed:** Enforcement table is `enforcement_record`. Embedding column is `embedding`, dimension = **384**.

### obligation (154 rows)
| Column | Observed Python Type |
|--------|---------------------|
| `obligation_id` | str (uuid) |
| `source_id` | str |
| `jurisdiction` | str |
| `law` | str |
| `domain` | str |
| `requirement_type` | str |
| `applicability` | str |
| `effective_date` | NoneType (nullable date) |
| `embedding` | str (vector(384)) |

### regulator (9 rows)
| Column | Observed Python Type |
|--------|---------------------|
| `regulator_id` | str (uuid) |
| `name` | str |
| `jurisdiction` | str |
| `authority` | str |
| `priority_weights` | dict (jsonb) |
| `enforcement_frequency_weight` | float |

### disclosure_clause (3655 rows)
| Column | Observed Python Type |
|--------|---------------------|
| `clause_id` | str (uuid) |
| `section_id` | str |
| `raw_text` | str |
| `normalized_text` | str |
| `category` | str |
| `subdomain` | NoneType (nullable str) |
| `ambiguity_score` | float |
| `readability_score` | float |
| `nlp_confidence` | float |
| `states_mentioned` | NoneType (nullable) |
| `embedding` | str (vector) |
| `category_v2` | str |
| `nlp_confidence_v2` | float |
| `classifier_version` | str |

### derived_data_item (883 rows)
| Column | Observed Python Type |
|--------|---------------------|
| `derived_data_item_id` | str (uuid) |
| `item_code` | str |
| `object_type` | str |
| `organization_id` | str |
| `notice_id` | str |
| `value` | float |
| `value_label` | str |
| `formula_version_id` | str |
| `benchmark_population_id` | str |
| `source_snapshot_id` | NoneType (nullable) |
| `confidence_score` | float |
| `confidence_components` | str (jsonb) |
| `explanation` | NoneType (nullable str) |
| `generated_at` | str (timestamptz) |
| `score` | float |
| `confidence_index` | float |
| `source_lineage` | str (jsonb) |

### risk_finding (140 rows)
| Column | Observed Python Type |
|--------|---------------------|
| `finding_id` | str (uuid) |
| `domain` | str |
| `severity` | str |
| `score` | float |
| `benchmark_deviation_score` | NoneType (nullable float) |
| `regulatory_exposure_score` | NoneType (nullable float) |
| `enforcement_correlation_score` | NoneType (nullable float) |
| `confidence_score` | float |
| `interpretive_variance` | NoneType (nullable float) |
| `explanation` | NoneType (nullable str) |
| `formula_version_id` | str |
| `created_at` | str (timestamptz) |
| `organization_id` | str |
| `notice_id` | str |
| `finding_type_code` | str |
| `snapshot_id` | str |
| `generated_at` | NoneType (nullable timestamptz) |

### report_snapshot (52 rows)
| Column | Observed Python Type |
|--------|---------------------|
| `snapshot_id` | str (uuid) |
| `organization_id` | str |
| `notice_id` | str |
| `payload` | str (jsonb) |
| `formula_version_set` | str (jsonb) |
| `benchmark_population_version` | int |
| `source_corpus_version` | int |
| `created_at` | str (timestamptz) |

### organization (30 rows)
| Column | Observed Python Type |
|--------|---------------------|
| `organization_id` | str (uuid) |
| `name` | str |
| `slug` | str |
| `domain` | str |
| `industry` | str |
| `size` | str |
| `geography` | str |
| `public_private` | NoneType (nullable str) |
| `entity_type` | str |
| `sector_tags` | NoneType (nullable jsonb) |
| `tenant_id` | str |
| `created_at` | str (timestamptz) |

### organization_intelligence_profile (30 rows)
| Column | Observed Python Type |
|--------|---------------------|
| `profile_id` | str (uuid) |
| `organization_id` | str |
| `ic` | int |
| `rss` | float |
| `pgms` | float |
| `osi` | int |
| `dsi` | float |
| `ehp` | int |
| `aigms` | int |
| `profile_version` | int |
| `confidence_score` | float |
| `generated_at` | str (timestamptz) |

### benchmark_membership (30 rows)
| Column | Observed Python Type |
|--------|---------------------|
| `cluster_id` | str (uuid) |
| `organization_id` | str |
| `normalization_score` | float |
| `benchmark_weight` | float |
| `inclusion_reason` | str |
| `population_version` | int |

### finding_enforcement (352 rows) — bonus discovery
| Column | Observed Python Type |
|--------|---------------------|
| `finding_id` | str (uuid) |
| `enforcement_id` | str (uuid) |
| `similarity` | float |
