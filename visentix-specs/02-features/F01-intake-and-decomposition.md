# F01 — Notice Intake & Decomposition Explorer

**Status:** shipped (mocks pending) · **Release:** R1 · **Depends on:** schema.md §2.4, intelligence-logic.md §4, design-system.md

## Purpose
First customer touchpoint after submitting a privacy notice. Ingests URL / PDF (≤10MB, MIME pdf/html/text) / raw text, decomposes it into taxonomy-classified clauses, and makes **lineage visible from the first interaction** via a split-pane original-document vs extracted-clauses view.

## Users & entry points
Customer role · `/intake` → redirects to `/intake/:assessment_id` when processing begins.

## Data
Writes: `assessment`, `privacy_notice`, `notice_section`, `disclosure_clause` (with embeddings + LLM classification). Reads: `clause_taxonomy`.

## API contracts
- `POST /api/assessments` — {intake_method, url|file|text, org metadata} → {assessment_id, ssrf_protected}. SSRF validation server-side.
- `GET /api/assessments/:id` — status (parsing → classifying → ready), clause list with domain, code, preview.

## Behavior & states
- Split pane: left = intake form or rendered doc; right = domain filter pills (8 domains + other), clause chips (navy, `C-118` + domain eyebrow + 80-char preview). Chip click highlights the source span in the left pane.
- Progress stepper `Ingest → Decompose → Classify` (left-stripe timeline style; animated, reduced-motion safe).
- "Verified source" ✓ on successful URL fetch from the real `ssrf_protected` flag — **never name SSRF in UI**.
- Honest counts: "n clauses extracted · n domains detected".
- States: Waiting / Processing / Ready ("View Assessment →") / Error (plain language).

## Guardrails & confidence
Clause classification stores `nlp_confidence`; low-confidence clauses flagged for SME attention downstream. No scores shown here — decomposition only.

## Mocks
| ID | What | Removal |
|---|---|---|
| M-01 | Static clause fixture | Wire to real decomposition output of `POST /api/assessments` |
| M-02 | Badge always shown | Read real `ssrf_protected` flag |
PDF intake is currently UI-only — wire to backend parsing.

## Acceptance criteria
- AC-1 Submitting a real URL produces real `disclosure_clause` rows visible in the right pane within the processing flow.
- AC-2 PDF and raw-text intake produce equivalent decomposition.
- AC-3 Verified-source badge reflects backend flag; absent on failure.
- AC-4 Chip↔span highlight sync works both panes; mobile stacks panes.
- AC-5 Parse failure shows plain-language error, no stack trace.

## Test gate
Intake pipeline integration tests (URL/PDF/text), SSRF validation tests, classification confidence persistence test, frontend vitest for stepper states.
