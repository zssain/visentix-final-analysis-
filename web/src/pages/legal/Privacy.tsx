import { LegalPage, type LegalSection } from "./LegalPage";

// DRAFT — founder approves wording in-session before this ships. See
// deploy/legal/visentix-privacy-notice.txt for the plain-text copy that is run
// through our own pipeline ("eat our own cooking"; scores go in the PR body).
const EFFECTIVE = "28 July 2026";

const SECTIONS: LegalSection[] = [
  {
    heading: "Who we are",
    body: [
      "Visentix provides privacy-intelligence analysis: we read published privacy notices and score how clearly and completely they disclose data practices, benchmarked against peers. We are the data controller for the account and usage data described below.",
      "Visentix produces intelligence and exposure signals. It does not provide legal advice and does not make compliance determinations.",
    ],
  },
  {
    heading: "What we collect",
    body: [
      "Account information: your name, email address, organisation name, and role. This is what you or your administrator provide when an account is created.",
      "Submitted notices and files: the privacy notices, documents, and URLs you submit for analysis, and the text and scores we derive from them. If you paste or upload a document, we store that document and its analysis so reports are reproducible.",
      "Usage logs: audit and access logs — who did what and when (sign-ins, submissions, report views, approvals), along with technical metadata such as timestamps and IP address, kept for security and troubleshooting.",
      "We do not use tracking cookies for advertising. We use a single first-party session token to keep you signed in.",
    ],
  },
  {
    heading: "How we use it",
    body: [
      "To run the analysis you request, generate reports, and let a subject-matter expert review findings before a report is delivered.",
      "To secure the service, investigate misuse, keep an audit trail, and meet our own record-keeping obligations.",
      "To operate your account and communicate with you about the service (including alert emails you or your administrator enable).",
      "We do not use your submitted notices to train third-party AI models. Classification and scoring run on models we operate on our own infrastructure.",
    ],
  },
  {
    heading: "Who we share it with (subprocessors)",
    body: [
      "We keep the list of subprocessors short and name them plainly:",
      "• Supabase — managed PostgreSQL database that stores account data, submitted notices, and derived scores.",
      "• RunPod — GPU compute that runs the analysis models (classification, embeddings) and the API.",
      "• Cloudflare — hosting and delivery of the web application.",
      "• Our email provider (SMTP) — sends transactional and alert emails when enabled.",
      "Each processes data only on our instructions to run the service. We do not sell your personal data, and we do not share it for advertising.",
    ],
  },
  {
    heading: "How long we keep it",
    body: [
      "Account data: for as long as your account is active, and then deleted or anonymised within 90 days of account closure unless we must keep it longer for legal or security reasons.",
      "Submitted notices and derived reports: kept for the life of the account so reports remain reproducible; deleted on request or on account closure, subject to the same legal-hold exception.",
      "Usage and audit logs: retained up to 12 months, then deleted or aggregated.",
    ],
  },
  {
    heading: "Your rights",
    body: [
      "You can ask us to access, correct, export, or delete your personal data, and to restrict or object to certain processing. Email privacy@visentix.ai and we will respond within a reasonable time and within any period the law requires.",
      "If your account was created by an organisation administrator, some requests may be routed through that administrator.",
    ],
  },
  {
    heading: "Security",
    body: [
      "Data is encrypted in transit (TLS). Access to production data is role-based and limited to what each role needs; tenants are isolated so one customer cannot read another's data. Secrets are held in environment configuration, never in our source code.",
    ],
  },
  {
    heading: "International transfers",
    body: [
      "Our subprocessors may process data in regions outside your own. Where required, transfers rely on appropriate safeguards such as standard contractual clauses.",
    ],
  },
  {
    heading: "Changes to this notice",
    body: [
      "If we change this notice we will update the effective date above and, for material changes, notify account administrators. Continued use after a change means you accept the updated notice.",
    ],
  },
  {
    heading: "Contact",
    body: [
      "Questions or requests: privacy@visentix.ai.",
    ],
  },
];

export function Privacy() {
  return (
    <LegalPage
      eyebrow="Legal"
      title="Privacy Notice"
      effectiveDate={EFFECTIVE}
      intro="How Visentix collects, uses, and protects your information. Written in plain language — no legalese."
      sections={SECTIONS}
    />
  );
}
