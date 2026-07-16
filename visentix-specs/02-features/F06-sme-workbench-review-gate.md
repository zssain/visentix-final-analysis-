# F06 — SME Workbench & Review Gate

**Status:** shipped (M-04 counters wired to real `/admin/training-stats`; queue actions pending) · **Release:** R1 · **Depends on:** F04, business-logic.md §5, design-system.md

## Purpose
The internal three-pane tool where human experts Confirm / Edit / Dismiss findings, author/approve Advisor Note prose, de-identify exemplars, and generate training labels — the quality gate that makes reports client-shippable and the data flywheel for model improvement.

## Users & entry points
SME role · `/review` (nav: Workbench). Internal register: expert jargon ("PII detected") is appropriate here.

## Data
Writes: `risk_finding.sme_status`, `training_label`, `disclosure_clause.exemplar_status`, Advisor layer content into snapshot at approval. Reads: review queue (pending findings), `finding_type` (Codex reference panel), training stats.

## Behavior
1. **Three panes:** source clause (left, with de-id flags) · auto finding + Analyst metrics (center, Confirm/Edit/Dismiss) · Advisor Note editor (right: Fraunces lede, body, "The Visentix Privacy Desk" attribution, empty reviewer slot, Codex reference).
2. **Gate modes:** `expert_review` holds report approval until queue cleared; `instant_draft` publishes draft immediately (admin-configurable, F09).
3. **De-identification:** regex checker flags name/email/URL/custom tokens with category labels, lock icon + red underline (legitimate red use #2); approve disabled until clean; one-click replace-all-with-[REDACTED]. Blocks exemplar approval.
4. **Training labels:** every action recorded; header shows live confirmed/edited/dismissed counters (M-04 → `/api/admin/health` training_stats).
5. **States:** clean / PII detected / redacted / queue empty ("All findings reviewed. Next batch expected [date].").
6. Dismissed findings drop from the client report before snapshot approval.

## API contracts
- `GET /api/review/queue` · `POST /api/review/findings/:id/action` {confirm|edit|dismiss, edits} · `POST /api/review/exemplars/:clause_id/deidentify` · `POST /api/review/exemplars/:clause_id/approve` (server re-validates de-id — never trust client) · `GET /api/admin/health` (training_stats).

## Acceptance criteria
- AC-1 Approving an exemplar with residual PII is impossible server-side.
- AC-2 Every SME action creates a `training_label` with before/after text where edited.
- AC-3 In `expert_review` mode a report cannot reach approved status with pending findings.
- AC-4 Dismissed findings absent from the approved snapshot payload.

## Mocks
See [`00-plan/mock-tracker.md`](../00-plan/mock-tracker.md): **M-04** (training-label counts) and **M-03** (exemplar clause, shared with F05).

## Test gate
De-id regex suite (all categories + evasion cases), gate-mode enforcement tests, training-label capture tests, queue action integration tests.

## Changelog
- 2026-07-16 (audit): Status trued up — training-label counters verified wired to the real `/admin/training-stats` route (M-04 **Replaced**); queue-action wiring remains pending.
- 2026-07-16: Added Mocks and Changelog sections for template conformance; no behavioral change.
