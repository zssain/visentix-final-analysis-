# F21 — Quarterly Global Privacy Intelligence Report (Deliverable 4, v1 BASELINE)

**Status:** approved — in-progress (owner-approved 2026-07-28 with authoritative S4 catalog; changelog 0.2)
**Release:** R4
**Owner:** eng (aggregation + freeze) + SME/expert (publication approval, methodology sign-off)
**Depends on:** [`reference/derived-catalog-S4.md`](../reference/derived-catalog-S4.md) (authoritative S4 formulas — cited verbatim), F03 profiling / benchmark population (CQS gate parity), F04 findings (frequencies), F05 `report/assembly.py` (snapshot-freeze pattern) + renderer (weasyprint), F06 review gate (`review.py` — expert-review permission, reused for publication approval), enforcement resolution (RESOLVED-only), OD-05 (`n=10` suppression), DIR-006 (minimum-sample suppression), DIR-010 (reproducibility / Hard Rule 6). Replaces F12 mock M-15–M-18.

## Purpose
The public, editorial, **anonymized** quarterly report — industry-wide disclosure maturity, the most common gaps, AI-disclosure levels, and where regulators focused. **v1 is a BASELINE publication: no prior quarter exists → zero QoQ deltas** (F-012 delta engine begins next quarter against this frozen baseline). Everything is computed **strictly from live data**, drawn only from cohorts large enough that **no company can be identified** (DIR-006 + OD-05), and **reproducible byte-for-byte** from the frozen snapshot (DIR-010). **No hand-written statistic anywhere** — every number is a stored `quarterly_metric` row; the methodology block is generated from snapshot metadata.

## Catalog reference (authoritative — RESOLVED)
The owner supplied the authoritative Service-4 rows (Derived Intelligence Catalog v1.0), saved verbatim at [`reference/derived-catalog-S4.md`](../reference/derived-catalog-S4.md). Every v1 metric below cites its exact row. The earlier draft rotated S4-002/003/004 — **corrected here** against the source (S4-002 = Privacy **Clauses**, S4-003 = **Industries**, S4-004 = **Jurisdictions**). Nothing invents a formula — every v1 metric reduces to an existing live computation.

## Users & entry points
Public reader · `/quarterly` (no auth — approved, anonymized, suppression-safe). Admin · `/admin` quarterly panel (build / preview / gate result / approve). Expert (SME) · approves the publication through the **same review-permission check** as assessment approval.

## v1 IN-SCOPE metrics — computed strictly from live data (NO QoQ)
Each is a `quarterly_metric` row with `population_n`, `formula_citation` (the S4 row), and the suppression rule applied. **Dedup / catalog qualifiers answered inline.**

| S4 id | Catalog name | Live realization | Dedup / qualifier answer | Citation |
|---|---|---|---|---|
| **S4-001** | Organizations Analyzed | `COUNT(DISTINCT organization_id)` over the eligible population (after quality filters + anonymization thresholds) | One org counted **once** regardless of notice/version count | S4-001 |
| **S4-002** | Privacy Clauses Analyzed | `COUNT(DISTINCT clause_id)` over each org's **latest** notice. Catalog qualifier is `extraction_confidence >= threshold`; **no such threshold exists in config** → **v1 proxy = `is_noise = false` clauses**, stated in the methodology block (no invented cutoff) | **Latest notice per org only** (never sum historical versions → no revision double-count); noise excluded (decompose-v2) | S4-002 |
| **S4-003** | Industries Benchmarked | `COUNT(DISTINCT organization.industry)` **where the industry's `sample_size (org count) >= 10`** (OD-05 min threshold) | Distinct **canonical industry slug**; `NULL`/`'unknown'` excluded; **industries below n=10 do not count** (catalog `sample_size >= minimum threshold`) | S4-003 |
| **S4-004** | Jurisdictions Covered | `COUNT(DISTINCT j)` over `unnest(privacy_notice.jurisdiction_scope[])` (latest notice per org) **intersected with jurisdictions that have an active `regulator` mapping** | Only jurisdictions with an **active requirement/regulator mapping** count (catalog qualifier) — deduped | S4-004 |
| **S4-005** | Disclosure Maturity Index | Average **F-005** (`derived_data_item` `object_type='disclosure_maturity'`, F-005_v1, latest per org) **weighted by source confidence and industry representation** (see Weighting) | `population_n` = orgs with a DMI score | S4-005 (F-005_v1) |
| **S4-006** | AI Transparency Index | Average **F-007** (`object_type='ai_transparency'`, F-007_v1, latest per **AI-relevant** notice — a notice with `ai_disclosure_presence`/an AI clause) **weighted by industry and source confidence** | `population_n` = AI-relevant orgs with an AI score | S4-006 (F-007_v1) |
| **S4-018** | Top Enforcement Theme Share | `count(theme_records) / total_topic_classified_records × 100` over `enforcement_record.issue_tags[]`, **RESOLVED records only** | **Rule-3 tightening (deliberate deviation):** the catalog denominator is all topic-classified records; F21 restricts BOTH numerator and denominator to `resolution_status='resolved'` — stricter than the catalog, because unresolved (623) are pending signals, not outcomes; documented in the methodology block. Max-share check on `target_org` | S4-018 (stricter) |
| **(report aggregate)** | Top Disclosure Gaps | The N most frequent `risk_finding.finding_type_code` across the population (latest snapshot per org); **prevalence = share of orgs with ≥1 finding of that code**. **Not a numbered Service-4 formula** — a finding-frequency report section | Per-org presence (repeated code counts once); finding-code chips → Codex hover | F-002/F-004 findings · M-17 §2/§6 |

### Weighting (S4-005 / S4-006) — concrete, documented, no invented magic numbers
The catalog specifies "weighted by source confidence and industry representation". v1 realizes this with **only existing live signals**, fully documented in the methodology block:
- **Source confidence weight** = each row's `derived_data_item.confidence_score` (the real per-org VCI/100) — verbatim "source confidence".
- **Industry representation** = compute a **confidence-weighted mean per industry first, then average the industry means equally** — so an over-sampled industry cannot dominate the market index (the plain-language meaning of "weighted by industry representation"). Only industries with `n >= 10` contribute (consistent with S4-003).
This is transparent and reproducible; the exact scheme is flagged **OQ-5** for expert confirmation. (Houses rule: no invented weight/threshold — the only numbers used are live `confidence_score` values and the OD-05 `n=10` floor.)

## DEFERRED S4 items — each with the named missing input
- **S4-007 Consumer Rights Clarity Score** → **missing: a live rights-clarity formula.** Verified — there is **no `F-xxx` / `derived_data_item.object_type` for consumer-rights clarity**; the catalog's penalized average (missing rights / fragmented mechanisms / vague process language) is unbuilt. Re-include when the formula ships.
- **All QoQ deltas (every "since last quarter" figure)** → **missing: a prior approved `quarterly_snapshot`.** v1 is the baseline; the F-012 delta engine computes deltas next quarter against this frozen snapshot.
- **Enforcement Sensitivity, Compound Risk indices + other M-16 exposure indicators** (S4-008…017) → **missing: expert sign-off (OD) to publish market-level exposure indices** + confirmation their per-org scores are populated corpus-wide.
- **Industry benchmark rankings** (M-17 §3) → **missing: enough industries at per-industry `n ≥ 10`.** Current corpus clears the floor for only ~4 industries (retail/healthcare/fintech/saas); the rest suppress. Deferred until coverage broadens or the owner approves a **partial** ranking.
- **AI-governance 6-quarter trend line** (M-17 §5) → **missing: ≥2 historical quarterly snapshots** (only the baseline exists).
- **Regulator activity grid + activity deltas** (M-17 §4) → theme **shares** are in-scope (S4-ENF); the per-regulator×theme intensity grid + QoQ activity deltas are deferred → **missing: prior-quarter baseline + a regulator-activity time series.**
- **High-risk / compound disclosure patterns** (M-17 §7) → **missing: populated `risk_finding.compound_group_id` (F-008 grouping) + the real compound finding-type catalog** (mock CR-xx are placeholders).
- **Benchmark Spotlight excerpts** (M-18) → **missing: enough SME-approved, de-identified exemplars per domain above `n ≥ 10`** (currently 9 approved, several domain-mismatched per M-03).
- **Report Confidence Index per aggregate** (F-014-style aggregate VCI) → **missing: an aggregate-VCI `formula_version`** (per-org VCI exists; a market-aggregate VCI formula is not defined). v1 carries `population_n` per metric instead.

## Data (new — amends schema.md; migration 0040)
```
quarterly_snapshot(
  id uuid pk, quarter text,                       -- '2026-Q3'
  status text CHECK IN ('draft','approved') default 'draft',
  frozen_at timestamptz null, corpus_version text,
  formula_versions jsonb, population_criteria jsonb,
  gate_result jsonb null,                          -- {passed:bool, violations:[...]} (step 3 + admin panel)
  approved_by uuid null, approved_at timestamptz null,
  created_at timestamptz default now())            -- UNIQUE(quarter) where status='approved'

quarterly_metric(
  id uuid pk, snapshot_id fk→quarterly_snapshot,
  metric_id text,                                  -- 'S4-001' …
  value numeric null, value_label text null,
  population_n int, suppressed bool default false,
  suppression_reason text null,
  formula_citation text,                           -- Catalog/formula ref
  computed_at timestamptz default now())
```
`gate_result` / `approved_by` / `approved_at` are **additions beyond the task's literal columns**, required by step 3 ("draft-invalid" + the admin gate panel) and the approval-identity requirement — flagged for owner OK (OQ-2). Reads: `organization`, `privacy_notice`, `disclosure_clause`, `derived_data_item`, `risk_finding`, `enforcement_record` (resolved).

## Aggregation job (manual trigger only in v1)
`POST /admin/quarterly/build {quarter}` (admin) → runs `services/quarterly.py`:
1. **Materialize the eligible population** — orgs with **≥1 completed assessment in the quarter window** (a `report_snapshot`/scored notice dated in `[quarter_start, quarter_end]`) **AND CQS-passing notices** (fresh `open_web` notice — the exact gate `benchmark/population.py` applies, F03 parity) **AND `organization.origin != 'rehearsal'`.** Record the exact rule + resulting org set size into `population_criteria`.
2. **Compute each in-scope S4 metric** per its formula above; every row stores `population_n`. **Suppress** (`suppressed=true`, `value=null`, `suppression_reason`) when **either**: `population_n < 10` (OD-05 / DIR-006 → `reason='below_min_sample_n10'`) **OR** it is derivable to a single org — **max-share check: no single org contributes > 50% of the numerator** (`reason='single_org_dominance'`; applies to gaps, enforcement themes, and any share/average).
3. **Anonymization gate** — an automated pass over **all** rows: any **unsuppressed** row that violates (`n<10`, max-share, or resolves to one identifiable org) → **the job fails loudly**, `gate_result={passed:false, violations:[…]}`, snapshot **stays `draft` and is non-approvable** (draft-invalid).
4. **Freeze** — on approval, `quarterly_metric` + `quarterly_snapshot` rows are **immutable**, enforced **two ways** (owner-approved OQ-3 = both): (a) a **service-layer guard** rejecting any write to an approved snapshot (+ test), AND (b) a **Postgres trigger in migration 0040** that raises on `UPDATE`/`DELETE` where `status='approved'` — so immutability of our most public artifact does not depend on every future code path remembering the rule. Reproducibility (DIR-010): re-render is byte-identical from the frozen rows.

## Approval — reuse the expert-review permission (no bypass)
`POST /admin/quarterly/{id}/approve` — **`require_role('sme','admin')`** (the **exact** permission guarding `/review/*` approval in `review.py`, verified) — records `approved_by` + `approved_at`, and **requires `gate_result.passed = true`** (a gate-failed or already-approved snapshot → 4xx). This wires publication approval through the **same review-permission check** the expert uses for assessments (`expert_review` semantics — the expert approves quarterly publications too). No admin-only or gate-bypassing path may approve (tested).

## API contracts
- **`GET /quarterly/latest`** — **public** (no auth); the **latest `approved`** snapshot only. Public-safe payload = **non-suppressed** metrics + the methodology block. Suppressed metrics are **absent** (never advertised).
- **`GET /quarterly/{quarter}`** — public; approved only; **404 if not approved** (drafts never served publicly).
- **`GET /admin/quarterly`** — `require_role('admin')`; **all** snapshots incl. drafts (+ `gate_result`).
- **`GET /quarterly/{quarter}.pdf`** — editorial weasyprint render; **approved → public; draft → admin-only, gold DRAFT watermark.** Byte-identical per snapshot.
- **Methodology block** — auto-generated from snapshot metadata: corpus size (= S4-001..004 metric values), population criteria, `formula_versions`, quarter window, the suppression-rule text, the **S4-002 non-noise-clause-proxy note** and the **S4-018 resolved-only deviation note**, the S4-005/006 weighting scheme, corpus/benchmark version. **No hand-written numbers.**

## Behavior & states
- **Baseline banner:** wherever a QoQ delta would appear, render **"Baseline edition — trend deltas begin next quarter."** No delta field is emitted (null/absent), not zero.
- **Public suppression:** suppressed metrics **do not render as dashes** — they are **simply absent** (the public surface never reveals what was suppressed).
- Admin: build button + quarter picker, draft preview (gold watermark), **anonymization-gate result panel (violations listed)**, approve button (permission-gated), archive list.
- Empty/loading/error per conventions; reduced-motion honored.

## Guardrails & confidence
Suppression (OD-05 `n=10` + DIR-006 + single-org max-share) enforced **server-side before serialization**; the anonymization gate is a hard pre-approval barrier. Reproducibility per DIR-010. Enforcement themes from **resolved records only**. Descriptive-only vocabulary (guardrail filter applies to any generated prose). Frozen-snapshot immutability = Hard Rule 6.

## Mocks
Replaces **M-15** (publication snapshot + corpus counts), **M-16** (indicators — v1 ships DMI + AI only; rest deferred), **M-17** (section aggregates — v1 ships gaps + enforcement themes; rest deferred), **M-18** (spotlight — deferred). Mark M-15 Replaced and M-16/M-17 **partially Replaced (v1 subset)**, M-18 Open, in `mock-tracker.md` on merge — with the deferred items pointing here.

## Acceptance criteria
- **AC-1** Population = orgs with a completed assessment in-window ∧ CQS-passing ∧ `origin != 'rehearsal'`; **rehearsal-origin orgs are excluded** (tested).
- **AC-2** `population_n < 10` → metric suppressed (`value=null`, reason) (tested).
- **AC-3** **Single-org dominance** (>50% of a numerator) → metric suppressed with `single_org_dominance` (tested, independent of AC-2).
- **AC-4** Anonymization gate: an unsuppressed violation → **build fails, snapshot stays draft, non-approvable** (tested).
- **AC-5** Approving a gate-failed snapshot, or approving via any path missing the `sme|admin` review-permission → **rejected** (tested).
- **AC-6** Approved snapshot is **immutable** — a metric-update attempt on an approved snapshot **fails** (tested).
- **AC-7** **Baseline has zero delta fields** — no `quarterly_metric` carries a QoQ value in v1 (tested).
- **AC-8** Methodology numbers **== stored metadata** (no drift; every displayed statistic traces to a `quarterly_metric`/snapshot field) (tested).
- **AC-9** Public endpoints **never serve drafts** (404) and never emit suppressed metrics (tested).
- **AC-10** **PDF reproducibility** — re-render of an approved snapshot is byte-identical (tested).
- **AC-11** Enforcement themes exclude unresolved records (only `resolution_status='resolved'`) (tested).

## Test gate
`tests/test_f21_quarterly.py` — population build + rehearsal exclusion (AC-1); n<10 suppression (AC-2); single-org-dominance suppression (AC-3); gate-fail blocks approval (AC-4); approval permission + gate-passed required, no bypass (AC-5); approved-snapshot immutability (AC-6); zero-delta baseline (AC-7); methodology == stored metadata (AC-8); public never serves drafts / suppressed (AC-9); PDF byte-identity (AC-10); resolved-only enforcement themes (AC-11). Frontend vitest: public hero/indicator cards with `population_n` small-print, suppressed-absent (not dashes), baseline line present, gate-result panel, permission-gated approve.

## Open questions
- **OQ-1 [OWNER/DATA] — RESOLVED 2026-07-28.** Authoritative Service-4 rows supplied + saved at `reference/derived-catalog-S4.md`; ID rotation corrected; each v1 metric cites its exact row.
- **OQ-2 [ENG] — RESOLVED 2026-07-28 (owner).** `gate_result` / `approved_by` / `approved_at` added to `quarterly_snapshot` (necessary lineage).
- **OQ-3 [ENG] — RESOLVED 2026-07-28 (owner): BOTH.** Service-layer guard + tests AND a Postgres UPDATE/DELETE-reject trigger for `status='approved'` in migration 0040.
- **OQ-4 [SME] — RESOLVED 2026-07-28 (acting SME).** Public copy approved verbatim and wired into `methodology_block` (`METHODOLOGY_INTRO` / `SUPPRESSION_PUBLIC` / `S4018_PUBLIC`): suppression line = *"Statistics are published only for groups of 10 or more organizations, and never where a single organization dominates a figure. Where those conditions are not met, the statistic is omitted."*; methodology intro = *"Every figure in this report is computed from our maintained corpus using versioned formulas, frozen at publication. Corpus size, population criteria, and formula versions are stated below."*; S4-018 deviation = *"Enforcement themes are computed only from actions we have fully verified against the acting regulator and named company — a stricter standard than raw counts."*
- **OQ-5 [SME/DATA] — RESOLVED 2026-07-28 (acting SME): approved as built** (confidence-weighted mean per industry → equal-industry average over n≥10 industries), logged **provisional** with a revisit trigger: **re-evaluate industry weighting when industries at n≥10 exceed 5, OR after F17 baselines exist — whichever comes first.**

## Changelog
- 0.3 (2026-07-28): Acting-SME sign-off — **OQ-4 RESOLVED** (public methodology/suppression/S4-018 copy approved verbatim, wired into `methodology_block` + surfaced in the reader page and PDF); **OQ-5 RESOLVED** (weighting approved as built, provisional with a revisit trigger at >5 industries@n≥10 or F17 baselines). Source: acting SME.
- 0.2 (2026-07-28): Owner-approved for build with the **authoritative Service-4 catalog** (saved at `reference/derived-catalog-S4.md`). Corrected the S4-002/003/004 ID rotation (S4-002 Clauses, S4-003 Industries with `sample_size>=10`, S4-004 Jurisdictions with active regulator mapping); each v1 metric now cites its exact row. S4-002 uses the non-noise-clause proxy (no `extraction_confidence` threshold in config). S4-005/006 weighting made concrete (confidence-weighted, industry-normalized) + flagged OQ-5. **S4-007 deferred** (verified: no live rights-clarity formula). S4-018 resolved-only kept as a deliberate Rule-3 tightening. OQ-2 approved (lineage columns). OQ-3 approved as **both** (service guard + Postgres trigger in 0040). Source: owner.
- 0.1 (2026-07-28): Initial spec (DRAFT). v1 BASELINE quarterly report — `quarterly_snapshot`/`quarterly_metric` (migration 0040), manual build job (population → compute → suppression [n<10 + single-org max-share] → anonymization gate → freeze), expert-review-permission approval (reused from `review.py`), public/admin/PDF endpoints, auto-generated methodology. In-scope: S4-001..006 (corpus counts + DMI + AI index), top disclosure gaps, resolved-enforcement theme shares. All QoQ + M-16 indicators 3–5 + M-17 §3/§5/§7 + M-18 deferred with named inputs. Replaces F12 M-15–M-18 (v1 subset). Not implemented — awaiting owner approval. Source: engineer (F21). **S4 catalog not in-repo — see OQ-1.**
