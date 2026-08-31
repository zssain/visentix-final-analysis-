# F07 — Continuous Monitoring Dashboard (Hero)

**Status:** shipped (R1) — Dashboard is real-data (assessments + stats); the monitoring hero (trend sparkline, change feed, alert center) is built and wired to live endpoints (M-06/M-07/M-08 Replaced 2026-07-27) · **Release:** R1 wiring done / R2 real pipelines (richer alerts) · **Depends on:** F02, F04 (F-012/F-013), design-system.md

## Purpose
Make the platform feel *alive* — the difference between "I got a report once" and "this watches the landscape for me." Surfaces trend (F-012), alerts (F-013), and the change feed. This is the GRC product seed and the primary evaluator-convincer.

## Users & entry points
Customer role · `/assessments` (nav: Monitor, title: Privacy Intelligence Monitor).

## Data
Reads: `derived_data_item` (overall score, domain scores, stored F-012/F-013 outputs), `monitoring_event`, `report_snapshot` (provenance), resolved `enforcement_record`.

> ⚠️ **Live-schema reality (2026-07-27, see schema.md §5.4).** The applied `monitoring_event` table has **no `organization_id`** — events are org-scoped at query time via `source_record.url` host ↔ `organization.domain`; `trigger_type` (live value `hash_change`) is normalized to the vocabulary below. There is **no `alert` table** live — alerts are computed from stored F-013 `alert_escalation` (`derived_data_item`) joined to **resolved** `enforcement_record` only (unresolved never surface). F-013→severity band thresholds are undefined (expert-owned); severity is surfaced only from a stored `monitoring_event.severity`, never invented.

## Surfacing rule — the hero is capability-gated (owner-decided 2026-08-31)
The monitoring hero is **built and wired**, and in the pilot configuration it is **structurally incapable of populating**: `SCHEDULER_ENABLED=false` (`.env.example` — "PILOT: keep false"), so the jobs never run and no `monitoring_event` is ever written; `privacy_notice.monitoring_enabled` defaults **false** (migration 0037), so no notice is watched even with the scheduler on; and F-013 severity thresholds are deliberately unset, so alerts are suppressed by AC-6. Three permanently-empty panels do not communicate "nothing has changed" — they communicate "this product does not work" (DDR-011, earn your place).

**Rule:** each of trend, change feed, and alert center renders **only when its own endpoint reports a populated state**; when all three are unpopulated the hero does not render at all. This is a *display* gate over the real endpoint states (`no_history` / `no_events` / no alerts) — **not** a feature flag, and never a fabricated or placeholder panel. The genuine `baseline_established` and quiet-period states below are **kept**: an org that really is being monitored and really has had no changes still sees its calm empty state, because for that org the absence is the information. The distinction is between *nothing has happened yet* (show it) and *nothing can happen* (hide it).

Un-hiding is not a code change: the hero returns the moment the endpoints return data, i.e. when the scheduler is enabled, notices are opted into monitoring, and (for alerts) an expert sets the F-013 thresholds. **No countdown, "coming soon" badge, or upsell fills the vacated space.**

## Customer dashboard composition (owner-decided 2026-08-31)
The Monitor's supporting cards are re-cut against DDR-011:
- **Exposure counts stay, compressed.** Assessment count, finding count, and the high/elevated exposure counts are real and actionable, but do not warrant a talkative side card. They render as a **compact stat row** near the top of the content, in the reader's primary scan path, labelled in plain language.
- **Review Activity is removed from the customer surface.** It rendered `training_stats` (confirmed / edited / dismissed SME decisions) — internal review-flywheel machinery with no customer use, on a customer screen. This is a **register violation** (design-system §4, Hard Rule 9), the same family as the "SSRF-Protected" badge (L-005), not merely clutter. The data is unchanged and stays available on the SME/admin surfaces that own it (F06/F09). See L-011.
- **"Latest Snapshot" is removed as a standing card.** A truncated UUID, a date, and `Population v269382882` are identifiers without meaning attached (DDR-011). The frozen date belongs to the report's own provenance ribbon; the snapshot ID and benchmark-population version are reached on command there and in Traceability. Nothing is deleted from the snapshot and no lineage is lost — the values move from *permanently displayed* to *one gesture away*.

## Layout & behavior
- **Overall Intelligence Score:** big figure + ONE hero sparkline + ▲/▼ delta vs last snapshot. Domain scorecards (8): score + delta, **no mini-sparklines**. All deltas improvement-colored (DDR-009).
- **Change feed:** reverse-chronological, timestamped, snapshot-linked; types: notice changed, score moved (lead with score deltas e.g. 41→38, not prose diffs), regulator signal, cohort re-benchmarked. Left-stripe timeline styling.
- **Alert center:** High/Medium chips; opening one renders the AdvisorNote component for that finding.
- **Live-dot** emerald pulse (static under reduced motion). Provenance ribbon (snapshot surface).
- **Assessment history (owner feedback 2026-08-31).** The Monitor shows *where the organization stands now*; it does not show *what has been run*. A customer needs a plain, reverse-chronological **history of assessments** — every run for their organization with its date, the source assessed (URL / pasted text / uploaded filename), its status (processing / draft / approved), its band-led headline standing, and a link straight to that run's frozen report. It reads from existing objects only (`assessment` / `privacy_notice` / `report_snapshot`); **nothing is recomputed and no historical snapshot is re-rendered or back-filled** (Hard Rule 6) — a legacy run missing a field shows honest absence. Strictly org-scoped via `customer_org_scope` (AGENTS.md §3a), and any new route is added to `CAPTURE_ROUTES` in `tests/test_org_isolation.py`. This is the surface the change feed's entries point *back* into: the feed says what moved, the history says what was run.
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
- AC-9 Assessment history lists every run for the caller's organization in reverse-chronological order with date, source, status, band-led standing, and a working link to that run's frozen report; a run from another organization never appears (route covered by `tests/test_org_isolation.py`).
- AC-11 With every monitoring endpoint reporting an unpopulated state, the hero renders nothing at all — no empty panels, no placeholder, no "coming soon" — and no fabricated series, event, or alert appears in its place.
- AC-12 An org that IS monitored and has genuinely had no changes still sees the `baseline_established` / quiet-period states: the gate distinguishes "nothing can happen" from "nothing has happened yet", and enabling the scheduler + monitoring on a notice restores the hero with no code change.
- AC-13 No customer-facing surface renders `training_stats` (confirmed/edited/dismissed) or any other SME review-flywheel figure; those remain on the SME/admin surfaces only.
- AC-14 The customer dashboard shows no standing card whose content is a bare identifier or version string; exposure counts render as a compact labelled stat row in the primary scan path.
- AC-10 History rows read stored values only — opening the page recomputes nothing and mutates no snapshot; a legacy run lacking a field shows honest absence rather than a back-filled or re-derived value.

## Test gate
Route contract tests, trendColor unit tests, no_prior_history state test, feed pagination test, alert→AdvisorNote integration test. **F07 completion:** `tests/test_f07_scheduler_alerts.py` — job idempotency / unchanged-hash zero-writes, suppressed_no_threshold with zero SMTP calls, HMAC verifiable, cross-org scoping, admin-only, manual-trigger job_run.

## Changelog
- 2026-08-31b (owner feedback, DRAFT pending approval): **Capability-gated monitoring hero + dashboard re-cut (DDR-011).** Verified in code that the hero cannot populate in the pilot configuration (`SCHEDULER_ENABLED=false`, `monitoring_enabled` defaults false, F-013 thresholds unset) — so the three panels now render **only when their own endpoints report populated state**, as a display gate over real states rather than a feature flag or a placeholder. Genuine `baseline_established` / quiet-period states are explicitly **kept** (nothing-has-happened-yet is information; nothing-can-happen is not). Dashboard re-cut: exposure counts compressed into a labelled stat row in the primary scan path; **Review Activity removed from the customer surface as a register violation** (internal SME `training_stats` on a customer screen — see L-011, cf. L-005); **"Latest Snapshot" card removed** (bare UUID + `Population v…` are identifiers without meaning — values move to on-command provenance/Traceability, nothing deleted). New AC-11…AC-14. No endpoint, formula, event type, or stored value changed. Source: owner (product) verbal notes.
- 2026-08-31 (owner feedback, DRAFT pending approval): **Assessment history on the Monitor.** Added a reverse-chronological history of every assessment run for the organization (date, source, status, band-led standing, link to the frozen report), reading stored `assessment`/`privacy_notice`/`report_snapshot` values only — no recomputation, no back-fill, honest absence on legacy rows (Hard Rule 6). Org-scoped via `customer_org_scope` with the route added to the cross-tenant contract test. New AC-9/AC-10. No scheduler, alert, formula, or event-type change. Source: owner (product) verbal notes.
- 2026-07-28 (engineer): **F07 completion — scheduler, jobs, alert delivery (migration 0037).** In-process APScheduler (Postgres job store) runs monitor_notices / pull_regulators / refresh_benchmarks under a job_run ledger with a concurrency guard; each emits only the four §2.8 event types with org + typed payload (additive monitoring_event columns). Alert pipeline computes F-013 and **suppresses delivery (`suppressed_no_threshold`, nothing sent) while thresholds are unset** — never inventing them; when set, sends jinja email (SMTP env) / HMAC-signed webhook, strictly org-scoped. New admin job endpoints (admin-only) + real `/admin/status` + org-scoped `/orgs/{id}/notifications`. New AC-5…8; tests in `tests/test_f07_scheduler_alerts.py`. **MUST-NOTs honored:** no F-013 thresholds set, no real email in tests, no unapproved crawl, no new event types, no full-rescore of unchanged notices. Source: engineer (F07 completion). *(Frontend Jobs panel + Notifications card + delivery chips = next commit; corpus growth = separate commit.)*
- 2026-07-27 (engineering closeout): **Monitoring hero built and wired — M-06/M-07/M-08 Replaced.** `app/routers/monitoring.py` + `app/services/monitoring.py` serve the three API contracts above; `web/src/pages/customer/MonitoringHero.tsx` renders sparkline + improvement-colored delta (DDR-009) + change feed + alert center on the Dashboard, all org-scoped per F10. Trend deltas come from the versioned `compute_f012`; single-snapshot orgs return `baseline_established` (AC-1); alerts surface stored F-013 outkeys joined to resolved enforcement only (AC-3 partially — full AdvisorNote expansion from an alert deferred pending the finding join). Live-schema drift documented in the Data note + schema.md §5.4. Contract/baseline/empty tests in `tests/test_monitoring_api.py`.
- 2026-07-16 (audit): **Status corrected — it lied in both directions.** The current Dashboard is fully real-data (assessments + stats from the live API, no mocks), but the monitoring-hero surfaces this spec describes (sparkline, change feed, alert center — M-06–M-08) are not present in the code at all. Remaining work is building those panels *and* their endpoints, not merely unmocking them. Mock-tracker rows corrected (v1.8).
- 2026-07-16: Added Changelog section for template conformance; no behavioral change. (Mocks M-06–M-09 tracked in [`00-plan/mock-tracker.md`](../00-plan/mock-tracker.md).)
