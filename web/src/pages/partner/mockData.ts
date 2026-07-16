/**
 * F11 — White-Label Portal & Intelligence APIs · MOCK DATA
 *
 * ┌──────────────────────────────────────────────────────────────────────────┐
 * │ REGISTERED MOCKS (see visentix-specs/00-plan/mock-tracker.md):            │
 * │  M-19  Partner contract + client workspaces (real: `partner`,            │
 * │        `client_workspace` tables + live usage per DIR-005 isolation).    │
 * │  M-20  API keys + per-contract usage/rate limits (real: `api_key`,       │
 * │        `usage_record` metering).                                          │
 * │  M-21  Anonymized feed catalog (real: `feed_snapshot` aggregates with    │
 * │        min-sample suppression, DIR-006; confidence metadata mandatory).  │
 * │  M-22  Branding config + report templates (real: partner branding store  │
 * │        applied to the report template engine).                           │
 * └──────────────────────────────────────────────────────────────────────────┘
 *
 * Guardrail: partner-branded narratives obey the SAME banned-term rules as
 * customer output; no customer-specific traceability leaves the platform; every
 * feed record carries confidence metadata + permitted-use restrictions.
 */

/* ── Partner contract / licensing (M-19) ─────────────────────────────────── */

export interface PartnerContract {
  partnerName: string;
  tier: string;            // business-logic §3 Product 3 = T3
  workspaceLimit: number;
  apiCallLimit: number;    // per billing period
  apiCallsUsed: number;
  periodEnds: string;
}

export const CONTRACT: PartnerContract = {
  partnerName: "Meridian Privacy Advisors",
  tier: "White-Label · T3",
  workspaceLimit: 10,
  apiCallLimit: 100_000,
  apiCallsUsed: 91_240,   // deliberately near limit → exercises the quota-caution state
  periodEnds: "2026-07-31",
};

/* ── Client workspaces (M-19) — partner sees ONLY its own (DIR-005) ──────── */

export interface Workspace {
  id: string;
  clientName: string;
  industry: string;
  assessments: number;
  lastActivity: string;
  branded: boolean;        // has the partner's branding applied
  status: "active" | "paused";
}

export const WORKSPACES: Workspace[] = [
  { id: "ws-01", clientName: "Northwind Retail Group", industry: "Retail & E-commerce", assessments: 24, lastActivity: "2026-07-15", branded: true,  status: "active" },
  { id: "ws-02", clientName: "Corestone Financial",    industry: "Financial Services",  assessments: 41, lastActivity: "2026-07-14", branded: true,  status: "active" },
  { id: "ws-03", clientName: "Vantage Health Systems",  industry: "Healthcare",          assessments: 17, lastActivity: "2026-07-11", branded: true,  status: "active" },
  { id: "ws-04", clientName: "Lumen SaaS",              industry: "Technology / SaaS",   assessments: 8,  lastActivity: "2026-06-29", branded: false, status: "paused" },
];

/* ── Branding config (M-22) ──────────────────────────────────────────────── */

export interface Branding {
  logoLabel: string;       // stand-in for an uploaded asset
  primary: string;         // hex
  accent: string;          // hex
  reportFooter: string;
}

export const BRANDING: Branding = {
  logoLabel: "MERIDIAN",
  primary: "#1F3A5F",
  accent: "#C99A3B",
  reportFooter: "Prepared by Meridian Privacy Advisors · Intelligence by Visentix",
};

/* ── API keys + usage metering (M-20) ────────────────────────────────────── */

export interface ApiKey {
  id: string;
  label: string;
  maskedKey: string;
  scope: string;           // which Intelligence API surface
  rateLimit: string;       // human-readable
  callsThisPeriod: number;
  callLimit: number;
  status: "active" | "expired";
}

export const API_KEYS: ApiKey[] = [
  { id: "k1", label: "Production — Profile API",       maskedKey: "vsx_live_••••••••4a2f", scope: "Organization Profile", rateLimit: "60 req/min", callsThisPeriod: 42_180, callLimit: 50_000, status: "active" },
  { id: "k2", label: "Production — Classification API", maskedKey: "vsx_live_••••••••9c71", scope: "Notice Classification", rateLimit: "60 req/min", callsThisPeriod: 38_902, callLimit: 40_000, status: "active" },  // near limit
  { id: "k3", label: "Sandbox — Benchmark API",         maskedKey: "vsx_test_••••••••0e15", scope: "Benchmark Population", rateLimit: "20 req/min", callsThisPeriod: 10_158, callLimit: 50_000, status: "active" },
  { id: "k4", label: "Legacy — Explainability API",     maskedKey: "vsx_live_••••••••bb30", scope: "Explainability",       rateLimit: "30 req/min", callsThisPeriod: 0,       callLimit: 50_000, status: "expired" },
];

/* The Intelligence API suite (F11 §2 / VICBNF §14) — every payload carries
   VCI + formula_version + explainability refs where permitted. */
export const API_SURFACES = [
  { name: "Organization Profile API", desc: "Firmographic + normalized profile signals for an organisation." },
  { name: "Notice Classification API", desc: "Clause decomposition and finding-type classification for a notice." },
  { name: "Benchmark Population API",  desc: "Cohort membership and percentile position, with honest cohort n." },
  { name: "Derived Intelligence API",  desc: "Scores and findings as versioned derived_data_items with lineage." },
  { name: "Explainability API",        desc: "Formula id, plain-English description, inputs, and VCI for any score." },
  { name: "White-Label Feed API",      desc: "Anonymized aggregate feeds: dataset_id, schema_version, refresh_date, permitted_use, confidence." },
];

/* ── Anonymized feed catalog (M-21) ──────────────────────────────────────── */

export interface Feed {
  datasetId: string;
  name: string;
  schemaVersion: string;
  refreshDate: string;
  permittedUse: string;
  cohortN: number;          // aggregate sample size behind the feed
  vci: number;              // confidence metadata (mandatory)
  suppressed: boolean;      // below minimum-sample threshold (DIR-006)
}

export const FEEDS: Feed[] = [
  { datasetId: "feed-benchmark-2026Q2", name: "Industry Benchmark Averages", schemaVersion: "v2.1", refreshDate: "2026-07-01", permittedUse: "Benchmarking & internal analysis · no redistribution", cohortN: 342, vci: 88, suppressed: false },
  { datasetId: "feed-regulator-trends", name: "Regulator Activity Trends",    schemaVersion: "v1.4", refreshDate: "2026-07-01", permittedUse: "Editorial & advisory use with attribution",       cohortN: 210, vci: 82, suppressed: false },
  { datasetId: "feed-ai-maturity",      name: "AI Governance Maturity Index", schemaVersion: "v1.0", refreshDate: "2026-07-01", permittedUse: "Benchmarking & internal analysis · no redistribution", cohortN: 156, vci: 79, suppressed: false },
  { datasetId: "feed-sector-niche",     name: "Niche Sector Signals",          schemaVersion: "v0.9", refreshDate: "2026-07-01", permittedUse: "Restricted preview",                             cohortN: 6,   vci: 0,  suppressed: true },  // below min sample → suppressed
];

/* ── Report template engine (M-22) ───────────────────────────────────────── */

export interface ReportTemplate {
  id: string;
  name: string;
  desc: string;
}

export const TEMPLATES: ReportTemplate[] = [
  { id: "assessment", name: "Branded Assessment",  desc: "The full 12-section report under the partner's brand." },
  { id: "memo",       name: "Legal Memo",          desc: "Narrative memo format for counsel — exposure and maturity framing." },
  { id: "board",      name: "Board Deck",          desc: "Executive slide summary: headline scores, cohort position, trend." },
  { id: "export",     name: "Data Export",         desc: "Structured derived_data_items with lineage for the client's own systems." },
];
