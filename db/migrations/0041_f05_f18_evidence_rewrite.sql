-- Migration 0041: F05 addendum (recommendation evidence stacks) + F18 (clause
-- rewrite). ADDITIVE ONLY. Idempotent.
--
-- F05: evidence assembled at APPROVAL/FREEZE and stored here once — the frozen
-- artifact (DIR-010 byte-identity). risk_reduction_delta is NULL forever (no
-- formula in intelligence-logic — never invented).
-- F18: one row per rewrite attempt; a rewrite is only surfaced when BOTH
-- guardrail_passed AND verification_passed; otherwise fallback_used=true.

CREATE TABLE IF NOT EXISTS recommendation_evidence (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    finding_id          UUID REFERENCES risk_finding(finding_id),
    assessment_id       UUID NOT NULL REFERENCES privacy_notice(notice_id),
    obligation_refs     JSONB,      -- [{obligation_id, similarity, matched_terms, law, requirement_type, jurisdiction, verified}]
    exemplar_clause_id  UUID REFERENCES disclosure_clause(clause_id),  -- SME-approved only; NULL = honest absence
    enforcement_refs    JSONB,      -- [{enforcement_id, regulator, year, similarity}] — resolved only, max 2
    absence_reason      TEXT,       -- one of: out_of_scope | below_floor | no_approved_exemplar (or NULL)
    risk_reduction_delta NUMERIC,   -- NULL FOREVER (no formula exists — never computed)
    formula_version_id  TEXT,
    confidence          NUMERIC,
    generated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- One evidence row per (assessment, finding) — the freeze is idempotent.
CREATE UNIQUE INDEX IF NOT EXISTS uq_rec_evidence_finding
    ON recommendation_evidence (assessment_id, finding_id);
CREATE INDEX IF NOT EXISTS idx_rec_evidence_assessment ON recommendation_evidence (assessment_id);

CREATE TABLE IF NOT EXISTS clause_rewrite (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    assessment_id       UUID NOT NULL REFERENCES privacy_notice(notice_id),
    clause_id           UUID NOT NULL REFERENCES disclosure_clause(clause_id),
    model_version       TEXT,
    prompt_version      TEXT,
    guardrail_passed    BOOLEAN NOT NULL DEFAULT false,
    verification_passed BOOLEAN NOT NULL DEFAULT false,
    suggested_text      TEXT,       -- NULL when fallback used
    fallback_used       BOOLEAN NOT NULL DEFAULT false,
    diff                JSONB,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_clause_rewrite_assessment ON clause_rewrite (assessment_id, clause_id);
