# DECISION-NEEDED — Presence proxy, F-002 severity, and Section 4 measure

**Status:** PROPOSED — awaiting expert approval. No formula, threshold, stored score, or existing snapshot is changed by this memo.
**Author:** implementing engineer · 2026-08-21
**Evidence base:** current source, `INTELLIGENCE-QUALITY.md`, and `REHEARSAL-DIAGNOSIS.md`.
**Nothing here is applied.** These are proposals. Every modelling choice below is **(PROPOSAL — needs expert calibration)** until the expert records a decision.

---

## Q1 — What should count as an observed F-005 element?

### Current behaviour

`app/services/scoring/formulas.py:217-221`:

```python
# Elements present = domains with clauses (proxy — actual element detection is Phase 5)
present_count = sum(
    1 for e in expected_elements
    if e["domain"] in ctx.domains_present
)
```

The related presence-depth implementations are `app/services/profiling/live_profile.py:200`, `:254`, and `:298`:

```python
depth = min(count / max(len(categories) * _PGMS_SAT, 1), 1.0)
presence_conf = min(count / _DSI_SAT, 1.0)
factor_scores[factor] = min(count / _AIGMS_SAT, 1.0) * 100
```

### What the spec says

`visentix-specs/01-foundation/intelligence-logic.md:67` says:

> F-005 | Disclosure Maturity | (Observed / Expected elements) × 100 − clarity/ambiguity penalties

The code and spec do not fully agree: the spec says elements; the current implementation treats every expected element in a present domain as observed. PGMS/DSI/AIGMS also measure saturated presence depth rather than element quality.

### Observed consequence

The read-only rehearsal diagnosis found 8 domains present both before and after noise exclusion, so F-005's presence numerator did not change. For the same notice, the conservative shipped noise filter left PGMS 100.00, DSI 93.45, and AIGMS 85.00 because the relevant presence terms remained saturated. These are recorded observations from `REHEARSAL-DIAGNOSIS.md`; no new value is estimated here.

### Options

1. **Keep the presence proxy and label it explicitly.** No formula code or stored score changes. Customer language must describe breadth/presence, not element-level quality. Existing snapshots remain unchanged. No new `formula_version` row is required if only labels/spec clarification change.
2. **Implement element-level detection.** **(PROPOSAL — needs expert calibration).** Define governed element detectors and evidence rules, then make F-005 count only detected expected elements; decide separately whether PGMS/DSI/AIGMS consume those signals. This requires labelled SME work, new tests and a new formula/profile version. Existing snapshots remain immutable; new scores must be written as new versioned rows. Benchmark populations must be recomputed under the new profile version before comparison.
3. **Keep F-005 but recalibrate presence saturation.** **(PROPOSAL — needs expert calibration).** This changes PGMS/DSI/AIGMS depth without resolving F-005's domain-versus-element mismatch. It requires calibrated config, new formula/profile versions, new population versions, and new rows. Existing snapshots remain unchanged.

### Recommendation

**(PROPOSAL — needs expert calibration):** choose Option 1 for the pilot and require Option 2 before representing F-005 as element-level disclosure quality. Do not use saturation recalibration as a substitute for real element detection.

### What the expert must decide

Should F-005 remain an explicitly labelled domain-presence measure for the pilot, or should external delivery wait for governed element-level detection?

### Blast radius

`intelligence-logic.md` §7; F04 and F05; `app/services/scoring/formulas.py::compute_f005`; `app/services/profiling/live_profile.py` PGMS/DSI/AIGMS; element checklist/config; scoring, perturbation, golden-notice, report-copy and benchmark tests; `formula_version`, `organization_intelligence_profile`, `derived_data_item`, benchmark population versions, and newly generated `report_snapshot` rows. Existing rows/snapshots are preserved.

---

## Q2 — Should F-002 disclosure severity represent volume or quality?

### Current behaviour

`app/services/scoring/formulas.py:61-64` and `:76-80`:

```python
"""F-002 = Σ(JW × RPW × DS) normalized 0-100.

DS (disclosure severity) = proportion of clauses in each domain.
"""
...
ds_by_domain[domain] = count / ctx.total_clauses
```

### What the spec says

`visentix-specs/01-foundation/intelligence-logic.md:64` says:

> F-002 | Regulatory Exposure | Σ(JW × RPW × DS) normalized 0–100

Section 9 describes disclosure quality using vagueness, ambiguity, contradiction, and readability. The registry does not define whether DS means clause volume or a quality deficit. Code therefore implements one plausible interpretation, but the spec does not settle the semantic direction.

### Observed consequence

`INTELLIGENCE-QUALITY.md` records that DS values are coupled proportions whose sum is one. Moving or removing clauses changes multiple domains at once, so the evaluation harness cannot assert a clean “weakened disclosure increases exposure” monotonicity rule. No calibrated quality-based counterfactual exists in the repository, so no replacement score is estimated here.

### Options

1. **Keep volume share.** Clarify DS in the spec as “domain share of substantive clauses.” Cost is documentation and customer-label review. Existing formula outputs and snapshots remain unchanged; no new formula version is needed if the formula meaning is confirmed as already implemented.
2. **Use disclosure-quality severity.** **(PROPOSAL — needs expert calibration).** Define DS from governed quality signals, including their direction and missing-data behavior. This changes F-002, downstream F-008/F-010/F-009, findings and report values. It requires labelled evidence, a new F-002 formula version and dependent formula-version review. Existing snapshots remain immutable; new derived rows and snapshots are versioned.
3. **Separate volume and quality signals.** **(PROPOSAL — needs expert calibration).** Preserve volume as lineage/context and introduce a governed quality-severity input to F-002. This is the largest change: schema/lineage, formulas, UI explanations, tests and population validation all expand. New formula versions are required.

### Recommendation

**(PROPOSAL — needs expert calibration):** do not call the current clause proportion “severity” in customer output. For a pilot, retain it as domain concentration/context; design Option 3 only after SME-labelled quality signals exist.

### What the expert must decide

Is F-002 DS intended to mean substantive-clause volume share, disclosure-quality deficit, or two separately reported signals?

### Blast radius

`intelligence-logic.md` §§7/9; F04/F05; `compute_f002`; `score_notice`; F-008/F-009/F-010 inputs; heatmap/report explanations; score-validity, formula, golden-notice, finding and determinism tests; `formula_version`, new `derived_data_item` versions and new snapshots. Existing stored values remain untouched.

---

## Q3 — Which measure should Benchmark Intelligence position among peers?

### Current behaviour

`app/services/live_scoring.py:91-95` builds peer values and the organization value from PGMS:

```python
peer_scores = [
    {"score": m.get("pgms", 0), "weight": m["benchmark_weight"]}
    for m in population["members"]
]
org_pgms = target_profile.get("pgms", 50.0)
```

`app/services/pipeline.py:130` then uses that same PGMS value for F-011:

```python
f011 = compute_f011(org_pgms, peer_scores, len(peer_scores) + 1)
```

F-003 receives the same `org_pgms` and peer set through `ScoringContext`. Section 4 now renders the stored F-003 lineage value and labels it “Governance Maturity (PGMS)”; it no longer mixes in F-010.

### What the spec says

`intelligence-logic.md:65` says:

> F-003 | Benchmark Deviation | max(0, TopQuartile − OrgScore) or percentile distance from peer median/top quartile

`intelligence-logic.md:73` says:

> F-011 | Benchmark Percentile | PercentileRank(OrgScore in weighted comparable peer population)

`intelligence-logic.md:72` separately defines F-010 as the overall score. “OrgScore” is ambiguous, so the code is internally coherent around PGMS but the spec does not explicitly say whether the product should position PGMS or F-010.

### Observed consequence

The rehearsal recorded PGMS 100 and F-011 percentile 100 against its weighted cohort. The corresponding F-010 value is not recorded in the source diagnosis used for this memo, so no numeric comparison is invented. Before this remediation, Section 4 could display F-010 against PGMS-derived threshold/percentile values; the reader is now internally coherent, but the product decision remains open.

### Options

1. **Benchmark PGMS.** Clarify “OrgScore” as PGMS for F-003/F-011 and keep Section 4's current label. No formula-code or historical-output change; no new formula version is required if this confirms existing meaning. Existing snapshots stay unchanged.
2. **Benchmark F-010.** **(PROPOSAL — needs expert calibration).** Build peer F-010 values from comparable, same-version inputs and pass F-010 consistently to F-003/F-011. This changes benchmark deviation, percentile, VCI inputs and reports; new F-003/F-011 formula versions and new population/snapshot rows are required. Existing snapshots stay unchanged.
3. **Show both as separate measures.** **(PROPOSAL — needs expert calibration).** Keep PGMS peer position and add a separately named overall-score peer position only when a comparable F-010 population exists. This adds a distinct derived object and lineage rather than combining scales. It requires spec/API/UI/test work and likely a new formula ID or explicitly versioned extension approved by the expert.

### Recommendation

**(PROPOSAL — needs expert calibration):** choose Option 1 for the pilot because it matches the current weighted peer inputs and avoids retroactive semantic change. Label it PGMS everywhere and keep F-010 on the cover/dashboard.

### What the expert must decide

Should F-003/F-011 and Section 4 benchmark PGMS, F-010, or two explicitly separate peer-position measures?

### Blast radius

`intelligence-logic.md` §§5-7; F03/F04/F05; `app/services/live_scoring.py`, `pipeline.py`, F-003/F-011 functions, report assembly/renderers and React Section 4; normalization/population and content-hash contracts; population, formula, report, PDF determinism and golden-notice tests; `formula_version`, `derived_data_item`, benchmark population versions and new snapshots. Existing snapshots remain immutable.

---

## What I need to proceed

Answer OD-10, OD-11 and OD-12 separately. Until those answers are recorded and propagated spec-first, no proposal in this memo is authorized for implementation.
