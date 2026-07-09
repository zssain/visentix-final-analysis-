-- Migration 0016: Legal Reference + Finding-Legal-Reference junction
-- Real, verifiable citations for each finding domain.
-- ADDITIVE ONLY.

CREATE TABLE IF NOT EXISTS legal_reference (
    reference_id    TEXT PRIMARY KEY,
    jurisdiction    TEXT NOT NULL,
    framework       TEXT NOT NULL,
    citation        TEXT NOT NULL,
    title           TEXT NOT NULL,
    summary         TEXT,
    official_url    TEXT NOT NULL,
    domain_id       TEXT,          -- CR/DC/SH/RT/AI/SEC/TRK/XB
    clause_type     TEXT,
    last_verified   DATE,
    sme_authored    BOOLEAN NOT NULL DEFAULT false
);

CREATE TABLE IF NOT EXISTS finding_legal_reference (
    finding_type_code TEXT NOT NULL,
    reference_id      TEXT NOT NULL REFERENCES legal_reference(reference_id),
    is_primary        BOOLEAN NOT NULL DEFAULT false,
    rationale         TEXT,
    PRIMARY KEY (finding_type_code, reference_id)
);

-- ============================================================
-- Seed real, verifiable legal citations
-- ============================================================

-- Consumer Rights (CR)
INSERT INTO legal_reference VALUES
('LR-CCPA-100', 'US-CA', 'CCPA/CPRA', 'Cal. Civ. Code §1798.100', 'Right to Know', 'Consumers have the right to know what personal information is collected.', 'https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?sectionNum=1798.100.&lawCode=CIV', 'CR', 'Access', '2026-07-01', false),
('LR-CCPA-105', 'US-CA', 'CCPA/CPRA', 'Cal. Civ. Code §1798.105', 'Right to Delete', 'Consumers have the right to request deletion of personal information.', 'https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?sectionNum=1798.105.&lawCode=CIV', 'CR', 'Delete', '2026-07-01', false),
('LR-CCPA-106', 'US-CA', 'CCPA/CPRA', 'Cal. Civ. Code §1798.106', 'Right to Correct', 'Consumers have the right to correct inaccurate personal information.', 'https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?sectionNum=1798.106.&lawCode=CIV', 'CR', 'Correct', '2026-07-01', false),
('LR-CCPA-120', 'US-CA', 'CCPA/CPRA', 'Cal. Civ. Code §1798.120', 'Right to Opt-Out of Sale', 'Right to opt out of the sale or sharing of personal information.', 'https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?sectionNum=1798.120.&lawCode=CIV', 'CR', 'Opt-Out', '2026-07-01', false),
('LR-GDPR-15', 'EU', 'GDPR', 'GDPR Art. 15', 'Right of Access', 'Data subjects have the right to obtain confirmation and access to their data.', 'https://gdpr-info.eu/art-15-gdpr/', 'CR', 'Access', '2026-07-01', false),
('LR-GDPR-17', 'EU', 'GDPR', 'GDPR Art. 17', 'Right to Erasure', 'Data subjects have the right to have their personal data erased.', 'https://gdpr-info.eu/art-17-gdpr/', 'CR', 'Delete', '2026-07-01', false),
('LR-GDPR-21', 'EU', 'GDPR', 'GDPR Art. 21', 'Right to Object', 'Data subjects have the right to object to processing.', 'https://gdpr-info.eu/art-21-gdpr/', 'CR', 'Opt-Out', '2026-07-01', false)
ON CONFLICT (reference_id) DO NOTHING;

-- Data Sharing (SH)
INSERT INTO legal_reference VALUES
('LR-CCPA-SH-120', 'US-CA', 'CCPA/CPRA', 'Cal. Civ. Code §1798.120', 'Opt-Out of Sale/Sharing', 'Right to opt out of sale or sharing of PI with third parties.', 'https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?sectionNum=1798.120.&lawCode=CIV', 'SH', 'Service Providers', '2026-07-01', false),
('LR-GDPR-13e', 'EU', 'GDPR', 'GDPR Art. 13(1)(e)', 'Recipients of Personal Data', 'Controller must inform data subjects of recipients or categories of recipients.', 'https://gdpr-info.eu/art-13-gdpr/', 'SH', 'Service Providers', '2026-07-01', false)
ON CONFLICT (reference_id) DO NOTHING;

-- Tracking (TRK)
INSERT INTO legal_reference VALUES
('LR-EPRIVACY-5', 'EU', 'ePrivacy Directive', 'ePrivacy Directive Art. 5(3)', 'Consent for Cookies', 'Storage of or access to information on terminal equipment requires informed consent.', 'https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32002L0058', 'TRK', 'Cookies', '2026-07-01', false),
('LR-FTC-5', 'US-FED', 'FTC Act', 'FTC Act §5', 'Unfair or Deceptive Acts', 'Prohibits unfair or deceptive acts or practices in or affecting commerce.', 'https://www.ftc.gov/legal-library/browse/statutes/federal-trade-commission-act', 'TRK', 'Cookies', '2026-07-01', false)
ON CONFLICT (reference_id) DO NOTHING;

-- AI Governance (AI)
INSERT INTO legal_reference VALUES
('LR-CPRA-ADMT', 'US-CA', 'CCPA/CPRA', 'CPRA ADMT Regulations', 'Automated Decision-Making Technology', 'CPRA regulations require disclosure and opt-out for automated decision-making.', 'https://cppa.ca.gov/regulations/', 'AI', 'Automated Decisions', '2026-07-01', false),
('LR-GDPR-22', 'EU', 'GDPR', 'GDPR Art. 22', 'Automated Individual Decision-Making', 'Right not to be subject to solely automated decisions with legal or significant effects.', 'https://gdpr-info.eu/art-22-gdpr/', 'AI', 'Automated Decisions', '2026-07-01', false)
ON CONFLICT (reference_id) DO NOTHING;

-- Retention (RT)
INSERT INTO legal_reference VALUES
('LR-CPRA-RT', 'US-CA', 'CCPA/CPRA', 'Cal. Civ. Code §1798.100(a)(3)', 'Retention Period Disclosure', 'Businesses must disclose the length of time they intend to retain each category of PI.', 'https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?sectionNum=1798.100.&lawCode=CIV', 'RT', 'Specific Period', '2026-07-01', false),
('LR-GDPR-5e', 'EU', 'GDPR', 'GDPR Art. 5(1)(e)', 'Storage Limitation', 'Personal data must not be kept longer than necessary for the purpose.', 'https://gdpr-info.eu/art-5-gdpr/', 'RT', 'Specific Period', '2026-07-01', false)
ON CONFLICT (reference_id) DO NOTHING;

-- Sensitive Data (DC)
INSERT INTO legal_reference VALUES
('LR-CPRA-121', 'US-CA', 'CCPA/CPRA', 'Cal. Civ. Code §1798.121', 'Limit Use of Sensitive PI', 'Consumers can limit the use and disclosure of sensitive personal information.', 'https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?sectionNum=1798.121.&lawCode=CIV', 'DC', 'Sensitive Information', '2026-07-01', false),
('LR-GDPR-9', 'EU', 'GDPR', 'GDPR Art. 9', 'Special Categories of Data', 'Processing of special categories such as health, biometric, racial data requires explicit consent.', 'https://gdpr-info.eu/art-9-gdpr/', 'DC', 'Sensitive Information', '2026-07-01', false)
ON CONFLICT (reference_id) DO NOTHING;

-- Cross-Border (XB)
INSERT INTO legal_reference VALUES
('LR-GDPR-44', 'EU', 'GDPR', 'GDPR Arts. 44-49', 'Transfers to Third Countries', 'Transfers of personal data to third countries require adequate safeguards.', 'https://gdpr-info.eu/art-44-gdpr/', 'XB', 'Transfers', '2026-07-01', false)
ON CONFLICT (reference_id) DO NOTHING;

-- ============================================================
-- Finding → Legal Reference junctions
-- ============================================================
INSERT INTO finding_legal_reference VALUES
('CR-001', 'LR-CCPA-100', true, 'CCPA right to know is the primary US framework for consumer access rights.'),
('CR-001', 'LR-GDPR-15', false, 'GDPR right of access applies to EU data subjects.'),
('CR-001', 'LR-CCPA-105', false, 'CCPA right to delete is a component of consumer rights.'),
('SH-002', 'LR-CCPA-SH-120', true, 'CCPA opt-out of sale/sharing governs data sharing disclosures.'),
('SH-002', 'LR-GDPR-13e', false, 'GDPR requires disclosure of recipients.'),
('TRK-007', 'LR-EPRIVACY-5', true, 'ePrivacy Art 5(3) is the primary EU cookie consent requirement.'),
('TRK-007', 'LR-FTC-5', false, 'FTC Act Section 5 covers deceptive tracking practices in the US.'),
('RT-003', 'LR-CPRA-RT', true, 'CPRA requires disclosure of retention periods by category.'),
('RT-003', 'LR-GDPR-5e', false, 'GDPR storage limitation principle.'),
('AI-004', 'LR-CPRA-ADMT', true, 'CPRA ADMT regulations require automated decision-making disclosure.'),
('AI-004', 'LR-GDPR-22', false, 'GDPR Art 22 right regarding automated decisions.'),
('SEC-002', 'LR-CPRA-121', true, 'CPRA requires controls for sensitive personal information.'),
('SEC-002', 'LR-GDPR-9', false, 'GDPR Art 9 governs special categories of data.'),
('XB-001', 'LR-GDPR-44', true, 'GDPR Chapter V governs international transfers.'),
('DC-005', 'LR-CCPA-100', true, 'CCPA right to know covers disclosure completeness.')
ON CONFLICT (finding_type_code, reference_id) DO NOTHING;
