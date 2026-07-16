# F15 — Public Trust Center

**Status:** shipped UI — center built, trust metrics mocked (M-27); metrics feed proposed · **Release:** R2 · **Depends on:** business-logic.md §2/§6, design-system.md, F05 (traceability), F08 (Codex/Methodology)

## Purpose
A public, no-login page that earns trust before a prospect ever signs in: it states plainly what Visentix does and does not claim, how customer data is handled, how the intelligence is produced and kept reproducible, and — the differentiator — that **every public statistic is backed by the traceability matrix**. It is the credibility asset analysts, regulators, and buyers check first. Everything here is written in the customer's register (plain language, no security jargon or attack-class names — Hard Rule 9) and obeys the no-legal-verdict guardrail.

## Users & entry points
Prospects, analysts, regulators, journalists, security reviewers. Public route `/trust` (like `/methodology` and `/codex`), linked from the Intelligence nav group and from the site footer. No auth.

## Data
Mostly authored, static commitments. The only dynamic part is a small **trust-metrics** strip (e.g. formulas versioned, reproducibility guarantee, cohorts benchmarked) — each metric carries a **source/traceability note**. Real source: system/publication metadata (the same frozen snapshot + `formula_version` the product already exposes). No fabricated scale (Hard Rule 7): metrics are real counts or omitted. Until wired, mocked (M-27).

## API contracts
`GET /api/trust-metrics` → `{ metrics: [{ label, value, source_note }] }`. Values are real counts from system/publication metadata; any metric that would require a cohort under the suppression threshold is omitted, not shown. No score payloads here.

## Behavior & states
- **Commitment sections:** (1) *What we claim* — exposure/maturity/confidence intelligence, never a legal or compliance verdict; (2) *Your data* — customer notices are customer-scoped; benchmark/white-label/quarterly outputs are aggregated, de-identified, sample-suppressed; notice text is processed locally by default and never stored by third parties; we log that text was processed, never its content; (3) *How the intelligence is made* — versioned formulas, human SME review gate, deterministic narratives (links to `/methodology` and `/codex`); (4) *Traceability guarantee* — every score stores its formula version, inputs, confidence (VCI), and timestamp, and reports regenerate identically from frozen snapshots.
- **Trust-metrics strip:** each metric shows its value and a plain-language source note; a metric with no real backing is omitted, never faked.
- Empty/loading/error (plain language), mobile (sections stack), reduced-motion.

## Guardrails & confidence
- **Register rule (Hard Rule 9):** customer-facing plain language only — no security jargon or attack-class names (e.g. describe source verification as "we confirm the source and block requests to internal addresses", never the acronym).
- **No legal verdicts (Hard Rule 1):** the page states what Visentix does *not* do, using exposure/maturity/confidence language; every string passes the banned-term filter.
- **Honest numbers (Hard Rule 7):** no fabricated scale; every shown statistic has a source note tying it to real metadata, or it is omitted.
- The "Intelligence, not legal advice" mark (DDR-007) is present.

## Mocks
| ID | What's mocked | Real source | Removal plan |
|---|---|---|---|
| M-27 | Trust-metrics strip values (formulas versioned, reproducibility, cohorts benchmarked, review-gate) | System/publication metadata (`formula_version`, frozen publication snapshot) via `GET /api/trust-metrics` | Wire the endpoint to real counts; omit any metric below the suppression threshold |

## Acceptance criteria
- AC-1 The page renders with no authentication and states, in plain language, what Visentix does and does not claim (no legal-verdict vocabulary — banned-term test over all copy).
- AC-2 No security jargon or attack-class acronyms appear in any string (a unit test scans for a denylist of jargon terms).
- AC-3 Every trust metric shows a source/traceability note; a metric without one does not render.
- AC-4 The data-handling section states the customer-scoped / aggregated-and-suppressed / local-processing / log-metadata-not-content commitments.
- AC-5 The traceability section lists the four lineage fields (formula version, inputs, VCI, timestamp) and the reproducible-snapshot guarantee.
- AC-6 The "Intelligence, not legal advice" mark is present; at 375px sections stack and the body does not scroll sideways.

## Test gate
Unit: banned-term scan (AC-1) and security-jargon denylist scan (AC-2) over the page copy; metric-without-source omission (AC-3). Component: presence of the data-handling and traceability commitment blocks (AC-4, AC-5). Visual QA at 375/768/1280 (AC-6).

## Open questions
- Which trust metrics are safe and durable to publish (owner: Product + SME) — e.g. reproducibility guarantee and formula count are safe; corpus scale must be real and may be better omitted early. This spec ships the UI on mock metrics pending that selection.

## Changelog
- 2026-07-16: Graduated from `03-ideas/further-ideas.md` (Public Trust Center) to a feature spec and built UI-only against mocks (engineer). Public `/trust` page: four commitment sections (claims / data / methodology / traceability), a source-noted trust-metrics strip, register-appropriate security language, no-legal-verdict + honest-numbers guardrails, Intelligence mark. `GET /api/trust-metrics` remains proposed. Files: `web/src/pages/trust/{TrustCenter.tsx,mockData.ts,trust.css}`, `/trust` route + nav.
