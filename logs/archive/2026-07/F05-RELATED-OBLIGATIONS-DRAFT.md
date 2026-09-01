# DRAFT for approval — F05 addition: "Related obligations" as finding-drawer lineage context

**Status:** DRAFT — Phase gate (task step 5). F05 currently has no related-obligations section, so per the task I am **drafting the spec addition and STOPPING for approval before any UI/report work.** Nothing in F05 or the report renderer is changed yet.

**Why now:** Part-B clause→obligation matching (`clause_obligation`) is being activated (embeddings backfill + `scripts/run_obligation_match.py`). Surfacing it must be **lineage context only**, matching the matcher's own framing.

## Proposed F05 change (for review — not yet applied)

### Behavior (new sub-point under §3 Furniture / Disclosure Findings drawer)
> **Related obligations (context, not a legal mapping).** The Disclosure Findings lineage drawer *may* list obligations matched to the finding's cited clauses, read from `clause_obligation`. This is **exposure context only — never a legal conclusion or a compliance mapping** (verbatim intent of `obligation_match.py`). Each row shows the obligation's law / requirement_type / applicability, the `similarity`, the `matched_terms` (lineage), and a **verified / unverified** confidence badge (unverified = obligation `effective_date IS NULL`, reduced confidence). Honest empty state when no obligation clears the **0.35** similarity floor: "No related obligations above the similarity threshold." Presentation only — it **never** affects any score or finding (DIR-008: presentation never recalculates), and is drawn from the frozen snapshot like every other number.

### Data
> Reads `clause_obligation` (Part-B matcher output: `similarity`, `match_method`, `matched_terms`, `model_version`). No new writes at render.

### Proposed acceptance criteria
- **AC-6** The Disclosure Findings drawer lists related obligations from `clause_obligation` for the finding's cited clauses, each with the exposure-context disclaimer, similarity, matched_terms, and a verified/unverified badge; below-floor cases show the honest empty state.
- **AC-7** Related-obligation context carries **zero** verdict/legal-mapping language (guardrail scan) and demonstrably does **not** change any displayed score or finding (DIR-008).
- **AC-8** Related obligations render from the frozen snapshot (byte-identical re-pull) — not recomputed at render.

### Guardrails
> The related-obligations block is subject to the banned-term filter and the "Intelligence, not legal advice" mark (DDR-007). Unverified obligations must visibly carry reduced confidence.

## What is blocked pending approval
- Freezing `clause_obligation` context into the report snapshot payload.
- The finding-drawer UI (interactive + PDF parity).
- F05 changelog + AC bump (via the spec-update workflow) once approved.

**STOP — awaiting approval to proceed to the F05 spec edit + report/UI work.** The backend (embeddings, matcher, `clause_obligation` population, F-004 deepening) proceeds independently and is not gated by this.
