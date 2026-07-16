# F04 — Scoring, Findings & Confidence Engine

**Status:** shipped · **Release:** R1 · **Depends on:** F03, intelligence-logic.md §7–§9, schema.md §2.7

## Purpose
The formula layer: converts classified clauses + profiles + cohorts + regulator/enforcement data into derived intelligence objects (F-002…F-014), deterministic risk findings with finding codes, VCI on every output, and full explainability lineage. Deterministic, reproducible, versioned.

## Data
Writes: `derived_data_item`, `risk_finding`, `explainability_reference`. Reads: `formula_version`, `disclosure_clause`, `organization_profile`, `benchmark_membership`, `regulator`, `enforcement_record`, `obligation`, `clause_obligation_match`, `finding_type`.

## Behavior
1. **Formula engine** executes F-002–F-011 per assessment with the active `formula_version` weight sets; F-012/F-013 run on monitoring cycles; F-014 at report assembly.
2. **VCI engine** computes the 5-component confidence for every object; **suppression rule:** VCI < 40 → object suppressed from customer output / routed to review; 40–59 → caution label.
3. **Findings engine** deterministically maps scored weaknesses to governed finding codes (Codex), severity (Low/Moderate/High/Severe), interpretive-variance class, and related clause IDs; identical inputs → identical findings (reproducibility guarantee, snapshot-tested).
4. **Compound risk (F-008)** groups interacting findings via `compound_group_id` with correlation multipliers (1.00–2.50) and regulator weights.
5. **Enforcement correlation (F-004)** uses clause↔enforcement embedding similarity × RPW × EFW.
6. Every object writes `explainability_reference` rows sufficient to populate the lineage drawer (clause → regulator → jurisdiction → cohort + formula + VCI + snapshot).

## API contracts
- `GET /api/assessments/:id/intelligence` → derived objects, each {object_type, score, vci, vci_components, formula_version, explainability_refs}.
- `GET /api/findings/:risk_id/lineage` → drawer payload.

## Guardrails & confidence
All output labels use exposure/maturity/likelihood vocabulary. No LLM in the scoring path — LLM assists classification upstream and narration downstream only.

## Acceptance criteria
- AC-1 Re-running an assessment against a pinned snapshot reproduces byte-identical scores and findings.
- AC-2 Every derived object exposes VCI + formula_version + ≥1 explainability reference (DIR-002/004).
- AC-3 VCI < 40 objects never appear in customer-facing payloads.
- AC-4 Formula weight change via `formula_version` affects only new outputs; historical snapshots unchanged.

## Behavior & states
Engine/data states (F04 has no screen of its own; consuming feature specs own UI chrome):
- **Happy path:** classified clauses → `derived_data_item` rows carrying score + VCI + formula_version + lineage (DIR-001…004).
- **Empty:** no classified clauses → no derived items; downstream shows an honest "baseline established" state, never a fabricated score.
- **Low-confidence:** VCI < 40 suppressed from customer-facing payloads; 40–59 carries the caution label (Hard Rule 5 / §8).
- **Error:** a partial pipeline failure surfaces as a missing value with a reason — never a guessed or default score.
- **Re-scoring:** writes new versioned rows; existing snapshots untouched (DIR-003, Hard Rule 6).

## Test gate
The existing formula/VCI/findings suites (Phase 4 gates) plus: suppression threshold test, reproducibility snapshot test, weight-versioning isolation test.

## Changelog
- 2026-07-16: Added Behavior & states and Changelog sections for template conformance; no behavioral change.
