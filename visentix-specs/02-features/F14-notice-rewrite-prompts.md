# F14 — Notice Rewrite Prompts (Trust Language Studio)

**Status:** shipped UI — studio built, all data mocked (M-26); suggestion library + backend proposed · **Release:** R2 · **Depends on:** F04 (findings/gaps), F06 (exemplar de-id + approval), F08 (Codex domains), business-logic.md §2, design-system.md

## Purpose
A trust/marketing tool for the customer's own team: for each disclosure gap in their notice, show a **benchmark-informed language pattern** — an example of how top-quartile peers phrase the same disclosure — so the team can improve clarity and reader trust. Suggestions are **language patterns, not legal drafting**: they never tell an organisation what it must do or assert compliance; they show how clearer notices in the cohort tend to read. This framing (and the guardrail behind it) is what lets a privacy-intelligence product offer wording help at all.

## Users & entry points
Customer privacy, trust, and marketing teams (and SMEs reviewing). Authenticated route `/rewrite` (Workspace nav group), reachable from a report's Recommendations section and from the Monitor dashboard. Not public.

## Data
Read-only over the org's own data plus authored patterns:
- `disclosure_clause` (the org's current clause text per domain) and `risk_finding` (detected gaps, domain, severity) — schema.md.
- Exemplar language from `disclosure_clause WHERE is_exemplar = true`, **already SME-approved and de-identified** via the F06 pipeline.
- **New:** an authored `rewrite_pattern` library (`domain_id`, `pattern_text`, `rationale`, `source_cohort_n`) — patterns are authored/curated, never LLM-invented (Hard Rule 2). Amend schema.md when the backend lands. Until then, mocked (M-26).

## API contracts
`GET /api/rewrite?assessment_id` → `{ prompts: [{ domain_id, gap_status, current_excerpt?, pattern_text, rationale, source_cohort_n }] }`. No score is asserted; if a payload ever carries one it includes `vci`, `formula_version`, `explainability_refs`. Patterns are returned from the authored library + exemplar store, never generated at request time.

## Behavior & states
- **Prompt list by domain:** each of the org's gap domains shows a card with: the gap status (`missing` / `could be clearer` / `adequate`), the **current excerpt** (or "not addressed in your notice"), the **suggested language pattern**, a plain-language **why it helps** rationale, the exemplar cohort `n` it's drawn from, and a **Copy pattern** action.
- **Adequate domains** are shown collapsed with a teal "reads clearly" marker — the tool celebrates what's already good, not only gaps.
- **Checklist progress:** a header count of domains addressed vs. total; checking a prompt marks it handled (local only in the mock).
- Empty (no gaps → "Your notice addresses every domain clearly"), loading, error (plain language), low-confidence (small exemplar cohort labelled), mobile (cards stack), reduced-motion.

## Guardrails & confidence
- **Language patterns, never legal drafting or verdicts.** A persistent banner states this; every string passes the banned-term filter (no verdict vocabulary); patterns use "clearer notices tend to…" framing, never obligation phrasing.
- Patterns come from the **authored library + SME-approved, de-identified exemplars** (Hard Rule 2 + Hard Rule 8) — never LLM-invented and never raw peer text.
- Exemplar cohort sizes shown honestly; small cohorts carry the low-confidence label. The "Intelligence, not legal advice" mark (DDR-007) is always present.

## Mocks
| ID | What's mocked | Real source | Removal plan |
|---|---|---|---|
| M-26 | Rewrite prompts (per-domain gap status, current excerpt, suggested pattern, rationale, cohort n) | `rewrite_pattern` authored library + `disclosure_clause` (org clauses + `is_exemplar` patterns) via `GET /api/rewrite` | Author the pattern library; wire the endpoint over real gaps + approved exemplars |

## Acceptance criteria
- AC-1 For each gap domain the studio shows the current excerpt (or an explicit "not addressed") beside a suggested language pattern — never a suggestion without showing the current state.
- AC-2 Every suggested pattern and rationale passes the banned-term filter; a unit test asserts this over the full mock dataset.
- AC-3 No pattern uses obligation/compliance framing ("must", "required to", "to comply"); a unit test scans for these.
- AC-4 Each pattern shows the exemplar cohort `n`; cohorts below `LOW_CONFIDENCE_COHORT_N` render the low-confidence label.
- AC-5 The "language patterns, not legal drafting" banner and the "Intelligence, not legal advice" mark are present at all times.
- AC-6 Adequate domains render collapsed with a positive marker; the header shows addressed/total progress.
- AC-7 At 375px cards stack and the page body does not scroll sideways.

## Test gate
Unit: banned-term scan (AC-2) and obligation-phrase scan (AC-3) over the pattern dataset; cohort low-confidence labelling (AC-4). Component: current-vs-suggested pairing (AC-1), progress count + collapsed-adequate rendering (AC-6). Visual QA at 375/768/1280 (AC-7).

## Open questions
- Pattern library authorship + SME sign-off process (owner: SME team) — who authors and approves the `rewrite_pattern` entries, and how they stay tied to approved exemplars. This spec ships the UI on mock patterns pending that process.

## Changelog
- 2026-07-16 (audit): AC-2 (banned-term) and AC-3 (obligation-phrase) unit tests implemented (`guardrails.test.ts`); Copy-pattern feedback now honest (reports failure when the clipboard write fails); banner + domain chip moved to shared furniture.
- 2026-07-16: Graduated from `03-ideas/further-ideas.md` (near-term candidate) to a feature spec and built UI-only against mocks (engineer). Studio: per-domain prompt cards (current excerpt vs. benchmark-informed pattern), rationale, honest exemplar cohort n, checklist progress, positive markers for adequate domains, descriptive-only + no-obligation guardrails, Intelligence mark. Authored pattern library + `GET /api/rewrite` remain proposed. Files: `web/src/pages/rewrite/{NoticeRewrite.tsx,mockData.ts,rewrite.css}`, `/rewrite` route + nav.
