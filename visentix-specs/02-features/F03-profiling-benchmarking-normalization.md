# F03 — Organization Profiling, Benchmark Populations & Normalization

**Status:** shipped (deterministic profiler 4.0A + normalization 4.0B) · **Release:** R1 core / R2 scale · **Depends on:** intelligence-logic.md §2, §5, §6; schema.md §2.3, §2.6

## Purpose
Classify every organization into the 7-dimension Organization Intelligence Profile (IC, RSS, PGMS, OSI, DSI, EHP, AIGMS), construct dynamic benchmark populations from the profile tiers, and compute per-peer normalization scores and benchmark weights so no percentile is ever calculated from a raw unweighted peer set. This is the core patent-relevant IP.

## Data
Writes: `organization_profile` (versioned), `benchmark_population` (versioned, relaxation recorded), `benchmark_membership` (normalization_score, benchmark_weight, inclusion_reason). Reads: `organization`, `industry_taxonomy`, `state_law_weight`, `enforcement_record`, notice classification scores.

## Behavior
1. Profiler computes all seven dimensions deterministically from configurable lookup tables + customer metadata + observable indicators (formulas in intelligence-logic.md §2).
2. Population builder: key = Industry + 6 tiers; applies cohort-size ladder (≥100 full / 50–99 minor relaxation / 20–49 adjacent-tier / <20 broaden + low-confidence flag). Every relaxation written to explainability metadata. **CQS gate (single, shared):** both the live **dynamic population** (`build_population`, used by scoring for any org) and the **demo-cohort job** (`scripts/build_cohorts.py`) draw only from **CQS-eligible** orgs — those with a fresh `open_web` privacy_notice. Neither benchmarks against CQS-excluded stale-corpus orgs (e.g. 2019 Princeton). When the gate holds orgs out, the count is disclosed on the cohort label as a `cqs_gated_excluded_N` relaxation token.
3. Normalization engine computes per-member similarity (tier-match 1.0 / adjacent 0.75 / non-adjacent 0.4) across 7 dimensions with the fixed weight set; benchmark weight = product of relevance factors.
4. Monthly rebuild preserves prior population versions; report snapshots pin `benchmark_population_id`.

## API contracts
- `GET /api/organizations/:id/profile` → all 7 scores + tiers + profile_version + confidence.
- `GET /api/benchmark/populations/:id` → population_key, dimensions, cohort_size (live count), relaxations, version.

## Guardrails & confidence
Cohort size < `LOW_CONFIDENCE_COHORT_N` surfaces the low-confidence footer everywhere the cohort appears (M-12: n always live-queried). Benchmark confidence feeds VCI.

**Known limitation — presence-count saturation (Option 1, expert decision 2026-07-28).** The presence-count profile dimensions **saturate at small clause counts**: PGMS pillars at `n_categories × 3` clauses (**3–9**), DSI at **5** clauses per category, AIGMS at **2** clauses per factor (constants in `config/org_profile_weights.json → presence_saturation`, value-identical to the former hardcoded `×3` / `/5` / `/2`). Above the threshold these dimensions measure **breadth/presence, not depth** — a comprehensive notice maxes them regardless of additional detail, which is one of two documented drivers of a top-band optic (the other being segmentation noise, now filtered — F01 `decompose-v2`). The thresholds were **kept as-is** (Option 1): the noise filter alone does not move a genuinely comprehensive notice (`REHEARSAL-DIAGNOSIS.md` §2.5), so any threshold rescaling is a **formula-calibration decision (Option 2), not an engineering change**, and is deferred — revisit trigger logged in `logs/decision-log.md` (after F17 golden-notice baselines exist). Confidence/label wording should reflect that these dimensions are presence-weighted.

## Acceptance criteria
- AC-1 Profile is reproducible: same inputs + same lookup versions → identical scores.
- AC-2 Population construction records any relaxed dimension and the size-ladder branch taken.
- AC-3 Percentiles downstream (F-011) demonstrably use benchmark weights, not raw counts.
- AC-4 Rebuilding populations does not mutate populations referenced by existing snapshots.
- AC-5 The dynamic population and the demo-cohort job apply the **same CQS eligibility gate** (fresh `open_web` notice); a CQS-excluded org never appears in either, and any hold-out is disclosed on the cohort label (`cqs_gated_excluded_N`).

## Test gate
Profiler determinism tests; population-size ladder branch tests; normalization weight-math tests; snapshot-pinning regression test.

## Changelog
- 2026-07-28 (engineer, expert-approved — Option 1): **Presence-count saturation documented + constants moved to config (no behavior change).** Extracted the PGMS/DSI/AIGMS saturation divisors (`×3` / `/5` / `/2`) from `live_profile.py` into `config/org_profile_weights.json → presence_saturation`, **value-identical** — so a future calibration is a config + formula-version change, not a code hunt. Added the presence-count saturation limitation to Guardrails. Thresholds unchanged (Option 1 kept); Option 2 (scale-with-depth) deferred with a decision-log revisit trigger. Source: `DECISION-NEEDED.md` Part 2; `REHEARSAL-DIAGNOSIS.md` §4/§2.5.
- 2026-07-28 (engineer, Stage-3 rehearsal fix): **Shared CQS gate on the dynamic population (Rule 6).** `build_population` now draws only from CQS-eligible orgs (fresh `open_web` notice) — the same gate the demo-cohort job (`scripts/build_cohorts.py`) already enforced — and discloses hold-outs on the cohort label (`cqs_gated_excluded_N`). Fixes an inconsistency the rehearsal surfaced: a live org was benchmarked against 17 CQS-excluded stale-corpus orgs (population n=90 → n=73 after the gate). New AC-5; test `tests/test_population_cqs.py`. No threshold/weight change. (Note for the expert, not a spec change: percentile-100 in the rehearsal traced to the org's own `pgms=100` profile, not the cohort — see `REHEARSAL-DIAGNOSIS.md`.)
- 2026-07-16: Added Changelog section for template conformance; no behavioral change.
