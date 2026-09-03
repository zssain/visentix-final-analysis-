# F05 Amendment — PDF Visual Direction (2026-09-03)

**Status:** shipped (owner supplied visual reference 2026-09-03)

## Purpose
Adopt the supplied clean, audit-report visual language in the existing immutable PDF renderer without copying its illustrative claims. This is a presentation amendment only: stored section ids, snapshot payloads, formulas, score bands and report content remain unchanged.

## Approved visual structure
- Editorial cover: Visentix identity, large assessment title, prepared-for/date/type metadata, confidentiality panel, and navy/teal edge geometry.
- Executive page: compact three-card summary followed by evidence-backed takeaways.
- Dashboard: headline cards/gauges, supporting metric cards, and horizontal dimension bars.
- Regulator page: regulator cards plus the existing snapshot-backed heatmap.
- Findings and traceability: dense but readable tables with repeated column headers.
- Language comparison: assessed excerpt and approved comparator side by side.
- Guidance: grouped by stored severity without inventing owners, deadlines, or outcomes.
- Closing: Next Steps, one methodology destination, Disclosure, and restrained brand/contact treatment.
- Every content page carries organization/report context and a page number in the footer.

## Integrity constraints
- Fixed corpus-scale claims such as `1,250+` never render; use real frozen counts with date or honest absence.
- No peer-position words while OD-14 is open. Percentiles render only with a real cohort.
- Only finding codes present in the governed `finding_type` catalog render; unknown codes fail the build.
- The reference's teal low-risk swatch is not adopted. Standing colors come from `theme.css`; PDF hex values are generated for WeasyPrint. Existing `_ramp_key` cut-points remain byte-identical until OD-17's threshold half closes.
- No multi-series trend chart is invented while the data source and categorical palette remain unresolved (OD-20). A baseline state replaces absent history.
- Any wording in the visual reference that conflicts with the banned-term list is excluded.

## Acceptance criteria
- AC-P1 The cover, executive summary, dashboard, regulator analysis, findings, language comparison, guidance, traceability and closing matter follow the approved hierarchy using only frozen snapshot values.
- AC-P2 Stored block ids and `section-N` anchors are unchanged; no snapshot or derived value is recomputed.
- AC-P3 PDF palette values are generated from `web/src/theme.css`; hand-edit drift fails CI and `_ramp_key` cut-points do not change.
- AC-P4 No fixed corpus scale, unresolved comparative word, unknown finding code, invented trend, or prohibited phrase appears.
- AC-P5 Scope remains at the front and exactly one Disclosure closes the report.

## Test gate
`tests/test_report_design.py`, `tests/test_pdf_determinism.py` ten-run comparison against the recorded OD-18 baseline, guardrail scan, generator drift check, and full pytest suite.

## Changelog
- 0.2 (2026-09-03): Shipped generated print palette, editorial cover, compact executive/dashboard hierarchy, repeated findings headers, severity guidance, Next Steps and closing matter. Structural/PDF tests and visual inspection passed; the ten-run gate passed 10/10 on this run, while OD-18 remains an explicitly pre-existing intermittent byte-identity defect.
- 0.1 (2026-09-03): Initial owner-approved visual amendment derived from the supplied twelve-page reference; illustrative content explicitly excluded.
