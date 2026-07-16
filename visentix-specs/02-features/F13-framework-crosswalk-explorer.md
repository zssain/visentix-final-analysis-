# F13 — Framework Crosswalk Explorer

**Status:** shipped UI — explorer built, all data mocked (M-25); crosswalk backend + copy sign-off proposed · **Release:** R2 · **Depends on:** F08 (Codex / `finding_type`), intelligence-logic.md §4 (8 domains), business-logic.md §2 (descriptive-only rule), design-system.md

## Purpose
Privacy, legal, and compliance teams already report against frameworks they know — the NIST Privacy Framework, ISO/IEC 27701, GDPR, and CCPA/CPRA. The Framework Crosswalk Explorer shows how Visentix's eight disclosure domains and their finding codes **relate to** those frameworks, so a reader can connect an exposure signal to the reference they already track. Every mapping is **descriptive** ("relates to CCPA §1798.120"), never a compliance verdict — this is the guardrail that lets the feature exist at all.

## Users & entry points
Privacy officers, GCs, GRC managers, and analysts. Public route `/crosswalk` (like `/codex` and `/methodology`), reachable from the sidebar (Intelligence group), from Codex finding entries, and cited from the report's framework section (F05). No auth required to read.

## Data
Read-only. Sources:
- `finding_type` (`finding_code`, `domain_id`, `canonical_definition`, `related_codes[]`) — the Codex taxonomy (schema.md).
- **New:** `framework_reference` (`framework`, `domain_id`, `finding_code` nullable, `citation`, `relationship_note`, `descriptive` flag) mapping a domain or code to a framework citation. Amend schema.md in the same PR when the backend is implemented. Until then, mocked (M-25).

## API contracts
`GET /api/crosswalk` → `{ domains: [{ id, name, codes: [finding_code] }], frameworks: [id], mappings: [{ domain_id, finding_code?, framework, citation, relationship_note }] }`. Descriptive-only: no field asserts compliance. Payloads that surface a score also carry `vci`, `formula_version`, `explainability_refs` — the crosswalk itself carries no score, only references.

## Behavior & states
- **Matrix view:** rows = the 8 domains (CR, DC, SH, RT, AI, SEC, TRK, XB), columns = frameworks (NIST PF, ISO 27701, GDPR, CCPA/CPRA). Each cell shows the framework citation(s) the domain relates to.
- **Framework filter:** narrow to a single framework; the matrix collapses to that column's citations.
- **Domain drill-down:** expanding a domain reveals its finding codes (navy Codex chips) with the specific citation each relates to.
- **Descriptive banner:** a persistent, plain-language note that these are references, not compliance determinations.
- Empty (no mapping for a cell → "—, no direct reference"), loading, error (plain language), mobile (matrix scrolls horizontally in its own container; drill-down stacks), reduced-motion.

## Guardrails & confidence
- Every mapping string passes the banned-term filter; language is "relates to / addresses / referenced by" only — **never** verdict vocabulary from the banned-term list (business-logic.md §2, Hard Rule 1).
- No mapping implies a verdict; the descriptive banner and the "Intelligence, not legal advice" mark (DDR-007) are always present.
- Citations are references, not legal advice; the copy is content that requires expert sign-off (OD-01) before real data replaces the mock.

## Mocks
| ID | What's mocked | Real source | Removal plan |
|---|---|---|---|
| M-25 | Crosswalk mappings (domain/code → framework citation + relationship note) | `framework_reference` table + `finding_type`, once `GET /api/crosswalk` is built | Build the mapping table + endpoint; SME/expert signs off the descriptive copy (OD-01), then swap the mock |

## Acceptance criteria
- AC-1 The matrix renders all 8 domains × 4 frameworks; a cell with no reference shows an explicit "no direct reference", never a blank that could read as "fails".
- AC-2 Filtering to one framework shows only that framework's citations for every domain.
- AC-3 Expanding a domain lists its finding codes as Codex chips, each with the citation it relates to.
- AC-4 Every mapping string passes the banned-term filter (no verdict vocabulary); a unit test asserts this over the full mock dataset.
- AC-5 The descriptive-only banner and the "Intelligence, not legal advice" mark are present on the page at all times.
- AC-6 At 375px the matrix scrolls horizontally within its own container and the page body does not scroll sideways; drill-downs stack.

## Test gate
Unit: banned-term scan over the crosswalk copy (AC-4); matrix completeness (8×4) and "no reference" rendering (AC-1). Component: framework filter (AC-2) and domain drill-down (AC-3). Visual QA at 375/768/1280 (AC-6).

## Open questions
- OD-01 (Product) — sign off the descriptive-only crosswalk copy. Recommendation on record: descriptive language, ship the shell now, real citations later. This spec ships the shell UI on mock citations pending that sign-off.

## Changelog
- 2026-07-16: Graduated from `03-ideas/further-ideas.md` (near-term candidate) to a feature spec and built UI-only against mocks (engineer). Shell explorer: 8×4 matrix, framework filter, domain drill-down to Codex chips, descriptive-only banner + Intelligence mark. Copy is mock pending OD-01 sign-off; `framework_reference` table + `GET /api/crosswalk` remain proposed. Files: `web/src/pages/crosswalk/{FrameworkCrosswalk.tsx,mockData.ts,crosswalk.css}`, `/crosswalk` route + nav.
