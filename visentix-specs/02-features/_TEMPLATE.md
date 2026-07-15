# Fxx — Feature Name

**Status:** proposed | approved | in-progress | shipped
**Release:** R1 (MVP) | R2 | R3 | R4 | R5
**Owner:** —
**Depends on:** foundation docs + other feature IDs

## Purpose
One paragraph: the user problem, the product it serves, and why it exists.

## Users & entry points
Personas, routes, and how the feature is reached.

## Data
Tables read/written (must exist in `01-foundation/schema.md`; if new, amend schema.md in the same PR).

## API contracts
Endpoints with method, path, request/response shape, auth role, error states. Every score payload includes `vci`, `formula_version`, `explainability_refs`.

## Behavior & states
Happy path, empty, loading, error, low-confidence, draft vs approved, reduced-motion, mobile.

## Guardrails & confidence
How the banned-term filter, VCI thresholds, and lineage requirements apply here.

## Mocks (if any)
| ID | What's mocked | Real source | Removal plan |

## Acceptance criteria
- AC-1 …
- AC-2 …

## Test gate
Unit / integration / verification tests that must be green before merge.

## Open questions
Anything blocking, with owner.
