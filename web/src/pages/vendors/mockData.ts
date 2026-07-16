/**
 * F16 — Vendor Due Diligence Mode · MOCK DATA
 *
 * ┌──────────────────────────────────────────────────────────────────────────┐
 * │ REGISTERED MOCK (see visentix-specs/00-plan/mock-tracker.md):            │
 * │  M-28  Vendor queue + per-vendor procurement summary, findings, and      │
 * │        decision state. Real source: `vendor` + `vendor_review` tables    │
 * │        over real assessment output (risk_finding, scores), via the       │
 * │        vendor endpoints.                                                  │
 * └──────────────────────────────────────────────────────────────────────────┘
 *
 * GUARDRAIL (F16): EXPOSURE intelligence with evidence — never a verdict, and
 * never a Visentix-issued approval/clearance. The approve/decline decision is
 * the CUSTOMER's procurement action. All copy is scanned against the
 * banned-term list (AC-2).
 */

export type VendorStatus = "pending" | "approved" | "conditional" | "declined";
export type Criticality = "critical" | "high" | "standard";

export interface VendorSignal {
  code: string;        // finding-type family (navy chip)
  issue: string;
  snippet: string;     // clause-level evidence from the vendor's notice
  vci: number;
}

export interface Vendor {
  id: string;
  name: string;
  category: string;
  criticality: Criticality;
  domain: string;
  exposureScore: number;   // 0–100, higher = more exposure
  vci: number;
  cohortN: number;
  status: VendorStatus;
  submitted: string;
  summary: string;         // procurement-facing, exposure framing
  signals: VendorSignal[];
  conditions?: string;     // present when status = conditional
}

export const VENDORS: Vendor[] = [
  {
    id: "v-01", name: "Northstar Analytics", category: "Marketing analytics", criticality: "high",
    domain: "northstar-analytics.com", exposureScore: 74.1, vci: 84, cohortN: 38, status: "pending",
    submitted: "2026-07-14",
    summary: "This vendor processes behavioural data for a marketing use case. Its notice leaves the automated-profiling and third-party-sharing disclosures less specific than most peers in its cohort, which raises the exposure signal for a high-criticality integration.",
    signals: [
      { code: "AI-01", issue: "Automated decision-making", vci: 82, snippet: "We use algorithms to segment audiences and personalise campaigns; the notice does not describe a way to opt out of profiling." },
      { code: "SH-002", issue: "Third-party sharing", vci: 80, snippet: "Data may be shared with advertising partners; categories of partners are not enumerated." },
    ],
  },
  {
    id: "v-02", name: "Cirrus Cloud Storage", category: "Infrastructure", criticality: "critical",
    domain: "cirrus-cloud.com", exposureScore: 41.6, vci: 88, cohortN: 52, status: "approved",
    submitted: "2026-07-10",
    summary: "A critical-tier infrastructure vendor whose notice names concrete safeguards, specific retention periods, and a clear transfer mechanism. Exposure signals sit below its cohort median across most domains.",
    signals: [
      { code: "XB-01", issue: "International transfers", vci: 86, snippet: "Data is stored in named regions; the transfer mechanism relied upon is stated explicitly for each region." },
    ],
  },
  {
    id: "v-03", name: "Ledgerly Payments", category: "Payments", criticality: "critical",
    domain: "ledgerly.io", exposureScore: 58.9, vci: 79, cohortN: 44, status: "conditional",
    submitted: "2026-07-08",
    summary: "Payments vendor with generally specific disclosures, but its data-retention language is less defined than peers. The exposure signal is moderate; the gap is narrow and addressable.",
    signals: [
      { code: "RT-003", issue: "Data retention", vci: 77, snippet: "Transaction records are retained 'as long as required for business purposes'; no category-level periods are published." },
    ],
    conditions: "Proceed pending the vendor publishing category-level retention periods; re-review at renewal.",
  },
  {
    id: "v-04", name: "Beacon HR Suite", category: "HR / people data", criticality: "high",
    domain: "beacon-hr.com", exposureScore: 79.8, vci: 71, cohortN: 8, status: "declined",
    submitted: "2026-07-05",
    summary: "People-data vendor whose notice omits an automated-decision review path and leaves cross-border handling unstated. Exposure signals are high; note the small peer cohort reduces confidence in the benchmark position.",
    signals: [
      { code: "AI-01", issue: "Automated decision-making", vci: 70, snippet: "Automated tools support hiring and performance decisions; no human-review route is described." },
      { code: "XB-01", issue: "International transfers", vci: 68, snippet: "Processing locations are not named, and no transfer safeguard is referenced." },
    ],
  },
  {
    id: "v-05", name: "Quill Support Desk", category: "Customer support", criticality: "standard",
    domain: "quill-support.com", exposureScore: 47.2, vci: 83, cohortN: 27, status: "pending",
    submitted: "2026-07-13",
    summary: "Standard-tier support tool with mostly clear disclosures. One exposure signal: its cookie and tracking language presents an accept-first banner without an equally weighted decline.",
    signals: [
      { code: "TRK-007", issue: "Tracking", vci: 81, snippet: "The cookie banner offers 'Accept'; managing choices is available but presented in lower-contrast secondary styling." },
    ],
  },
];

export const STATUS_LABEL: Record<VendorStatus, string> = {
  pending: "Pending review",
  approved: "Approved",
  conditional: "Approved with conditions",
  declined: "Declined",
};
