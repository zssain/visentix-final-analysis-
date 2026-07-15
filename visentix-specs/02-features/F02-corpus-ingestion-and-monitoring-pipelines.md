# F02 — Corpus Ingestion & Source Monitoring Pipelines

**Status:** partial (customer intake shipped; scheduled crawling proposed) · **Release:** R2 · **Depends on:** F01, schema.md §2.2/2.5, business-logic.md §7

## Purpose
Build and maintain the benchmark corpus and regulator/enforcement knowledge that all four products depend on: scheduled crawls of peer notices, weekly enforcement ingestion (FTC, state AGs, CPPA), state law catalog updates, hash-based change detection, and versioned source records with reliability scoring.

## Data
Writes: `source_record`, `source_version`, `corpus_quality`, `enforcement_record`, `litigation_event`, `obligation`, `state_law_weight`, `monitoring_event`. Reads: source registry config (living table, not code).

## Behavior
1. **Source registry** — configurable table of source families (FTC enforcement pages, CPPA materials, IAPP state tracker, state AG hubs, NIST frameworks, peer notice URLs) with cadence, tier, and parser type.
2. **Crawl & capture** — fetch, hash, compare to prior hash; on change create `source_version`, run section-level diff, tag changed sections by disclosure domain, set Material Change Indicator when regulator-sensitive categories changed.
3. **Quality gating** — compute F-001 Source Reliability and CQS; CQS < 75 excluded from active benchmark cohorts (retained for trend history or routed to review).
4. **Downstream triggers** — per intelligence-logic.md §11: enforcement ingest → F-004 recalc queue; law change → obligation/weight update; notice change → rescore affected customer assessments + emit `monitoring_event`.
5. **Tiering** — Tier 1 authoritative / Tier 2 legal-dispute / Tier 3 contextual, with the minimum metadata sets from VICBNF §3.2.

## API contracts
- `POST /api/admin/sources` CRUD on the registry (admin).
- `POST /api/admin/ingest/run` manual trigger per family (admin).
- Internal queue/scheduler (cron or worker) — implementation free, but every run logs source_id, hash, outcome.

## Guardrails & confidence
Extraction confidence recorded per capture; ambiguous/failed extractions routed to review, never silently included. US-only Phase 1; non-US sources tagged future-state only.

## Acceptance criteria
- AC-1 A monitored notice whose content changes produces a new `source_version`, a domain-tagged diff, a `monitoring_event`, and a rescore of affected domains.
- AC-2 A new enforcement record updates enforcement frequency/similarity inputs and queues F-004 recalculation.
- AC-3 CQS gate provably excludes low-quality sources from `benchmark_membership`.
- AC-4 Re-ingesting an unchanged source creates no new version.

## Test gate
Change-detection unit tests (hash, diff, material-change flag); CQS gating tests; trigger-matrix integration tests; scheduler idempotency test.
