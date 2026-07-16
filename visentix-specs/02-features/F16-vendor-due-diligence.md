# F16 — Vendor Due Diligence Mode

**Status:** shipped UI — workflow built, all data mocked (M-28); vendor pipeline + persistence proposed · **Release:** R2 · **Depends on:** F01 (intake), F04 (findings/scores), F08 (Codex), business-logic.md §2, design-system.md

## Purpose
A procurement/vendor-risk workflow: submit a vendor, run the same disclosure intelligence over its public notice, and move it through a **risk-approval workflow** (pending → approved / approved with conditions / declined) that ends in a **procurement-facing summary**. The distinction that keeps this inside the guardrail: Visentix supplies *exposure intelligence* about the vendor's disclosures; the approve/decline decision is **the customer's own procurement action**, recorded here — Visentix never issues a legal verdict or clearance about a vendor.

## Users & entry points
Procurement, vendor-risk, and privacy teams (and SMEs). Authenticated route `/vendors` (Workspace nav group), reachable from the Monitor dashboard. Not public.

## Data
Read the disclosure intelligence already produced for a vendor's notice (`disclosure_clause`, `risk_finding`, scores with VCI). **New:** `vendor` (name, category, criticality, domain) and `vendor_review` (status, decision_note, conditions, reviewer, decided_at) capturing the customer's procurement decision. Amend schema.md when the backend lands. Until then, mocked (M-28).

## API contracts
`GET /api/vendors` → list with exposure score + VCI + status; `GET /api/vendors/:id` → procurement summary + findings (each with clause evidence + VCI); `POST /api/vendors/:id/decision` → `{ status, note, conditions? }` records the customer's decision (never a Visentix verdict). Every score payload carries `vci`, `formula_version`, `explainability_refs`.

## Behavior & states
- **Vendor queue:** each vendor shows category, criticality, exposure score (band-colored), VCI, honest cohort n, top exposure signals, and its decision status pill (Pending / Approved / Approved with conditions / Declined).
- **Add vendor** intake: name, domain, category, criticality — queues an assessment (mock).
- **Vendor detail / procurement summary:** exposure signals framed descriptively with clause-level evidence + VCI; a decision panel with the three procurement actions and a required note; choosing "approved with conditions" reveals a conditions field. The panel is labelled as the customer's decision, with a line stating Visentix provides exposure intelligence, not an approval.
- **Filters** by status and criticality. Empty (no vendors), loading, error (plain language), low-confidence (small cohort labelled), mobile (queue rows stack; detail is a full-width panel), reduced-motion.

## Guardrails & confidence
- **Exposure intelligence, never a verdict.** Vendor summaries use exposure/maturity/likelihood/confidence language with evidence references — never verdict vocabulary from the banned-term list, and never a Visentix-issued clearance or approval. The decision is the customer's, explicitly.
- Every summary string passes the banned-term filter; every finding links to clause evidence + VCI; cohort sizes are honest with low-confidence labels.
- The "Intelligence, not legal advice" mark (DDR-007) is present on the summary.

## Mocks
| ID | What's mocked | Real source | Removal plan |
|---|---|---|---|
| M-28 | Vendor queue + per-vendor procurement summary, findings, and decision state | `vendor` + `vendor_review` tables over real assessment output (`risk_finding`, scores) via the vendor endpoints | Build vendor intake→assessment pipeline + review persistence; wire the endpoints |

## Acceptance criteria
- AC-1 The queue lists vendors with exposure score, VCI, honest cohort n, and a decision status; scores are band-colored by the shared score-band rule.
- AC-2 A vendor summary frames every signal as exposure with clause-level evidence + VCI — a unit test scans the summary copy against the banned-term list (no verdict vocabulary).
- AC-3 The decision panel offers approve / approve-with-conditions / decline, requires a note, and reveals a conditions field only for the conditional path.
- AC-4 The decision is labelled as the customer's procurement action; the page states Visentix provides exposure intelligence, not an approval.
- AC-5 Cohorts below `LOW_CONFIDENCE_COHORT_N` render the low-confidence label wherever a vendor's benchmark n is shown.
- AC-6 At 375px the queue rows stack and the body does not scroll sideways.

## Test gate
Unit: banned-term scan over vendor summaries (AC-2); low-confidence labelling (AC-5). Component: decision-panel states incl. conditional reveal + required note (AC-3); customer-decision labelling present (AC-4). Visual QA at 375/768/1280 (AC-6).

## Open questions
- Whether decisions are advisory-only or gate a downstream procurement integration (owner: Product) — MVP records the decision locally; integration is future scope. This spec ships the UI on mock vendors pending that call.

## Changelog
- 2026-07-16: Graduated from `03-ideas/further-ideas.md` (near-term candidate) to a feature spec and built UI-only against mocks (engineer). Workflow: vendor queue (exposure score / VCI / honest n / status), add-vendor intake, procurement summary with evidence-backed exposure signals, decision panel (approve / conditions / decline) framed as the customer's action. Exposure-not-verdict + honest-numbers guardrails, Intelligence mark. Vendor pipeline + `vendor`/`vendor_review` persistence remain proposed. Files: `web/src/pages/vendors/{VendorDueDiligence.tsx,mockData.ts,vendors.css}`, `/vendors` route + nav.
