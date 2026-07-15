# Phase 1 Migration Plan — Additive Schema Changes

**Date:** 2026-06-16
**Branch:** `phase-1-schema`
**Method:** Live introspection via Supabase REST API (anon key, read-only)

---

## Current State Summary

### Tables that ALREADY EXIST

| Table                | Rows | Current Columns |
|----------------------|-----:|-----------------|
| benchmark_membership | 30   | `cluster_id`, `organization_id` |
| derived_data_item    | 0    | `derived_data_item_id`, `object_type`, `organization_id`, `notice_id`, `value`, `confidence_score`, `confidence_components`, `formula_version_id`, `source_snapshot_id`, `benchmark_population_id`, `generated_at` |
| risk_finding         | 0    | `finding_id`, `severity`, `score`, `confidence_score`, `formula_version_id`, `created_at`, `domain` |
| finding_clause       | 0    | `finding_id`, `clause_id` |
| clause_obligation    | 0    | `clause_id`, `obligation_id` |
| finding_enforcement  | 0    | `finding_id`, `enforcement_id`, `similarity` |

### Tables that are MISSING (will be created)

| Table                                | Status  |
|--------------------------------------|---------|
| finding_type                         | MISSING |
| recommendation_library               | MISSING |
| exemplar                             | MISSING |
| organization_intelligence_profile    | MISSING |
| report_snapshot                      | MISSING |

---

## Migration Plan

All changes are **additive only** — new tables with `IF NOT EXISTS`, new nullable
columns with `ADD COLUMN IF NOT EXISTS`. No existing rows, tables, or columns
are altered or dropped.

### 1. CREATE TABLE `finding_type` (NEW)

```sql
CREATE TABLE IF NOT EXISTS finding_type (
    code         TEXT PRIMARY KEY,
    title        TEXT NOT NULL,
    default_severity TEXT NOT NULL DEFAULT 'medium',
    domain       TEXT NOT NULL,
    regulator_relevance JSONB,
    linked_recommendation_id TEXT
);
```

### 2. CREATE TABLE `recommendation_library` (NEW)

```sql
CREATE TABLE IF NOT EXISTS recommendation_library (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    finding_type_code TEXT NOT NULL REFERENCES finding_type(code),
    severity_bucket  TEXT NOT NULL,
    title            TEXT NOT NULL,
    body_template    TEXT NOT NULL,
    source_note      TEXT,
    sme_authored     BOOLEAN NOT NULL DEFAULT false,
    version          INTEGER NOT NULL DEFAULT 1
);
```

### 3. CREATE TABLE `exemplar` (NEW)

```sql
CREATE TABLE IF NOT EXISTS exemplar (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    domain              TEXT NOT NULL,
    category            TEXT NOT NULL,
    clause_text         TEXT NOT NULL,
    maturity_note       TEXT,
    source_internal_ref TEXT,
    embedding           vector(384),
    sme_cleaned         BOOLEAN NOT NULL DEFAULT false
);
```

### 4. ALTER TABLE `risk_finding` — ADD MISSING COLUMNS

Existing columns: `finding_id`, `severity`, `score`, `confidence_score`,
`formula_version_id`, `created_at`, `domain`.

Missing columns to add (all nullable, no existing rows affected):

```sql
ALTER TABLE risk_finding ADD COLUMN IF NOT EXISTS organization_id UUID;
ALTER TABLE risk_finding ADD COLUMN IF NOT EXISTS notice_id UUID;
ALTER TABLE risk_finding ADD COLUMN IF NOT EXISTS finding_type_code TEXT;
ALTER TABLE risk_finding ADD COLUMN IF NOT EXISTS snapshot_id UUID;
ALTER TABLE risk_finding ADD COLUMN IF NOT EXISTS generated_at TIMESTAMPTZ;
```

### 5. ALTER TABLE `clause_obligation` — ADD MISSING COLUMNS

Existing columns: `clause_id`, `obligation_id`.

Missing columns to add:

```sql
ALTER TABLE clause_obligation ADD COLUMN IF NOT EXISTS match_method TEXT;
ALTER TABLE clause_obligation ADD COLUMN IF NOT EXISTS similarity FLOAT8;
```

### 6. Tables `finding_clause` and `finding_enforcement` — NO CHANGES NEEDED

- `finding_clause` has: `finding_id`, `clause_id` — matches spec.
- `finding_enforcement` has: `finding_id`, `enforcement_id`, `similarity` — matches spec.

No columns need to be added.

### 7. CREATE TABLE `organization_intelligence_profile` (NEW)

```sql
CREATE TABLE IF NOT EXISTS organization_intelligence_profile (
    profile_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id   UUID NOT NULL,
    ic                FLOAT8,
    rss               FLOAT8,
    pgms              FLOAT8,
    osi               FLOAT8,
    dsi               FLOAT8,
    ehp               FLOAT8,
    aigms             FLOAT8,
    profile_version   INTEGER NOT NULL DEFAULT 1,
    confidence_score  FLOAT8,
    generated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### 8. ALTER TABLE `benchmark_membership` — ADD MISSING COLUMNS

Existing columns: `cluster_id`, `organization_id` (30 rows — NOT touched).

Missing columns to add (all nullable, existing rows get NULL):

```sql
ALTER TABLE benchmark_membership ADD COLUMN IF NOT EXISTS normalization_score FLOAT8;
ALTER TABLE benchmark_membership ADD COLUMN IF NOT EXISTS benchmark_weight FLOAT8;
ALTER TABLE benchmark_membership ADD COLUMN IF NOT EXISTS inclusion_reason TEXT;
ALTER TABLE benchmark_membership ADD COLUMN IF NOT EXISTS population_version INTEGER;
```

### 9. ALTER TABLE `derived_data_item` — ADD MISSING COLUMNS

Existing columns: `derived_data_item_id`, `object_type`, `organization_id`,
`notice_id`, `value`, `confidence_score`, `confidence_components`,
`formula_version_id`, `source_snapshot_id`, `benchmark_population_id`,
`generated_at`.

Missing columns to add:

```sql
ALTER TABLE derived_data_item ADD COLUMN IF NOT EXISTS score FLOAT8;
ALTER TABLE derived_data_item ADD COLUMN IF NOT EXISTS confidence_index FLOAT8;
ALTER TABLE derived_data_item ADD COLUMN IF NOT EXISTS source_lineage JSONB;
```

**Note:** The spec calls for `formula_version` but `formula_version_id` already
exists and serves the same purpose. Similarly, `confidence_index` is being added
alongside the existing `confidence_score` as they serve different roles (index =
composite, score = single value).

### 10. CREATE TABLE `report_snapshot` (NEW)

```sql
CREATE TABLE IF NOT EXISTS report_snapshot (
    snapshot_id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id            UUID NOT NULL,
    notice_id                  UUID,
    payload                    JSONB NOT NULL,
    formula_version_set        JSONB NOT NULL,
    benchmark_population_version INTEGER,
    source_corpus_version      INTEGER,
    created_at                 TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

---

## Change Summary

| Action | Target | Details |
|--------|--------|---------|
| CREATE | finding_type | 6 columns, new table |
| CREATE | recommendation_library | 8 columns, FK → finding_type |
| CREATE | exemplar | 8 columns, includes vector(384) |
| ALTER  | risk_finding | +5 nullable columns (0 rows, safe) |
| ALTER  | clause_obligation | +2 nullable columns (0 rows, safe) |
| NO-OP  | finding_clause | Already matches spec |
| NO-OP  | finding_enforcement | Already matches spec |
| CREATE | organization_intelligence_profile | 11 columns, new table |
| ALTER  | benchmark_membership | +4 nullable columns (30 rows get NULL) |
| ALTER  | derived_data_item | +3 nullable columns (0 rows, safe) |
| CREATE | report_snapshot | 7 columns, new table |

**Total: 5 new tables, 14 new nullable columns on 4 existing tables.**
**Zero existing rows or columns modified. Zero drops.**

---

## Awaiting Approval

This plan has NOT been applied. Waiting for human approval before writing the
migration SQL to `db/migrations/0001_phase1_schema.sql` and executing it.
