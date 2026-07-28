import { LegalPage, type LegalSection } from "./LegalPage";

// DRAFT — founder approves wording in-session before this ships.
const EFFECTIVE = "28 July 2026";

const SECTIONS: LegalSection[] = [
  {
    heading: "Agreement to these terms",
    body: [
      "These terms govern your use of Visentix. By creating an account or using the service you agree to them. If you are using Visentix on behalf of an organisation, you confirm you are authorised to accept these terms for it.",
    ],
  },
  {
    heading: "What Visentix is — and is not",
    body: [
      "Visentix analyses privacy notices and produces intelligence: exposure signals, disclosure-maturity scores, peer benchmarks, and expert-reviewed findings.",
      "Visentix is not a law firm and does not provide legal advice. Nothing in the service is a compliance determination or a statement that any notice does or does not comply with any law. Reports describe exposure and likelihood, not legality. Use the output as one input to your own decisions and consult qualified counsel for legal conclusions.",
    ],
  },
  {
    heading: "Accounts",
    body: [
      "Keep your credentials confidential and tell us promptly if you suspect unauthorised use. You are responsible for activity under your account. Accounts and roles may be provisioned or removed by your organisation's administrator.",
    ],
  },
  {
    heading: "Your content",
    body: [
      "You keep ownership of the notices, documents, and text you submit. You grant Visentix the permission needed to store and process that content to provide the service and to keep reports reproducible.",
      "You confirm you have the right to submit what you submit, and that you will not upload content you are not permitted to share.",
    ],
  },
  {
    heading: "Acceptable use",
    body: [
      "Do not use Visentix to break the law, infringe others' rights, probe or attack the service, attempt to reach another tenant's data, or resell the service without our agreement. We may suspend access to protect the service or other customers.",
    ],
  },
  {
    heading: "Pilot / availability",
    body: [
      "During the pilot the service is provided as is and may change, pause, or have limited availability. We aim for reliable operation and keep backups, but we do not guarantee uninterrupted service during this period.",
    ],
  },
  {
    heading: "No warranty; limitation of liability",
    body: [
      "To the extent permitted by law, Visentix is provided without warranties of any kind, and Visentix will not be responsible for indirect, incidental, or consequential damages. Nothing here limits any responsibility that cannot be limited by law.",
    ],
  },
  {
    heading: "Termination",
    body: [
      "You may stop using Visentix at any time. We may suspend or end access for breach of these terms or to protect the service. On termination we handle your data as described in the Privacy Notice.",
    ],
  },
  {
    heading: "Changes",
    body: [
      "We may update these terms; we will update the effective date and, for material changes, notify account administrators. Continued use after a change means you accept the updated terms.",
    ],
  },
  {
    heading: "Contact",
    body: [
      "Questions about these terms: legal@visentix.ai.",
    ],
  },
];

export function Terms() {
  return (
    <LegalPage
      eyebrow="Legal"
      title="Terms of Service"
      effectiveDate={EFFECTIVE}
      intro="The ground rules for using Visentix, in plain language."
      sections={SECTIONS}
    />
  );
}
