# F07 — Continuous Monitoring Dashboard (Hero)

**Status:** partial — Dashboard ships as a real-data assessments list + stats (live API); the monitoring hero (trend sparkline, change feed, alert center) is **unbuilt** — M-06–M-08 surfaces do not exist yet · **Release:** R1 wiring / R2 real pipelines · **Depends on:** F02, F04 (F-012/F-013), design-system.md

## Purpose
Make the platform feel *alive* — the difference between "I got a report once" and "this watches the landscape for me." Surfaces trend (F-012), alerts (F-013), and the change feed. This is the GRC product seed and the primary evaluator-convincer.

## Users & entry points
Customer role · `/assessments` (nav: Monitor, title: Privacy Intelligence Monitor).

## Data
Reads: `derived_data_item` (overall score, domain scores, trend deltas), `monitoring_event`, `alert`, `report_snapshot` (provenance).

## Layout & behavior
- **Overall Intelligence Score:** big figure + ONE hero sparkline + ▲/▼ delta vs last snapshot. Domain scorecards (8): score + delta, **no mini-sparklines**. All deltas improvement-colored (DDR-009).
- **Change feed:** reverse-chronological, timestamped, snapshot-linked; types: notice changed, score moved (lead with score deltas e.g. 41→38, not prose diffs), regulator signal, cohort re-benchmarked. Left-stripe timeline styling.
- **Alert center:** High/Medium chips; opening one renders the AdvisorNote component for that finding.
- **Live-dot** emerald pulse (static under reduced motion). Provenance ribbon (snapshot surface).
- **States:** first run `no_prior_history` (hide deltas, "baseline established" — never fake a flat line) · quiet period ("No changes since [date]" as calm empty state) · active alert (badge in nav).
- **Mobile:** stacks score → domain cards 2-up → feed → alerts.

## API contracts (new — MVP plan A1)
- `GET /api/monitoring/trend?org_id` → {series: [{snapshot_id, date, overall, domains}], deltas} from F-012 outputs.
- `GET /api/monitoring/events?org_id` → paged `monitoring_event` rows.
- `GET /api/monitoring/alerts?org_id` → F-013 escalations with finding refs.

## Guardrails & confidence
Score deltas carry lineage affordances; version-over-time diffs lead with numbers, never word-level prose diffs (avoids surfacing awkward phrasing to legal readers). Cohort mentions show live n.

## Mocks
M-06 sparkline / M-07 feed / M-08 alerts — all replaced by the three routes above.

## Acceptance criteria
- AC-1 First assessment shows baseline state; second shows real deltas colored by improvement.
- AC-2 A monitored-notice change (F02) appears in the feed within the plan's freshness SLA.
- AC-3 An F-013 escalation above threshold creates an alert whose detail opens the real AdvisorNote.
- AC-4 No static arrays remain in `Dashboard.tsx`.

## Test gate
Route contract tests, trendColor unit tests, no_prior_history state test, feed pagination test, alert→AdvisorNote integration test.

## Changelog
- 2026-07-16 (audit): **Status corrected — it lied in both directions.** The current Dashboard is fully real-data (assessments + stats from the live API, no mocks), but the monitoring-hero surfaces this spec describes (sparkline, change feed, alert center — M-06–M-08) are not present in the code at all. Remaining work is building those panels *and* their endpoints, not merely unmocking them. Mock-tracker rows corrected (v1.8).
- 2026-07-16: Added Changelog section for template conformance; no behavioral change. (Mocks M-06–M-09 tracked in [`00-plan/mock-tracker.md`](../00-plan/mock-tracker.md).)
