/**
 * F13 — Framework Crosswalk Explorer · MOCK DATA
 *
 * ┌──────────────────────────────────────────────────────────────────────────┐
 * │ REGISTERED MOCK (see visentix-specs/00-plan/mock-tracker.md):            │
 * │  M-25  Crosswalk mappings (domain/code → framework citation + note).     │
 * │        Real source: a `framework_reference` table + `finding_type`,      │
 * │        surfaced by GET /api/crosswalk. Descriptive copy needs OD-01      │
 * │        expert sign-off before the mock is replaced.                      │
 * └──────────────────────────────────────────────────────────────────────────┘
 *
 * GUARDRAIL (business-logic §2 / Hard Rule 1): every string here is
 * DESCRIPTIVE — "relates to / addresses / referenced by" only, never any
 * verdict vocabulary from the banned-term list. A unit test (F13 AC-4) scans
 * this dataset against scripts/data/banned_terms.txt.
 *
 * NOTE (Hard Rule 3): domain finding-code lists are illustrative placeholders
 * pending the real `finding_type` catalog (only TRK-007 / SH-002 / RT-003 are
 * confirmed catalog codes); the M-25 backend replaces them.
 */

export const FRAMEWORKS = [
  { id: "nist", name: "NIST Privacy Framework" },
  { id: "iso",  name: "ISO/IEC 27701" },
  { id: "gdpr", name: "GDPR" },
  { id: "ccpa", name: "CCPA / CPRA" },
] as const;

export type FrameworkId = (typeof FRAMEWORKS)[number]["id"];

/* The 8 disclosure domains (intelligence-logic.md §4) with representative
   finding codes (governed in the Codex / finding_type). */
export interface Domain {
  id: string;
  name: string;
  codes: string[];
}

export const DOMAINS: Domain[] = [
  { id: "CR",  name: "Consumer Rights",   codes: ["CR-01", "CR-04", "CR-07"] },
  { id: "DC",  name: "Data Collection",   codes: ["DC-02", "DC-05"] },
  { id: "SH",  name: "Sharing",           codes: ["SH-002", "SH-006"] },
  { id: "RT",  name: "Retention",         codes: ["RT-003", "RT-008"] },
  { id: "AI",  name: "Automated Decisions", codes: ["AI-01", "AI-04"] },
  { id: "SEC", name: "Security",          codes: ["SEC-02", "SEC-05"] },
  { id: "TRK", name: "Tracking",          codes: ["TRK-007", "TRK-011"] },
  { id: "XB",  name: "Cross-Border Transfers", codes: ["XB-01", "XB-03"] },
];

/* A mapping relates ONE domain (optionally one finding code) to ONE framework
   citation, with a descriptive note. code=null → domain-level reference. */
export interface Mapping {
  domainId: string;
  framework: FrameworkId;
  code: string | null;
  citation: string;
  note: string;   // descriptive-only
}

export const MAPPINGS: Mapping[] = [
  // Consumer Rights
  { domainId: "CR", framework: "ccpa", code: null,   citation: "CCPA §1798.100–.130", note: "Relates to the consumer rights to know, delete, correct, and opt out." },
  { domainId: "CR", framework: "ccpa", code: "CR-07", citation: "CCPA §1798.120", note: "Addresses the right to opt out of the sale or sharing of personal information." },
  { domainId: "CR", framework: "gdpr", code: null,   citation: "GDPR Arts. 15–22", note: "Relates to data-subject access, rectification, erasure, and objection rights." },
  { domainId: "CR", framework: "nist", code: null,   citation: "NIST PF · CONTROL-P", note: "Referenced by the Control-P function on data-processing management." },
  { domainId: "CR", framework: "iso",  code: null,   citation: "ISO 27701 §7.3", note: "Relates to obligations to data subjects." },

  // Data Collection
  { domainId: "DC", framework: "gdpr", code: null,   citation: "GDPR Arts. 5–6, 13", note: "Relates to lawfulness, data minimisation, and information at collection." },
  { domainId: "DC", framework: "ccpa", code: "DC-02", citation: "CCPA §1798.100(b)", note: "Addresses notice of categories collected at or before the point of collection." },
  { domainId: "DC", framework: "nist", code: null,   citation: "NIST PF · IDENTIFY-P", note: "Referenced by inventory and mapping of data processing." },
  { domainId: "DC", framework: "iso",  code: null,   citation: "ISO 27701 §7.2", note: "Relates to conditions for collection and processing." },

  // Sharing
  { domainId: "SH", framework: "ccpa", code: "SH-002", citation: "CCPA §1798.115", note: "Addresses disclosure of categories of third parties information is shared with." },
  { domainId: "SH", framework: "gdpr", code: null,   citation: "GDPR Art. 13(1)(e)", note: "Relates to disclosure of recipients or categories of recipients." },
  { domainId: "SH", framework: "iso",  code: null,   citation: "ISO 27701 §7.5", note: "Relates to sharing, transfer, and disclosure of PII." },
  // (no NIST mapping for SH — exercises the "no direct reference" cell)

  // Retention
  { domainId: "RT", framework: "gdpr", code: "RT-003", citation: "GDPR Art. 5(1)(e)", note: "Relates to storage limitation and defined retention periods." },
  { domainId: "RT", framework: "iso",  code: null,   citation: "ISO 27701 §7.4.7", note: "Relates to retention and disposal of PII." },
  { domainId: "RT", framework: "ccpa", code: null,   citation: "CCPA §1798.100(a)(3)", note: "Addresses disclosure of the retention period for each category." },

  // Automated Decisions
  { domainId: "AI", framework: "gdpr", code: "AI-01", citation: "GDPR Art. 22", note: "Relates to automated individual decision-making, including profiling." },
  { domainId: "AI", framework: "ccpa", code: null,   citation: "CPRA ADMT rulemaking", note: "Referenced by the CPRA rulemaking on automated decision-making technology." },
  { domainId: "AI", framework: "nist", code: null,   citation: "NIST PF · CONTROL-P", note: "Referenced by data-processing management for automated activities." },

  // Security
  { domainId: "SEC", framework: "gdpr", code: null,  citation: "GDPR Arts. 32–34", note: "Relates to security of processing and breach notification." },
  { domainId: "SEC", framework: "iso",  code: "SEC-02", citation: "ISO 27701 §6.x (with ISO 27001)", note: "Relates to information-security controls applied to PII." },
  { domainId: "SEC", framework: "nist", code: null,  citation: "NIST PF · PROTECT-P", note: "Referenced by the Protect-P data-protection function." },

  // Tracking
  { domainId: "TRK", framework: "ccpa", code: "TRK-007", citation: "CCPA §1798.135", note: "Addresses opt-out preference signals and the sharing of tracking data." },
  { domainId: "TRK", framework: "gdpr", code: null,  citation: "GDPR Art. 7 + ePrivacy", note: "Relates to consent for cookies and similar tracking technologies." },
  // (no NIST / ISO domain-level mapping — more "no direct reference" cells)

  // Cross-Border Transfers
  { domainId: "XB", framework: "gdpr", code: "XB-01", citation: "GDPR Arts. 44–49", note: "Relates to conditions and safeguards for international transfers." },
  { domainId: "XB", framework: "iso",  code: null,  citation: "ISO 27701 §7.5.1", note: "Relates to identifying the basis for transfers between jurisdictions." },
  { domainId: "XB", framework: "ccpa", code: null,  citation: "CCPA (no specific transfer regime)", note: "Referenced only generally; CCPA has no dedicated cross-border transfer article." },
];

/** All mappings for a given domain + framework (domain-level first, then codes). */
export function cellMappings(domainId: string, framework: FrameworkId): Mapping[] {
  return MAPPINGS
    .filter(m => m.domainId === domainId && m.framework === framework)
    .sort((a, b) => (a.code === null ? -1 : b.code === null ? 1 : a.code.localeCompare(b.code)));
}
