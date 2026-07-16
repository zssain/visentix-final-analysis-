# Visentix MVP — Schema Reference

**Updated:** 2026-06-16 (Phase 1)

This document describes every table added or extended in Phase 1 and its role in
the VICBNF intelligence pipeline.

---

## New Tables

### finding_type

Fixed catalog of finding codes. Each code maps to one privacy domain and carries
a default severity and regulator-relevance weights. The LLM never invents findings;
it selects from this catalog.

| Column                   | Type    | Notes                              |
|--------------------------|---------|------------------------------------|
| code                     | TEXT PK | e.g. "AI-004", "SH-002"           |
| title                    | TEXT    | Human-readable finding name        |
| default_severity         | TEXT    | "low" / "medium" / "high"         |
| domain                   | TEXT    | Links to disclosure_clause.category|
| regulator_relevance      | JSONB   | `{regulator_id: weight}` map       |
| linked_recommendation_id | TEXT    | Optional FK to recommendation      |
| sme_authored             | BOOLEAN | false = stub, true = SME-reviewed  |

**Lineage role:** Input catalog — consumed by the scoring engine and report generator.

---

### recommendation_library

Authored remediation templates, one or more per finding_type code. Templates contain
`{placeholder}` tokens filled at report-generation time with org-specific data.

| Column            | Type    | Notes                                   |
|-------------------|---------|-----------------------------------------|
| id                | UUID PK | Auto-generated                           |
| finding_type_code | TEXT FK | → finding_type(code)                     |
| severity_bucket   | TEXT    | Severity level this rec targets          |
| title             | TEXT    | Short recommendation title               |
| body_template     | TEXT    | Template with `{placeholders}`           |
| source_note       | TEXT    | Attribution / methodology note           |
| sme_authored      | BOOLEAN | false = stub, true = SME-reviewed        |
| version           | INTEGER | For versioned updates                    |

**Lineage role:** Output template — the report generator selects recommendations
by finding code + severity, then fills placeholders from computed data.

---

### exemplar

De-identified best/worst practice clause examples used for semantic similarity
search and maturity benchmarking. Each exemplar has a 384-dim embedding for
vector search against real clauses.

| Column              | Type        | Notes                               |
|---------------------|-------------|-------------------------------------|
| id                  | UUID PK     | Auto-generated                       |
| domain              | TEXT        | Privacy domain                       |
| category            | TEXT        | Clause category                      |
| clause_text         | TEXT        | De-identified example clause         |
| maturity_note       | TEXT        | SME assessment of maturity level     |
| source_internal_ref | TEXT        | Internal tracking reference          |
| embedding           | vector(384) | all-MiniLM-L6-v2 embedding           |
| sme_cleaned         | BOOLEAN     | false = stub, true = SME-reviewed    |

**Indexes:** `idx_exemplar_domain_category` (B-tree), `idx_exemplar_embedding_ivfflat`
(ivfflat, cosine distance).

**Lineage role:** Reference corpus — the embedding pipeline (Phase 3) compares
disclosure clauses against exemplars to assess maturity.

---

### organization_intelligence_profile

The 7-score organizational profile computed by the Normalization Engine (Phase 4).
Empty until Phase 4 populates it.

| Column           | Type        | Notes                                    |
|------------------|-------------|------------------------------------------|
| profile_id       | UUID PK     | Auto-generated                            |
| organization_id  | UUID        | → organization(organization_id)           |
| ic               | FLOAT8      | Intelligence Completeness                 |
| rss              | FLOAT8      | Regulatory Sensitivity Score              |
| pgms             | FLOAT8      | Privacy Governance Maturity Score         |
| osi              | FLOAT8      | Operational Sensitivity Index             |
| dsi              | FLOAT8      | Disclosure Sufficiency Index              |
| ehp              | FLOAT8      | Enforcement History Profile               |
| aigms            | FLOAT8      | AI Governance Maturity Score              |
| profile_version  | INTEGER     | Version counter for re-computation        |
| confidence_score | FLOAT8      | VCI confidence for this profile           |
| generated_at     | TIMESTAMPTZ | Computation timestamp                     |

**Lineage role:** Intermediate output — feeds the benchmark comparison and
normalization tiers that drive the final report scores.

---

### report_snapshot

Frozen report payload for reproducibility. Every published report writes a snapshot
so it can be regenerated identically from stored data.

| Column                       | Type        | Notes                          |
|------------------------------|-------------|--------------------------------|
| snapshot_id                  | UUID PK     | Auto-generated                  |
| organization_id              | UUID        | → organization                  |
| notice_id                    | UUID        | Optional — notice-level report  |
| payload                      | JSONB       | Full frozen report data         |
| formula_version_set          | JSONB       | All formula versions used       |
| benchmark_population_version | INTEGER     | Benchmark cohort version        |
| source_corpus_version        | INTEGER     | Source corpus version           |
| created_at                   | TIMESTAMPTZ | Snapshot creation time          |

**Lineage role:** Reproducibility anchor — every score and finding in a report
traces back to this snapshot.

---

## Extended Tables (columns added in Phase 1)

### risk_finding (+5 columns)

Pre-existing columns: `finding_id`, `severity`, `score`, `confidence_score`,
`formula_version_id`, `created_at`, `domain`.

| New Column        | Type        | Notes                                  |
|-------------------|-------------|----------------------------------------|
| organization_id   | UUID        | → organization                          |
| notice_id         | UUID        | → privacy_notice                        |
| finding_type_code | TEXT        | → finding_type(code)                    |
| snapshot_id       | UUID        | → report_snapshot                       |
| generated_at      | TIMESTAMPTZ | When this finding was computed           |

**Lineage role:** Connects a computed finding to its org, notice, catalog entry,
and reproducibility snapshot.

---

### clause_obligation (+2 columns)

Pre-existing columns: `clause_id`, `obligation_id`.

| New Column   | Type   | Notes                                  |
|--------------|--------|----------------------------------------|
| match_method | TEXT   | "embedding" / "keyword" / "manual"     |
| similarity   | FLOAT8 | Cosine similarity score of the match   |

**Lineage role:** M:M join with match provenance — traces which obligation
matched which clause and how.

---

### benchmark_membership (+4 columns)

Pre-existing columns: `cluster_id`, `organization_id` (30 rows unchanged).

| New Column         | Type    | Notes                                   |
|--------------------|---------|-----------------------------------------|
| normalization_score| FLOAT8  | Per-peer similarity weight               |
| benchmark_weight   | FLOAT8  | Weight in benchmark calculations         |
| inclusion_reason   | TEXT    | Why this org is in the benchmark cohort  |
| population_version | INTEGER | Version of the benchmark population      |

**Lineage role:** The Normalization Engine (Phase 4) writes these to record
per-peer weighting in benchmark comparisons.

---

### derived_data_item (+3 columns)

Pre-existing columns: `derived_data_item_id`, `object_type`, `organization_id`,
`notice_id`, `value`, `confidence_score`, `confidence_components`,
`formula_version_id`, `source_snapshot_id`, `benchmark_population_id`,
`generated_at`.

| New Column       | Type   | Notes                                  |
|------------------|--------|----------------------------------------|
| score            | FLOAT8 | Numeric score value                    |
| confidence_index | FLOAT8 | Composite confidence index             |
| source_lineage   | JSONB  | Full input reference chain             |

**Lineage role:** Generic derived-value store with full lineage — every computed
score records its formula version, inputs, and confidence.
