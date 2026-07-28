# F07 — Continuous Monitoring Dashboard (Hero)

**Status:** shipped (R1) — Dashboard is real-data (assessments + stats); the monitoring hero (trend sparkline, change feed, alert center) is built and wired to live endpoints (M-06/M-07/M-08 Replaced 2026-07-27) · **Release:** R1 wiring done / R2 real pipelines (richer alerts) · **Depends on:** F02, F04 (F-012/F-013), design-system.md

## Purpose
Make the platform feel *alive* — the difference between "I got a report once" and "this watches the landscape for me." Surfaces trend (F-012), alerts (F-013), and the change feed. This is the GRC product seed and the primary evaluator-convincer.

## Users & entry points
Customer role · `/assessments` (nav: Monitor, title: Privacy Intelligence Monitor).

## Data
Reads: `derived_data_item` (overall score, domain scores, stored F-012/F-013 outputs), `monitoring_event`, `report_snapshot` (provenance), resolved `enforcement_record`.

> ⚠️ **Live-schema reality (2026-07-27, see schema.md §5.4).** The applied `monitoring_event` table has **no `organization_id`** — events are org-scoped at query time via `source_record.url` host ↔ `organization.domain`; `trigger_type` (live value `hash_change`) is normalized to the vocabulary below. There is **no `alert` table** live — alerts are computed from stored F-013 `alert_escalation` (`derived_data_item`) joined to **resolved** `enforcement_record` only (unresolved never surface). F-013→severity band thresholds are undefined (expert-owned); severity is surfaced only from a stored `monitoring_event.severity`, never invented.

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
- **F07 completion (0037):** `GET /admin/jobs` · `POST /admin/jobs/{name}/run` (202, manual) · `POST /admin/jobs/{name}/toggle` — **admin only**. `GET /admin/status` — real payload {db_ok, ollama_ok, gate_mode, last_job_runs, pending_reviews, model_versions} (replaces the not_implemented stub). `GET|PUT /orgs/{id}/notifications` + `POST /orgs/{id}/notifications/test` — **org-scoped**.

## Scheduler, jobs & alert delivery (R2 — 0037)
In-process **APScheduler** (SQLAlchemy Postgres job store, survives restart), started only when `SCHEDULER_ENABLED=true`. Every job: open `job_run(running)` → idempotent batched work → close with counts; a job is **skipped if the same job_name is already running**. Cadence + enabled state come from `platform_setting` (`job.<name>.cron/.enabled`, SLA defaults).
- **monitor_notices** (daily 02:00 UTC): for each `privacy_notice.monitoring_enabled=true` → fetch URL → hash vs stored → if changed: section diff, classify ONLY changed sections, targeted re-score of AFFECTED domains, emit `notice_changed` and (per moved domain) `score_moved` with `payload={domain,from,to,formula_version}`. **Never full-recompute unchanged domains**; the stored hash is updated so a re-run with identical content is a no-op.
- **pull_regulators** (weekly Mon 03:00): run ftc/cppa/state_ag connectors → new `enforcement_record` → **deterministic entity resolution only** → for each resolved record, orgs whose weakest domains intersect the record's issue tags → emit `regulator_signal` `payload={enforcement_id,matched_domain}`.
- **refresh_benchmarks** (monthly 1st 04:00): re-run the F03 demo-cohort job → membership change → emit `cohort_rebenchmarked` `payload={cluster_id,old_n,new_n}`.
- Event types are **exactly the four §2.8 values** — none added (task's 'cohort_refreshed' reconciled to `cohort_rebenchmarked`).

**Alert pipeline** (after each job, per new event): compute F-013 escalation. **IF `platform_setting.f013_severity_thresholds` is unset → write `alert_delivery(status='suppressed_no_threshold')` and send NOTHING** (an admin banner surfaces this); thresholds are **never invented here** (expert-owned). Else severity ≥ threshold → jinja email (customer register, deep-links `/monitor`, no jargon) via SMTP env, and/or webhook POST `{event_id,org_id,type,severity,occurred_at,link}` with an **HMAC signature header** (per-org secret). Delivery is strictly org-scoped.

## Guardrails & confidence
Score deltas carry lineage affordances; version-over-time diffs lead with numbers, never word-level prose diffs (avoids surfacing awkward phrasing to legal readers). Cohort mentions show live n. **Alert delivery is paused (suppressed_no_threshold) until an expert sets F-013 severity thresholds — never invented.** Admin job endpoints are **admin-only**; org notification settings are **org-scoped**.

## Mocks
M-06 sparkline / M-07 feed / M-08 alerts — all replaced by the three routes above.

## Acceptance criteria
- AC-1 First assessment shows baseline state; second shows real deltas colored by improvement.
- AC-2 A monitored-notice change (F02) appears in the feed within the plan's freshness SLA.
- AC-3 An F-013 escalation above threshold creates an alert whose detail opens the real AdvisorNote.
- AC-4 No static arrays remain in `Dashboard.tsx`.
- AC-5 Jobs are idempotent: an unchanged notice hash writes zero events; running a job twice produces no duplicate events.
- AC-6 With F-013 thresholds unset, every eligible event yields `alert_delivery.status='suppressed_no_threshold'` and **zero** email/webhook sends.
- AC-7 Webhook payloads carry a verifiable per-org HMAC signature; org A never receives org B's events (delivery + endpoint scoping).
- AC-8 Admin job endpoints reject non-admin (403); manual trigger records `job_run(triggered_by='manual')`; `/admin/status` returns the real payload.

## Test gate
Route contract tests, trendColor unit tests, no_prior_history state test, feed pagination test, alert→AdvisorNote integration test. **F07 completion:** `tests/test_f07_scheduler_alerts.py` — job idempotency / unchanged-hash zero-writes, suppressed_no_threshold with zero SMTP calls, HMAC verifiable, cross-org scoping, admin-only, manual-trigger job_run.

## Changelog
- 2026-07-28 (engineer): **F07 completion — scheduler, jobs, alert delivery (migration 0037).** In-process APScheduler (Postgres job store) runs monitor_notices / pull_regulators / refresh_benchmarks under a job_run ledger with a concurrency guard; each emits only the four §2.8 event types with org + typed payload (additive monitoring_event columns). Alert pipeline computes F-013 and **suppresses delivery (`suppressed_no_threshold`, nothing sent) while thresholds are unset** — never inventing them; when set, sends jinja email (SMTP env) / HMAC-signed webhook, strictly org-scoped. New admin job endpoints (admin-only) + real `/admin/status` + org-scoped `/orgs/{id}/notifications`. New AC-5…8; tests in `tests/test_f07_scheduler_alerts.py`. **MUST-NOTs honored:** no F-013 thresholds set, no real email in tests, no unapproved crawl, no new event types, no full-rescore of unchanged notices. Source: engineer (F07 completion). *(Frontend Jobs panel + Notifications card + delivery chips = next commit; corpus growth = separate commit.)*
- 2026-07-27 (engineering closeout): **Monitoring hero built and wired — M-06/M-07/M-08 Replaced.** `app/routers/monitoring.py` + `app/services/monitoring.py` serve the three API contracts above; `web/src/pages/customer/MonitoringHero.tsx` renders sparkline + improvement-colored delta (DDR-009) + change feed + alert center on the Dashboard, all org-scoped per F10. Trend deltas come from the versioned `compute_f012`; single-snapshot orgs return `baseline_established` (AC-1); alerts surface stored F-013 outkeys joined to resolved enforcement only (AC-3 partially — full AdvisorNote expansion from an alert deferred pending the finding join). Live-schema drift documented in the Data note + schema.md §5.4. Contract/baseline/empty tests in `tests/test_monitoring_api.py`.
- 2026-07-16 (audit): **Status corrected — it lied in both directions.** The current Dashboard is fully real-data (assessments + stats from the live API, no mocks), but the monitoring-hero surfaces this spec describes (sparkline, change feed, alert center — M-06–M-08) are not present in the code at all. Remaining work is building those panels *and* their endpoints, not merely unmocking them. Mock-tracker rows corrected (v1.8).
- 2026-07-16: Added Changelog section for template conformance; no behavioral change. (Mocks M-06–M-09 tracked in [`00-plan/mock-tracker.md`](../00-plan/mock-tracker.md).)
