-- Migration 0015: Explainability Reference table (VICBNF-007)
-- Links every derived intelligence object + finding to its source clauses,
-- benchmark population, regulators, and formula version with a plain rationale.
-- ADDITIVE ONLY.

CREATE TABLE IF NOT EXISTS explainability_reference (
    explainability_id       TEXT PRIMARY KEY,
    intelligence_id         TEXT,        -- derived_data_item_id or finding_id
    object_type             TEXT,        -- e.g. 'regulatory_exposure', finding code
    source_type             TEXT,        -- 'clause'|'benchmark'|'regulator'|'enforcement'|'formula'
    source_id               TEXT,
    clause_id               TEXT,
    regulator_id            TEXT,
    benchmark_population_id TEXT,
    formula_version         TEXT,
    rationale               TEXT,
    generated_at            TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_explain_ref_intel
    ON explainability_reference(intelligence_id);
CREATE INDEX IF NOT EXISTS idx_explain_ref_object_type
    ON explainability_reference(object_type);
