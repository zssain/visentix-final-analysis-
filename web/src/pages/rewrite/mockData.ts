/**
 * F14 — Notice Rewrite Prompts (Trust Language Studio) · MOCK DATA
 *
 * ┌──────────────────────────────────────────────────────────────────────────┐
 * │ REGISTERED MOCK (see visentix-specs/00-plan/mock-tracker.md):            │
 * │  M-26  Rewrite prompts — per-domain gap status, current excerpt,         │
 * │        suggested language pattern, rationale, exemplar cohort n.         │
 * │        Real source: authored `rewrite_pattern` library + org clauses +   │
 * │        SME-approved `is_exemplar` patterns, via GET /api/rewrite.        │
 * └──────────────────────────────────────────────────────────────────────────┘
 *
 * GUARDRAILS (F14):
 *  - DESCRIPTIVE only — no verdict vocabulary from the banned-term list (AC-2).
 *  - No obligation framing — patterns describe how clearer peer notices tend to
 *    read, never what an organisation is obliged to do (AC-3 scans for that).
 *  - Patterns are authored / drawn from approved, de-identified exemplars —
 *    never LLM-invented, never raw peer text (Hard Rule 2 + 8).
 */

export type GapStatus = "missing" | "could_be_clearer" | "adequate";

export interface Prompt {
  domainId: string;
  domainName: string;
  status: GapStatus;
  currentExcerpt: string | null;   // null when the domain is not addressed
  pattern: string;                 // benchmark-informed language pattern
  rationale: string;               // plain-language "why it helps"
  cohortN: number;                 // exemplar cohort the pattern is drawn from
}

export const PROMPTS: Prompt[] = [
  {
    domainId: "AI", domainName: "Automated Decisions", status: "missing",
    currentExcerpt: null,
    pattern: "Where we use automated tools to make a decision that significantly affects you, we tell you before it happens, explain the main factors involved, and give you a way to ask a person to review it.",
    rationale: "Readers trust a notice more when the human-review path is named up front; clearer peer notices in this cohort describe it in plain terms rather than leaving it out.",
    cohortN: 34,
  },
  {
    domainId: "XB", domainName: "Cross-Border Transfers", status: "missing",
    currentExcerpt: null,
    pattern: "When we move your information to another country, we name the destination and the safeguard we rely on for that transfer.",
    rationale: "Naming both the destination and the safeguard reads as more transparent than a general statement that data 'may be processed abroad'.",
    cohortN: 21,
  },
  {
    domainId: "SH", domainName: "Sharing", status: "could_be_clearer",
    currentExcerpt: "We may share your information with third parties and partners to operate our services.",
    pattern: "We list each category of partner we share information with and, next to it, the reason for sharing and how to opt out.",
    rationale: "A named list with reasons reads as clearer and more trustworthy than a broad 'third parties and partners' phrase.",
    cohortN: 41,
  },
  {
    domainId: "RT", domainName: "Retention", status: "could_be_clearer",
    currentExcerpt: "We keep your information as long as necessary for the purposes described.",
    pattern: "We publish a short table listing each category of information and how long we keep it.",
    rationale: "Specific periods in a table read as more open than 'as long as necessary'; peer notices with a table score higher on clarity.",
    cohortN: 38,
  },
  {
    domainId: "TRK", domainName: "Tracking", status: "could_be_clearer",
    currentExcerpt: "By using our site you accept cookies. You can manage settings in your browser.",
    pattern: "Our cookie banner presents 'Accept' and 'Manage choices' with equal visual weight, and a one-click 'Reject all' is available.",
    rationale: "Balanced choices read as more respectful of the reader than an accept-first banner, and clearer peer notices tend to offer them.",
    cohortN: 7,   // small exemplar cohort → low-confidence label
  },
  {
    domainId: "CR", domainName: "Consumer Rights", status: "adequate",
    currentExcerpt: "You can access, correct, delete, or export your data, or appeal a decision, from the Privacy Center or by emailing privacy@…, and we respond within 30 days.",
    pattern: "Your current wording already names each right, gives a direct way to exercise it, and states a response time — this reads clearly.",
    rationale: "This domain already matches how the clearest peer notices phrase consumer rights; no change needed.",
    cohortN: 52,
  },
  {
    domainId: "SEC", domainName: "Security", status: "adequate",
    currentExcerpt: "We protect your information with encryption in transit and at rest, access controls, and a documented incident-response process.",
    pattern: "Your current wording names concrete safeguards and an incident process — this reads clearly.",
    rationale: "Naming specific measures reads as more credible than a generic 'we take security seriously', and your notice already does this.",
    cohortN: 44,
  },
];
