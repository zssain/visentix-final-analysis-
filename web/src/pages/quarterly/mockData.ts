/**
 * F12 — Quarterly Global Privacy Intelligence Report · MOCK DATA
 *
 * ┌──────────────────────────────────────────────────────────────────────────┐
 * │ REGISTERED MOCKS (see visentix-specs/00-plan/mock-tracker.md — pending    │
 * │ registration via the spec-update workflow):                               │
 * │  M-15  Publication snapshot + corpus stats (real: frozen publication      │
 * │        snapshot metadata — DIR-010). Cover counts are REAL counts from    │
 * │        the frozen snapshot, never the prototype's 1,250+/9.8M+ placeholder│
 * │        scale (F12 AC-5, Hard Rule 7). Mock values below are realistic     │
 * │        specific counts standing in for that snapshot.                     │
 * │  M-16  Intelligence Indicators (5 named indices + QoQ deltas). Real:      │
 * │        market-average aggregates per formula_version, each with VCI.      │
 * │  M-17  Section aggregates (rankings, regulator activity, AI governance,   │
 * │        disclosure trend, compound patterns). Real: corpus aggregation.    │
 * │  M-18  Benchmark Spotlight excerpts. Real: SME-approved + de-identified   │
 * │        exemplars above the minimum-sample threshold (F06 pipeline, AC-6). │
 * └──────────────────────────────────────────────────────────────────────────┘
 *
 * Guardrail note: all copy here is DESCRIPTIVE-ONLY (F12 AC-7). It states
 * observed movement ("continued rising"), never predictions/forecasts/verdicts.
 */

import type { MetricPolarity } from "../../lib/scoreBands";

/* ── Publication snapshot (M-15) ─────────────────────────────────────────── */

export interface PublicationMeta {
  quarter: string;          // human label, e.g. "Q2 2026"
  snapshotId: string;       // frozen publication snapshot id
  formulaVersions: string;  // formula version set frozen in this snapshot
  benchmarkVersion: string;
  cutoffDate: string;       // data cut-off (ISO-ish display)
  publishedDate: string;
  // Cover corpus stats — REAL counts from the frozen snapshot (AC-5).
  corpus: {
    organizations: number;
    industries: number;
    jurisdictions: number;
    clausesAnalyzed: number;
  };
}

export const PUBLICATION: PublicationMeta = {
  quarter: "Q2 2026",
  snapshotId: "QPUB-2026Q2-0007",
  formulaVersions: "F-002…F-014 v2.3",
  benchmarkVersion: "bench-2026Q2",
  cutoffDate: "2026-06-30",
  publishedDate: "2026-07-15",
  corpus: {
    organizations: 342,
    industries: 11,
    jurisdictions: 14,
    clausesAnalyzed: 48_910,
  },
};

/* ── Intelligence Indicators (M-16) ──────────────────────────────────────── */

export interface Indicator {
  key: string;
  name: string;
  value: number;            // 0–100 market average
  qoqDelta: number;         // change vs prior quarter (signed, in points)
  polarity: MetricPolarity; // maturity: higher = better · exposure: lower = better
  vci: number;              // Report Confidence Index for the aggregate (F-014)
  blurb: string;            // descriptive-only one-liner
}

/**
 * Five named market-average indices (F12 §2). Polarity is per-metric: the three
 * maturity indices read higher = better; Enforcement Sensitivity and Compound
 * Risk are exposure indices (higher = more exposure). This mix is deliberate —
 * it exercises both arms of the polarity rule (AC-8).
 */
export const INDICATORS: Indicator[] = [
  {
    key: "dmi", name: "Disclosure Maturity Index", value: 64.2, qoqDelta: +2.1,
    polarity: "maturity", vci: 88,
    blurb: "Average completeness of required disclosure elements across the corpus.",
  },
  {
    key: "ati", name: "AI Transparency Index", value: 41.7, qoqDelta: +5.4,
    polarity: "maturity", vci: 81,
    blurb: "How specifically notices address automated and AI-driven decision-making.",
  },
  {
    key: "crcs", name: "Consumer Rights Clarity Score", value: 58.9, qoqDelta: +0.8,
    polarity: "maturity", vci: 86,
    blurb: "Clarity and findability of data-subject rights and how to exercise them.",
  },
  {
    key: "esi", name: "Enforcement Sensitivity Index", value: 52.3, qoqDelta: +3.6,
    polarity: "exposure", vci: 79,
    blurb: "Overlap between observed disclosure gaps and historical enforcement themes.",
  },
  {
    key: "cri", name: "Compound Risk Index", value: 47.5, qoqDelta: -1.2,
    polarity: "exposure", vci: 83,
    blurb: "Concurrence of regulatory, disclosure, and enforcement exposure signals.",
  },
];

/* ── Section 2 · Key Quarterly Findings — 6 tiles (M-17) ──────────────────── */

export interface FindingTile {
  label: string;
  value: string;            // pre-formatted display value
  qoqDelta: number;         // signed points / percentage-points
  polarity: MetricPolarity;
  note: string;             // descriptive-only
}

export const KEY_FINDINGS: FindingTile[] = [
  { label: "Notices citing automated decision-making", value: "38%", qoqDelta: +6.0, polarity: "maturity", note: "Prevalence of any AI/ADM disclosure across the corpus." },
  { label: "Median disclosure-element completeness", value: "64%", qoqDelta: +2.1, polarity: "maturity", note: "Share of the required-element checklist present." },
  { label: "Notices with a clear rights-exercise path", value: "57%", qoqDelta: +0.8, polarity: "maturity", note: "A findable mechanism to exercise data-subject rights." },
  { label: "Dark-pattern consent gaps observed", value: "22%", qoqDelta: +3.1, polarity: "exposure", note: "Notices exhibiting at least one observed consent-friction pattern." },
  { label: "Cross-border transfer clarity", value: "49%", qoqDelta: +1.4, polarity: "maturity", note: "Notices naming transfer mechanisms and destinations." },
  { label: "Notices unchanged in 24+ months", value: "31%", qoqDelta: -2.0, polarity: "exposure", note: "Stale notices with no substantive revision in two years." },
];

/* ── Section 3 · Industry Benchmark Rankings (M-17) ───────────────────────── */

export interface IndustryRank {
  industry: string;
  dmi: number;      // Disclosure Maturity Index for the industry
  qoqDelta: number;
  cohortN: number;  // live cohort size — shown exactly (M-12 discipline); some < threshold
}

/** Sorted best→worst on entry; some cohorts sit below LOW_CONFIDENCE_COHORT_N. */
export const INDUSTRY_RANKINGS: IndustryRank[] = [
  { industry: "Financial Services", dmi: 74.8, qoqDelta: +1.9, cohortN: 52 },
  { industry: "Healthcare",         dmi: 71.2, qoqDelta: +2.4, cohortN: 38 },
  { industry: "Telecommunications", dmi: 68.5, qoqDelta: +0.6, cohortN: 21 },
  { industry: "Technology / SaaS",  dmi: 66.1, qoqDelta: +3.2, cohortN: 61 },
  { industry: "Retail & E-commerce",dmi: 61.4, qoqDelta: +1.1, cohortN: 44 },
  { industry: "Media & Publishing", dmi: 57.9, qoqDelta: -0.4, cohortN: 27 },
  { industry: "Travel & Hospitality",dmi: 54.3, qoqDelta: +0.9, cohortN: 19 },
  { industry: "Energy & Utilities", dmi: 51.7, qoqDelta: +1.6, cohortN: 12 },
  { industry: "Automotive",         dmi: 48.9, qoqDelta: +2.0, cohortN: 8 },  // < threshold → low-confidence
  { industry: "Public Sector",      dmi: 46.2, qoqDelta: -1.1, cohortN: 6 },  // < threshold → low-confidence
];

/* ── Section 4 · Regulator & Enforcement Intelligence (M-17) ──────────────── */

/**
 * Observed enforcement/guidance activity by regulator × theme.
 * Values are OBSERVED ACTIVITY COUNTS, not risk scores — rendered on a neutral
 * navy-intensity scale (not the red exposure scale) so color never reads as a
 * verdict. Descriptive-only.
 */
export const REGULATOR_THEMES = ["Dark patterns", "AI / ADM", "Data transfers", "Children's data", "Breach handling"] as const;

export interface RegulatorRow {
  regulator: string;
  activityDelta: number;              // QoQ change in total observed activity
  intensity: number[];                // per-theme observed activity, aligned to REGULATOR_THEMES
}

export const REGULATOR_ACTIVITY: RegulatorRow[] = [
  { regulator: "EU — EDPB / DPAs", activityDelta: +12, intensity: [9, 7, 8, 5, 6] },
  { regulator: "UK — ICO",         activityDelta: +5,  intensity: [6, 5, 4, 7, 5] },
  { regulator: "US — FTC",         activityDelta: +9,  intensity: [8, 6, 3, 6, 4] },
  { regulator: "US — State AGs",   activityDelta: +7,  intensity: [7, 4, 2, 3, 5] },
  { regulator: "CA — OPC",         activityDelta: +2,  intensity: [3, 3, 5, 2, 4] },
  { regulator: "APAC — Regional",  activityDelta: +4,  intensity: [4, 5, 6, 2, 3] },
];

export const REGULATOR_TOP_THEMES = [
  "Deceptive-design / consent friction drew the most new activity this quarter.",
  "AI and automated-decision guidance expanded across three major regulators.",
  "Cross-border transfer scrutiny continued at an elevated but steady level.",
];

/* ── Section 5 · AI Governance Intelligence (M-17) ────────────────────────── */

/** AIGMS / F-007 market-average trend line over the last six quarters. */
export const AI_GOVERNANCE_TREND: { quarter: string; index: number }[] = [
  { quarter: "Q1'25", index: 24.1 },
  { quarter: "Q2'25", index: 27.8 },
  { quarter: "Q3'25", index: 30.5 },
  { quarter: "Q4'25", index: 33.9 },
  { quarter: "Q1'26", index: 36.3 },
  { quarter: "Q2'26", index: 41.7 },
];

export const AI_DISCLOSURE_GAPS: { gap: string; prevalence: number }[] = [
  { gap: "No mention of automated decision-making at all", prevalence: 62 },
  { gap: "ADM named but no human-review pathway described", prevalence: 44 },
  { gap: "No reference to training-data sourcing or use", prevalence: 71 },
  { gap: "No opt-out or objection mechanism for profiling", prevalence: 53 },
];

/* ── Section 6 · Disclosure Trend Intelligence (M-17) ─────────────────────── */

export interface DomainTrend {
  domain: string;
  prevalence: number;   // % of corpus with adequate disclosure this quarter
  qoqDelta: number;     // percentage-point change QoQ
}

export const DISCLOSURE_TRENDS: DomainTrend[] = [
  { domain: "Automated decision-making", prevalence: 38, qoqDelta: +6.0 },
  { domain: "Data retention periods",    prevalence: 66, qoqDelta: +1.2 },
  { domain: "Third-party sharing",       prevalence: 59, qoqDelta: +0.4 },
  { domain: "International transfers",    prevalence: 49, qoqDelta: +1.4 },
  { domain: "Children's data handling",  prevalence: 33, qoqDelta: -0.6 },
  { domain: "Security measures",         prevalence: 71, qoqDelta: +0.9 },
];

/* ── Section 7 · High-Risk Disclosure Patterns (M-17) ─────────────────────── */

export interface CompoundPattern {
  code: string;         // finding-type family (navy chip)
  pattern: string;      // exposure framing, never an allegation
  prevalence: number;   // % of corpus exhibiting the compound pattern
}

export const COMPOUND_PATTERNS: CompoundPattern[] = [
  { code: "CR-04", pattern: "Broad data collection paired with an unclear retention window", prevalence: 18 },
  { code: "CR-07", pattern: "Third-party sharing disclosed without an opt-out mechanism", prevalence: 14 },
  { code: "CR-11", pattern: "Automated decisions referenced without a human-review pathway", prevalence: 11 },
  { code: "CR-02", pattern: "Consent friction combined with pre-ticked processing purposes", prevalence: 9 },
];

/* ── Section 8 · Benchmark Spotlight (M-18) ───────────────────────────────── */

export interface SpotlightExcerpt {
  domain: string;
  excerpt: string;      // de-identified, SME-approved exemplar language
  cohortN: number;      // must be ≥ suppression threshold to appear
}

/**
 * Only excerpts that passed SME de-id + approval AND sit above the minimum-sample
 * threshold may appear (AC-6). The reader page filters below-threshold rows and
 * shows a suppression notice, proving the rule visually.
 */
export const SPOTLIGHT_EXCERPTS: SpotlightExcerpt[] = [
  { domain: "Automated decision-making", cohortN: 34,
    excerpt: "Where we use automated tools to make a decision that significantly affects you, we tell you before it happens, explain the main factors involved, and give you a way to ask a person to review it." },
  { domain: "Data retention", cohortN: 41,
    excerpt: "We keep each category of information only for as long as the purpose requires, and we publish the specific retention period for every category in the table below." },
  { domain: "Consent (children)", cohortN: 7,  // below threshold → suppressed, not shown
    excerpt: "[suppressed — cohort below minimum sample]" },
];

/* ── Section 9 · Strategic Outlook (descriptive-only, AC-7) ───────────────── */

export const STRATEGIC_OUTLOOK: string[] = [
  "Enforcement activity around deceptive design and consent friction continued to rise through the quarter across multiple regulators.",
  "Disclosure of automated decision-making kept expanding, though a human-review pathway was still absent in most notices that mentioned it.",
  "Cross-border transfer language grew more specific, with more notices naming both the mechanism and the destination.",
  "The gap between the top and bottom industry cohorts on disclosure maturity narrowed slightly this quarter.",
];

/* ── Section 10 · Methodology (auto-generated from snapshot metadata) ─────── */

export const METHODOLOGY_FACTS: { label: string; value: string }[] = [
  { label: "Corpus size", value: `${PUBLICATION.corpus.organizations} organisations · ${PUBLICATION.corpus.clausesAnalyzed.toLocaleString()} clauses` },
  { label: "Industries / jurisdictions", value: `${PUBLICATION.corpus.industries} industries · ${PUBLICATION.corpus.jurisdictions} jurisdictions` },
  { label: "Benchmark populations", value: PUBLICATION.benchmarkVersion },
  { label: "Formula versions", value: PUBLICATION.formulaVersions },
  { label: "Data cut-off", value: PUBLICATION.cutoffDate },
  { label: "Publication snapshot", value: PUBLICATION.snapshotId },
];
