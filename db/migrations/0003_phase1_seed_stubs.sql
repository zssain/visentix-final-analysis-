-- Migration 0003: Phase 1 — Seed STUB rows for engineering unblock
-- Applied: 2026-06-16
-- All stubs are clearly flagged: sme_authored=false / sme_cleaned=false.
-- Real SME content replaces these later without schema change.
-- Uses ON CONFLICT DO NOTHING for idempotency.

-- ============================================================
-- finding_type stubs (8 rows covering each domain)
-- ============================================================
INSERT INTO finding_type (code, title, default_severity, domain, regulator_relevance, sme_authored)
VALUES
    ('AI-004',  'STUB — AI Transparency Gap',           'high',     'ai_automated_decisions',
     '{"FTC": 0.8, "CPPA": 0.7}'::jsonb, false),
    ('TRK-007', 'STUB — Tracking Disclosure Weakness',  'medium',   'tracking_cookies',
     '{"FTC": 0.7, "CPPA": 0.6}'::jsonb, false),
    ('SH-002',  'STUB — Data Sharing Exposure',         'high',     'data_sharing',
     '{"FTC": 0.9, "AG-CA": 0.8}'::jsonb, false),
    ('RT-003',  'STUB — Retention Period Omission',     'medium',   'retention',
     '{"FTC": 0.6, "CPPA": 0.7}'::jsonb, false),
    ('CR-001',  'STUB — Consumer Rights Gap',           'high',     'consumer_rights',
     '{"CPPA": 0.9, "AG-CA": 0.8}'::jsonb, false),
    ('DC-005',  'STUB — Disclosure Completeness Issue', 'medium',   'other',
     '{"FTC": 0.5}'::jsonb, false),
    ('SEC-002', 'STUB — Sensitive Data Handling Risk',  'high',     'sensitive_data',
     '{"FTC": 0.8, "HHS": 0.7}'::jsonb, false),
    ('XB-001',  'STUB — Cross-Border Transfer Gap',    'medium',   'cross_border',
     '{"FTC": 0.6, "EDPB": 0.9}'::jsonb, false)
ON CONFLICT (code) DO NOTHING;

-- ============================================================
-- recommendation_library stubs (1 per finding_type code)
-- ============================================================
INSERT INTO recommendation_library
    (finding_type_code, severity_bucket, title, body_template, source_note, sme_authored)
VALUES
    ('AI-004',  'high',   'STUB — Strengthen AI Transparency Disclosure',
     'Consider disclosing {ai_use_cases} and the logic involved in automated decision-making. STUB — replace with SME content.',
     'STUB — replace with SME content', false),
    ('TRK-007', 'medium', 'STUB — Enhance Tracking Technology Disclosure',
     'Consider specifying {tracking_technologies} used and their purposes. STUB — replace with SME content.',
     'STUB — replace with SME content', false),
    ('SH-002',  'high',   'STUB — Clarify Data Sharing Practices',
     'Consider enumerating {third_party_categories} and sharing purposes. STUB — replace with SME content.',
     'STUB — replace with SME content', false),
    ('RT-003',  'medium', 'STUB — Define Retention Periods',
     'Consider specifying retention periods for {data_categories}. STUB — replace with SME content.',
     'STUB — replace with SME content', false),
    ('CR-001',  'high',   'STUB — Expand Consumer Rights Section',
     'Consider detailing the process for exercising {consumer_rights}. STUB — replace with SME content.',
     'STUB — replace with SME content', false),
    ('DC-005',  'medium', 'STUB — Improve Disclosure Completeness',
     'Consider addressing {missing_elements} in the privacy notice. STUB — replace with SME content.',
     'STUB — replace with SME content', false),
    ('SEC-002', 'high',   'STUB — Sensitive Data Safeguards',
     'Consider disclosing safeguards for {sensitive_data_types}. STUB — replace with SME content.',
     'STUB — replace with SME content', false),
    ('XB-001',  'medium', 'STUB — Cross-Border Transfer Mechanisms',
     'Consider disclosing transfer mechanisms for {destination_countries}. STUB — replace with SME content.',
     'STUB — replace with SME content', false);

-- ============================================================
-- exemplar stubs (3 de-identified fake clauses)
-- ============================================================
INSERT INTO exemplar
    (domain, category, clause_text, maturity_note, source_internal_ref, sme_cleaned)
VALUES
    ('data_sharing', 'data_sharing',
     'STUB — [Company] may share your personal information with third-party service providers who assist us in operating our platform. STUB — replace with SME content.',
     'STUB maturity note: moderate — names categories but not specific entities.',
     'STUB-EXEMPLAR-001', false),
    ('ai_automated_decisions', 'ai_automated_decisions',
     'STUB — We use automated systems to personalize your experience. You may request human review of decisions. STUB — replace with SME content.',
     'STUB maturity note: high — discloses use and opt-out mechanism.',
     'STUB-EXEMPLAR-002', false),
    ('retention', 'retention',
     'STUB — We retain your data for as long as necessary to fulfill the purposes described in this notice. STUB — replace with SME content.',
     'STUB maturity note: low — no specific periods given.',
     'STUB-EXEMPLAR-003', false);
