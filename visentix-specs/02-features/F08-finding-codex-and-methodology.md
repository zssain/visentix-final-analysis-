# F08 — Finding Codex & Methodology Pages

**Status:** shipped (Codex on mock M-11) · **Release:** R1 · **Depends on:** schema.md (`finding_type`, `formula_version`), design-system.md

## Purpose
**Codex** (`/codex`): the governed, browsable glossary of every finding code — source of truth for all in-report tooltips and PDF appendices; public-facing candidate. A governed code dictionary is proprietary methodology (IP-relevant).
**Methodology** (`/methodology`, "How Visentix Works"): the discipline-as-sales-pitch page — the 14 formulas as a dignified plain-language list, the guardrail as principle, the SME gate as workflow, reproducibility explained, the Visentix + SOLRAC story.

## Data
Codex reads `finding_type` (canonical definition, exposure signal, anonymised example pattern, related codes). Methodology reads `formula_version.description` (F-001–F-014, plain English — no math notation; the math never ships to lawyers).

## Behavior
- Codex: left rail domain filter (8 + other), searchable list, navy code chips (consistent with reports), expandable entries, **deep-linkable URLs per code** so tooltips and PDFs can point at them. Search empty state shows exact count ("Search N finding codes…"); no-result offers nearest domain, never dead-ends.
- Codex tooltip component (DDR-006) consumes the same API.
- Methodology: Fraunces headlines, generous whitespace, gold accents; reads like a firm's "our standards" page. No "Intelligence, not legal advice" mark on either page (DDR-007 placement).

## API contracts (new)
- `GET /api/codex` → all entries; `GET /api/codex/:code` → single entry (tooltip + deep link).

## Acceptance criteria
- AC-1 Codex renders live `finding_type` rows; static JSON deleted (M-11).
- AC-2 Every code appearing in any report resolves to a Codex entry (referential integrity test).
- AC-3 Deep link `/codex#TRK-007` scrolls/expands the entry.
- AC-4 Methodology formula descriptions come from `formula_version.description` (populated, no NULLs — MVP plan A3).

## Test gate
Codex API contract test, report-code↔codex integrity test, search/empty-state vitest.
