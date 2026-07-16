/**
 * F12 — Bulk Analysis workflow · MOCK DATA
 *
 * ┌──────────────────────────────────────────────────────────────────────────┐
 * │ REGISTERED MOCKS (see visentix-specs/00-plan/mock-tracker.md):            │
 * │  M-23  Bulk batch results — ranked company queue with exposure scores,   │
 * │        VCI, cohort n (real: batch pipeline over the aggregation layer     │
 * │        shared with M-17; scores from derived_data_item).                  │
 * │  M-24  Clause-level evidence snippets per flag (real: `disclosure_clause`│
 * │        rows + finding-type classification, with VCI).                     │
 * └──────────────────────────────────────────────────────────────────────────┘
 *
 * Guardrail (F12): bulk outputs are EXPOSURE intelligence with evidence
 * references — never allegations or verdicts. Every flag links to clause-level
 * evidence + VCI (AC-3). Honest cohort n; descriptive framing only.
 *
 * NOTE (Hard Rule 3): finding codes here are illustrative placeholders pending
 * the real `finding_type` catalog (only TRK-007 / SH-002 / RT-003 are confirmed
 * catalog codes). Real codes arrive with the M-23/M-24 backend; SME to verify.
 */

/* ── Persona modes (F12 §Bulk analysis) — contract-gated capability ──────── */

export interface PersonaMode {
  id: string;
  label: string;
  blurb: string;
}

export const PERSONA_MODES: PersonaMode[] = [
  { id: "regulator", label: "Regulator sector scan", blurb: "Heat map, outliers, and the gaps most common across the sector." },
  { id: "firm",      label: "Plaintiff-firm screen", blurb: "Rank targets by exposure signal; every flag carries clause-level evidence." },
  { id: "audit",     label: "Audit prospecting",     blurb: "Surface disclosure-maturity gaps across a prospect list." },
];

/* ── Issue filters ───────────────────────────────────────────────────────── */

export const ISSUE_FILTERS = [
  "Automated decision-making",
  "Data retention",
  "Third-party sharing",
  "International transfers",
  "Consent friction",
  "Children's data",
] as const;

/* ── Evidence snippet (M-24) ─────────────────────────────────────────────── */

export interface Evidence {
  code: string;        // finding-type family (navy chip)
  issue: string;       // matches an ISSUE_FILTERS entry
  snippet: string;     // clause-level excerpt from the target's public notice
  vci: number;         // confidence for this flag
}

/* ── Ranked company result (M-23) ────────────────────────────────────────── */

export interface CompanyResult {
  rank: number;
  company: string;
  industry: string;
  exposureScore: number;   // 0–100, higher = more exposure
  vci: number;             // Report Confidence Index for the company result
  cohortN: number;         // live cohort size for the industry benchmark
  topIssues: string[];     // issue labels (subset of ISSUE_FILTERS)
  evidence: Evidence[];    // clause-level evidence, one+ per flag (AC-3)
}

/**
 * A mock batch of 8 companies, pre-ranked by exposure (highest first).
 * Names are fictional. Scores/VCI/cohort are illustrative stand-ins for the
 * real batch pipeline output.
 */
export const BATCH_RESULTS: CompanyResult[] = [
  {
    rank: 1, company: "Aperture Retail Co.", industry: "Retail & E-commerce",
    exposureScore: 78.4, vci: 86, cohortN: 44,
    topIssues: ["Automated decision-making", "Consent friction"],
    evidence: [
      { code: "CR-11", issue: "Automated decision-making", vci: 84, snippet: "We may use automated systems to personalise offers and decisions about your account. The notice does not describe a way to request human review." },
      { code: "CR-02", issue: "Consent friction", vci: 81, snippet: "Marketing preferences are pre-selected at sign-up and can be changed later in settings." },
    ],
  },
  {
    rank: 2, company: "Brightline Media Group", industry: "Media & Publishing",
    exposureScore: 71.9, vci: 82, cohortN: 27,
    topIssues: ["Third-party sharing", "Data retention"],
    evidence: [
      { code: "CR-07", issue: "Third-party sharing", vci: 80, snippet: "We share data with advertising partners. The notice lists categories of partners but no mechanism to opt out of sharing." },
      { code: "CR-04", issue: "Data retention", vci: 78, snippet: "Information is retained 'as long as necessary'; no specific retention periods are published." },
    ],
  },
  {
    rank: 3, company: "Cirrus Health Partners", industry: "Healthcare",
    exposureScore: 64.2, vci: 88, cohortN: 38,
    topIssues: ["International transfers"],
    evidence: [
      { code: "CR-09", issue: "International transfers", vci: 85, snippet: "Data may be processed outside your country. The notice names neither the destinations nor the transfer mechanism relied upon." },
    ],
  },
  {
    rank: 4, company: "Delta SaaS Inc.", industry: "Technology / SaaS",
    exposureScore: 58.7, vci: 79, cohortN: 61,
    topIssues: ["Automated decision-making", "Data retention"],
    evidence: [
      { code: "CR-11", issue: "Automated decision-making", vci: 77, snippet: "Automated tooling assists moderation decisions; the appeal path is described only in the terms of service, not the privacy notice." },
    ],
  },
  {
    rank: 5, company: "Evergreen Financial", industry: "Financial Services",
    exposureScore: 52.1, vci: 84, cohortN: 52,
    topIssues: ["Consent friction"],
    evidence: [
      { code: "CR-02", issue: "Consent friction", vci: 82, snippet: "Cookie consent uses a prominent 'Accept all' with 'Manage' presented in lower-contrast secondary styling." },
    ],
  },
  {
    rank: 6, company: "Fathom Travel", industry: "Travel & Hospitality",
    exposureScore: 47.3, vci: 71, cohortN: 19,
    topIssues: ["Third-party sharing"],
    evidence: [
      { code: "CR-07", issue: "Third-party sharing", vci: 70, snippet: "Loyalty data is shared with partner airlines and hotels; the notice describes the purpose but not retention by those partners." },
    ],
  },
  {
    rank: 7, company: "Granite Public Utilities", industry: "Energy & Utilities",
    exposureScore: 41.0, vci: 63, cohortN: 12,
    topIssues: ["Data retention"],
    evidence: [
      { code: "CR-04", issue: "Data retention", vci: 62, snippet: "Meter and usage data retention is described in general terms; no category-level periods are given." },
    ],
  },
  {
    rank: 8, company: "Harbor Mutual Insurance", industry: "Insurance",
    exposureScore: 36.5, vci: 58, cohortN: 8,   // small cohort → low-confidence caution
    topIssues: ["Automated decision-making"],
    evidence: [
      { code: "CR-11", issue: "Automated decision-making", vci: 57, snippet: "Underwriting may use automated risk models; the notice acknowledges this but does not describe the main factors or a review route." },
    ],
  },
];

/* ── Regulator-mode sector aggregates (derived from the batch) ───────────── */

export const SECTOR_COMMON_GAPS: { issue: string; sharePct: number }[] = [
  { issue: "Data retention", sharePct: 50 },
  { issue: "Automated decision-making", sharePct: 50 },
  { issue: "Third-party sharing", sharePct: 38 },
  { issue: "Consent friction", sharePct: 38 },
  { issue: "International transfers", sharePct: 13 },
];
