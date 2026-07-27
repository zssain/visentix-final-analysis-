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

## What changed vs what's flagged
- **Fixed (code + test):** `build_population` CQS gate (Finding 1a).
- **Flagged for expert/SME (no change):** PGMS-100 profiling (1b); enforcement-lineage dead path, DC-005/children_teens/ambiguity coverage gaps (§2); segmentation noise (§3). Added to `SME-REVIEW-CHECKLIST.md`.
