/**
 * F15 — Public Trust Center · MOCK DATA
 *
 * ┌──────────────────────────────────────────────────────────────────────────┐
 * │ REGISTERED MOCK (see visentix-specs/00-plan/mock-tracker.md):            │
 * │  M-27  Trust-metrics strip values. Real source: system/publication       │
 * │        metadata (`formula_version`, frozen publication snapshot) via     │
 * │        GET /api/trust-metrics. Any metric below the suppression          │
 * │        threshold is omitted, never faked (Hard Rule 7).                  │
 * └──────────────────────────────────────────────────────────────────────────┘
 *
 * GUARDRAILS (F15):
 *  - Honest numbers only — every metric has a source note or is omitted; no
 *    fabricated scale (Hard Rule 7).
 *  - Register-appropriate: plain language, no security jargon / attack-class
 *    names (Hard Rule 9). No verdict vocabulary (Hard Rule 1).
 *
 * The values below are real, durable facts about how the platform works
 * (formula count, lineage fields, reproducibility, review gate) — not corpus
 * scale — standing in for the metrics endpoint.
 */

export interface TrustMetric {
  label: string;
  value: string;
  sourceNote: string;   // ties the number to real metadata (AC-3)
}

export const TRUST_METRICS: TrustMetric[] = [
  {
    label: "Versioned formulas",
    value: "14",
    sourceNote: "F-001–F-014 in the formula registry; every score names the version that produced it.",
  },
  {
    label: "Report reproducibility",
    value: "100%",
    sourceNote: "Every report regenerates identically from its frozen snapshot — pull the same snapshot twice, get the same document.",
  },
  {
    label: "Lineage fields per score",
    value: "4",
    sourceNote: "Formula version, inputs, confidence (VCI), and timestamp are stored on every derived value.",
  },
  {
    label: "Expert review",
    value: "Every report",
    sourceNote: "A subject-matter expert reviews each report before it becomes visible to a client.",
  },
];

/* Data-handling commitments (business-logic §6) — authored, register-safe. */
export const DATA_COMMITMENTS: { title: string; body: string }[] = [
  {
    title: "Your notices stay yours",
    body: "The notices you submit are scoped to your organisation. Benchmark, white-label, and quarterly outputs use aggregated, de-identified data with small groups suppressed — never your identifiable content.",
  },
  {
    title: "Processed locally by default",
    body: "By default, notice text is analysed on our own infrastructure and is not sent to any third-party model. If a hosted model is ever used, it runs under an agreement that forbids retention or training on your text.",
  },
  {
    title: "We log the fact, not the content",
    body: "When text is processed we record that it happened — a timestamp and length — but never the words themselves. Keys and credentials are never written to logs.",
  },
  {
    title: "Sources are verified",
    body: "When you submit a notice by URL, we confirm the source and block requests aimed at internal or private addresses before fetching anything.",
  },
];

/* The four lineage fields on every score (traceability guarantee, AC-5). */
export const LINEAGE_FIELDS: { field: string; desc: string }[] = [
  { field: "Formula version", desc: "Which versioned formula produced the value." },
  { field: "Inputs", desc: "The source, clause, regulator, and cohort references it was computed from." },
  { field: "Confidence (VCI)", desc: "How confident the result is, on a published five-band scale." },
  { field: "Timestamp", desc: "When it was generated — frozen into the report snapshot." },
];
