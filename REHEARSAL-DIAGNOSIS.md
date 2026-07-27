# Rehearsal Diagnosis — 2026-07-28

**By:** implementing engineer. Diagnoses the two intelligence-credibility concerns from the 2026-07-27 local rehearsal (1‑800‑Flowers, assessment `91a04e55…`, org `066745ed…`, snapshot `46c49843…`): **percentile 100** and **only 1 finding** for a 176-clause notice. Evidence-first; the one clear bug (cohort CQS gate) is fixed, the rest are flagged for the expert. **No thresholds/weights/segmentation rules were tuned. Stored rehearsal results were not overwritten — the recompute below is a separate, labeled diagnostic run.**

---

## 1. Cohort composition + percentile (Task 2.1)

**Method:** rebuilt the rehearsal org's dynamic population via `build_population` and cross-referenced each member against the F03 CQS gate (has a fresh `open_web` notice). Recomputed F‑011 against CQS-only members with the *versioned* `compute_f011` (diagnostic, not stored).

| Metric | Value |
|---|---|
| Distinct profiled orgs | 103 |
| CQS-eligible (fresh `open_web` notice) | 85 |
| **Profiled but CQS-excluded** | **18** (stale corpus, incl. 2019 Princeton) |
| Rehearsal population (as-shipped) | **n=90**, relaxation `minor_relaxation_n90`, confidence_penalty 0.03 |
| **CQS-excluded members in that population** | **17 of 90** |
| Population after CQS gate | **n=73**, 0 CQS-excluded |
| F‑011 percentile vs all 90 | **100.0** |
| F‑011 percentile vs CQS-only 73 | **100.0** |

**"minor_relaxation_n90":** a size-band label (`build_population`): 50–99 members → minor weighting relaxation, confidence_penalty 0.03. Not a data-quality signal on its own.

### Finding 1a — **BUG (Rule 6), FIXED:** the dynamic cohort builder ignored the CQS gate the F03 demo-cohort job enforces.
`scripts/build_cohorts.py` gates members on `JOIN privacy_notice … notice_type='open_web'` (CQS-fresh). `build_population` selected members by profile similarity only — so a live org was benchmarked against **17 CQS-excluded stale-corpus orgs** that could never appear in a demo cohort. **Fix:** `build_population` now filters the candidate pool to CQS-eligible orgs (same gate), and discloses the hold-out on the cohort label via a `cqs_gated_excluded_N` relaxation token. After the fix the population is n=73 with 0 CQS-excluded. Regression test: `tests/test_population_cqs.py`.

### Finding 1b — **Not the cohort's fault:** percentile 100 is driven by the org's own PGMS.
The CQS-only recompute is **still 100** — removing the stale members did not change this org's percentile. The driver is `organization_intelligence_profile.pgms = 100` for the rehearsal org: at/above every peer. **Open question for the expert (profiling, not cohorting):** why does a freshly-profiled org land at PGMS 100? Likely `_ensure_org_profile` producing a maxed or default value for a new org. This is a **profiling credibility item**, separate from the cohort gate — I did not change profiling (expert-owned).

---

## 2. Finding yield — why only AI-004 (Task 2.2)

**Rule (`select_findings`, deterministic):** for each domain with clauses, a finding fires when `maturity < 70` **or** `avg_ambiguity > 0.05`, where `maturity = min(clause_count × 15, 100)` (a *coverage* proxy — thin coverage reads as exposure). Per-domain inputs for this assessment:

| domain | code | clauses | maturity | avg amb | fired? | why |
|---|---|---:|---:|---:|---|---|
| ai_automated_decisions | AI-004 | 3 | 45 | 0.007 | **FIRED** | maturity 45 < 70 (only 3 clauses) |
| sensitive_data | SEC-002 | 5 | 75 | 0.017 | no | 75 ≥ 70; amb ≤ 0.05 |
| cross_border | XB-001 | 6 | 90 | 0.018 | no | 90 ≥ 70 |
| retention | RT-003 | 7 | 100 | 0.004 | no | 100 ≥ 70 |
| tracking_cookies | TRK-007 | 14 | 100 | 0.014 | no | 100 ≥ 70 |
| consumer_rights | CR-001 | 24 | 100 | 0.022 | no | 100 ≥ 70 |
| data_sharing | SH-002 | 68 | 100 | 0.015 | no | 100 ≥ 70 |

**Conclusion:** the yield is **correct given the rule** — 1‑800‑Flowers covers every domain with ≥5 clauses except AI (3), so only AI-004 flags. "1 finding" means "one thinly-covered domain," not "one problem." Consistent with percentile 100: a comprehensive, mature notice vs peers.

### Coverage gaps (rules that cannot fire given current data — SME list, not patched here)
- **Enforcement lineage on findings is DEAD.** `app/services/pipeline.py:167` hardcodes `enforcement_matches=[]`, so every finding's `enforcement_ids` is always empty — the enforcement-correlation link never populates at intake (the F-004/alert machinery exists elsewhere but isn't wired in). Coverage gap.
- **DC-005 cannot fire for comprehensive notices.** It requires `< 4` non-"other" domains present; this notice has 8. It only fires on sparse notices.
- **`children_teens` has no finding-type mapping** in `DOMAIN_TO_FINDING` (1 clause here) — those clauses never produce a finding.
- **Ambiguity rarely triggers.** Every domain's avg ambiguity (≤ 0.022) is below the 0.05 trigger, so firing is dominated by clause *count*, not clause *quality* — a vague-but-plentiful domain won't flag. **Threshold is expert-owned; flag only, no tuning.**

---

## 3. Segmentation noise (Task 2.3)

**Method:** heuristic over the notice's 186 sections — flagged as noise if `chars < 120`, or title-only (`≤ 6` words), or a short link-list; plus duplicate-text detection; plus clauses-per-section.

| Metric | Value |
|---|---:|
| Sections | 186 |
| **Flagged noise** (heading/metadata/list-fragment) | **92 (49%)** |
| Sections with duplicated text | 25 |
| Sections with 0 clauses | 10 |
| Clauses total | 176 |
| **Clauses from noise sections** | **82 (46%)** |

**5 examples:** `# Privacy Notice` (16 chars) · `Last Updated: April 28, 2026` (metadata) · `INTRODUCTION` (heading) · `why we gather information about you;` (list fragment) · `how we collect it;` (list fragment).

**Impact:** ~half the sections are non-substantive, and **46% of the "clauses" are fragments from noise sections**. Because the finding rule's maturity proxy is `clause_count × 15`, these noise clauses **inflate domain counts → inflate maturity → suppress findings**. So segmentation noise and the low finding yield are linked. **Recommendation (SME + eng jointly, not changed here — decomposer is expert-owned):** filter headings/metadata/list-fragments before clause extraction (e.g. min-length + link-density + heading heuristics), or down-weight noise clauses in the coverage proxy.

---

## 4. PGMS-100 evidence trace (Task 2.4)

**Hypothesis:** the PGMS signal is fed by segmentation-noise clauses. **Method:** for the rehearsal org, mapped every clause → section → the §3 noise flag, then recomputed the presence-count profile dimensions **excluding noise clauses** (labeled diagnostic; stored profile untouched). 176 clauses, **82 (46%) from noise sections**.

### 4a. What feeds PGMS (and how noise enters)
PGMS = 4 pillars, each `depth = min(clause_count_in_pillar_categories / (n_categories × 3), 1)`. The `× 3` threshold means a pillar **saturates at just 3–9 clauses**:

| pillar (weight) | categories | thr | ALL n / depth | CLEAN n / depth | noise clauses |
|---|---|---:|---|---|---:|
| governance_infrastructure (.30) | retention, cross_border, sensitive_data | 9 | 18 / **100** | 9 / **100** | 9 |
| operational_controls (.30) | data_sharing, tracking_cookies | 6 | 82 / **100** | 52 / **100** | 30 |
| transparency_practices (.20) | ai_automated_decisions | 3 | 3 / **100** | 2 / **67** | 1 |
| consumer_rights_support (.20) | consumer_rights | 3 | 24 / **100** | 16 / **100** | 8 |

Only the thin **transparency** pillar changes (one of 3 AI clauses is noise → 3→2 → depth 100→67). Every other pillar stays saturated even after dropping ~half its clauses.

### 4b. Labeled diagnostic — recompute excluding noise (stored scores untouched)
| dimension | as-stored (ALL) | noise-excluded (CLEAN) | delta |
|---|---:|---:|---:|
| **PGMS** | 100.0 | **93.33** (still "Leading") | −6.67 |
| **DSI** | 93.45 | **64.85** | **−28.60** |
| **AIGMS** | 85.0 | 75.0 | −10.0 |
| **F-005** (domains present) | 8 domains | 8 domains (**none dropped**) | 0 |
| **F-011 percentile** (vs CQS-gated n=73) | 100.0 | **97.49** | −2.51 |

### 4c. Findings
1. **Hypothesis partially confirmed.** Noise clauses do feed the presence-count dimensions — removing them moves PGMS −6.67, **DSI −28.6** (the most corrupted), AIGMS −10. **DSI is the dimension most distorted by segmentation noise** (its `count/5` presence-confidence is padded straight to saturation by noise).
2. **But PGMS-100 is primarily a FORMULA-saturation effect, not noise.** The pillar thresholds (`n_categories × 3` = 3–9 clauses) max out on almost any real notice; **de-noised PGMS is still 93.33 ("Leading"), percentile 97.49.** Filtering noise alone will not drop this org out of the top band — the saturation thresholds are the deeper cause.
3. **F-005 is robust to noise** — it is domain-*presence*-based; no domain was present only via noise clauses, so it is unchanged.
4. **Degenerate path is safe (Task 2.4.3):** `compute_pgms/compute_dsi/compute_aigms` all return **`(0.0, 0.3)`** for zero-signal input (explicit `total_clauses == 0` guard) — **no high default, no code bug.** Nothing to fix here.

### 4d. Decision the expert actually needs
The percentile-100 optic has **two independent, expert-owned causes**, both surfaced here, neither tuned:
- **(a) Segmentation noise** inflating presence-count dimensions (DSI most). → *Approve a decomposer noise-filtering rule (spec-first): drop headings/metadata/list-fragments before clause extraction.* This materially corrects DSI and partially PGMS/AIGMS.
- **(b) PGMS/DSI presence-count saturation thresholds** (`× 3`, `count/5`) that max on a modest notice. → *Review whether those thresholds should scale with notice depth or category quality* (a formula-calibration decision — **not** an engineering change).

---

## What changed vs what's flagged
- **Fixed (code + test):** `build_population` CQS gate (Finding 1a).
- **Flagged for expert/SME (no change):** PGMS-100 traced to §4 (segmentation noise on presence-count dims + PGMS saturation thresholds — clean percentile still 97.49); enforcement-lineage dead path, DC-005/children_teens/ambiguity coverage gaps (§2); segmentation noise (§3). Degenerate profiling path verified safe (§4c.4). Added to `SME-REVIEW-CHECKLIST.md`.
