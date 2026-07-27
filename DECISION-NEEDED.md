# DECISION-NEEDED — Decomposer noise filter + presence-count calibration

**Status:** PHASE A (spec draft, no code). Awaiting expert approval before any code or spec-file edit.
**Author:** implementing engineer · 2026-07-28
**Evidence base:** `REHEARSAL-DIAGNOSIS.md` §3 (Task 2.3, segmentation noise) + §4 (Task 2.4, PGMS/DSI/AIGMS presence-count trace). Stored rehearsal scores were never altered; the numbers below are the diagnosis's labeled diagnostic recompute.
**Nothing here is applied.** These are proposals. Weights/thresholds are expert-owned; where a number isn't drawn from the §2.3/§2.4 analysis it is marked **(PROPOSAL — needs expert calibration)** and nothing is tuned.

Two independent, expert-owned causes of the rehearsal's percentile-100 optic were surfaced in the diagnosis (§4d), neither tuned:
- **(a)** Segmentation noise inflating presence-count dimensions (DSI most) → **Part 1** below (noise-filter rule).
- **(b)** Presence-count **saturation thresholds** that max out on a modest notice → **Part 2** below (calibration options memo).

---

## PART 1 — Proposed decomposer noise-filter rule  *(for approval)*

### 1.1 Design constraints (from the task + house rules)
- **Deterministic + explainable.** No LLM, no scoring. Every decision is a boolean predicate a non-author can re-check by eye.
- **Uses only signals already computed in the §2.3 analysis:** **char length**, **link density** (list-fragment structure), **duplication across sections**, **section position**. No new NLP.
- **Never deletes.** A filtered clause is **kept in the DB** with `is_noise = true` + a `noise_reason` code, so lineage and the split-pane original view are intact. It is only **excluded from counts**.
- **Versioned + non-retroactive.** New behavior ships behind the tag **`decompose-v2-noisefilter`**; existing assessments are untouched (Rule 4). Re-scoring old notices is a separate, expert-gated action.

### 1.2 Signals (all already computed in the diagnosis §3)
For each **section** (the decomposer's `notice_section`, which already carries `sequence` = position):
- `chars` = `len(extracted_text.strip())` — **char length**
- `words` = word count
- `is_heading` = text begins with a markdown heading marker (`#`/`##`/`###`) — already produced by `_split_sections`
- `list_fragment` = **link density / list structure**: `words ≤ 12` **and** text ends with `;` or `:` **and** has no sentence-terminal `.`/`?`/`!`  (the diagnosis's "short link-list" signal)
- `dup_key` = normalized (lowercased, whitespace-collapsed) text; a section is a **duplicate** if `dup_key` already appeared at a lower `sequence` — **duplication across sections**
- `sequence` — **section position** (used to keep the first of a duplicate set and to recognize front-matter)

### 1.3 Predicates → `noise_reason`  (first match wins, evaluated in this order)
| # | Predicate | Signals used | `noise_reason` |
|---|---|---|---|
| 1 | `is_heading` **or** (`words ≤ 6` and no terminal `.`/`?`/`!`) | char length + heading marker | `heading_only` |
| 2 | matches front-matter metadata `^(last updated|effective date|version\b|©|copyright|all rights reserved)` (case-insensitive) | char length + position | `metadata` |
| 3 | `list_fragment` (ends `;`/`:`, `words ≤ 12`, no terminal sentence punctuation) | link density | `list_fragment` |
| 4 | non-heading, non-list, `chars < 120`, not a complete sentence (no terminal `.`) | char length | `too_short` |
| 5 | `dup_key` seen at a lower `sequence` (keep the first) | duplication + position | `duplicate_of:<section_id>` |

- **Thresholds `120` and `≤ 6 words`** are taken **verbatim from the §2.3 analysis** (`chars < 120`, title-only `≤ 6` words) — not invented here. The `list_fragment` operationalization (`≤ 12` words + trailing `;`/`:`) is the analysis's "short link-list" made checkable; **the `12`-word bound is a (PROPOSAL — needs expert confirmation)**, everything else is from the analysis.

### 1.4 Propagation to clauses + the existing silent drop
- Every clause whose `section_id` is a noise section inherits `is_noise = true`, `noise_reason = 'section:<reason>'`.
- **Replace the current silent drop.** `decompose()` today does `if len(para.strip()) < 20: continue` — it **deletes** short fragments, which loses lineage. Under the rule, such a clause is instead **kept** with `is_noise = true`, `noise_reason = 'clause_fragment'`. (No clause is dropped anymore.)

### 1.5 What "excluded" means (kept in DB, dropped from counts)
`is_noise = true` clauses are excluded from — and **only** from — count-based inputs:
- classification tallies (the `llm` / `keyword_fallback` counts on intake),
- profiling `clause_categories` that feed **PGMS pillars, DSI presence-confidence, and AIGMS factors** (built from `WHERE is_noise = false`),
- finding-rule maturity counts (`select_findings` per-domain `clause_count`).

They remain: stored, classified (for lineage), visible in the split-pane original and the lineage drawer (shown as *filtered, with reason*), and counted in nothing user-facing as substance. **F-005 (domains present) is unaffected** — the diagnosis (§4c.3) showed no domain was present *only* via noise clauses, so presence is unchanged; the filter is applied uniformly regardless.

### 1.6 Schema addition (proposed — Phase B migration, additive/idempotent)
```
disclosure_clause.is_noise      BOOLEAN NOT NULL DEFAULT false
disclosure_clause.noise_reason  TEXT              -- NULL unless is_noise
```
Existing rows default `is_noise = false` (correct: they were never filtered). schema.md §2.4 gains these two columns; F01 gains the rule + acceptance criteria. **These edits are drafted, not applied.**

### 1.7 Five worked examples — real rehearsal sections
Notice `91a04e55-b825-46b9-924b-3ca44ff4fe5b`, org `066745ed…` ("1-800-Flowers (rehearsal)"). Section IDs are the **real stored rows** (verified live 2026-07-28); the diagnosis §3 named these five.

| # | `section_id` (real) | seq | text (verbatim) | chars | words | signal that fires | → `noise_reason` | kept? | counted? |
|---|---|---:|---|---:|---:|---|---|---|---|
| 1 | `2010c701-9ddd-4d91-a84d-013c47496be4` | 0 | `# Privacy Notice` | 16 | 3 | markdown heading | `heading_only` | ✅ kept | ❌ excluded |
| 2 | `d7b17cd2-cead-43e7-83d8-62adb8cae719` | 1 | `Last Updated: April 28, 2026` | 28 | 5 | metadata pattern @ low seq | `metadata` | ✅ kept | ❌ excluded |
| 3 | `26acc774-5aeb-45ef-ad2f-940c0169ff94` | 2 | `INTRODUCTION` | 12 | 1 | `words ≤ 6`, no terminal punct | `heading_only` | ✅ kept | ❌ excluded |
| 4 | `894972e2-bba8-4bb7-9434-55538a958c33` | 5 | `why we gather information about you;` | 36 | 6 | ends `;`, `words ≤ 12`, no `.` | `list_fragment` | ✅ kept | ❌ excluded |
| 5 | `acf762d1-afcb-4401-b967-349f3d58a60b` | 6 | `how we collect it;` | 18 | 4 | ends `;`, no `.` | `list_fragment` | ✅ kept | ❌ excluded |

**Boundary note (surfaced, not resolved):** in the same notice, `seq=9` (`81f117bd…`, 88 chars, 14 words, `"the choices you may have regarding the personal information …"`) is a *continuation* of the same split bullet list but ends without `;` — a naive `chars < 120` rule (predicate 4) would flag it, yet it is arguably real content. This is exactly why the rule leads with the structural `list_fragment`/`heading_only` predicates before the blunt `too_short` one, and why the `too_short` predicate requires "not a complete sentence." **Whether such list-continuation lines should be noise is an expert call** — flagged, not decided.

### 1.8 Tests that would ship with Phase B (for reference)
Noise clause is **kept + flagged** (`is_noise`, `noise_reason` populated, row not deleted); PGMS/DSI/AIGMS + finding counts computed from `is_noise = false` **exclude** it; lineage intact (clause still linked to its section and retrievable); old-version assessments unchanged.

---

## PART 2 — Presence-count saturation: calibration options memo  *(expert decision — no recommendation)*

### 2.1 The exact current formulas (live_profile.py — what the rehearsal ran)
| Dim | Per-unit depth/presence term | Saturates at | Source |
|---|---|---|---|
| **PGMS** | pillar `depth = min(count / (n_categories × 3), 1)` | `3 × n_categories` clauses per pillar | `live_profile.py:193` |
| **DSI** | per-category `presence_conf = min(count / 5, 1)` | **5** clauses per category | `live_profile.py:247` |
| **AIGMS** | per-factor `min(count / 2, 1)` | **2** clauses per factor | `live_profile.py:291` |

PGMS pillar thresholds (from `config/org_profile_weights.json`, `n_categories × 3`):
| pillar (weight) | categories | saturates at |
|---|---|---:|
| governance_infrastructure (0.30) | retention, cross_border, sensitive_data | **9** |
| operational_controls (0.30) | data_sharing, tracking_cookies | **6** |
| transparency_practices (0.20) | ai_automated_decisions | **3** |
| consumer_rights_support (0.20) | consumer_rights | **3** |

**Factual finding:** the saturation divisors (`× 3`, `/ 5`, `/ 2`) are **hardcoded in `live_profile.py`, not in the config** — unlike the weights/category maps. If any threshold change is approved (Option 2), those constants should move into `config/org_profile_weights.json` to stay consistent with "nothing hardcoded."

### 2.2 Evidence of the effect (diagnosis §4a/§4b, labeled recompute)
| dimension | as-stored (ALL clauses) | noise-excluded (CLEAN) | delta |
|---|---:|---:|---:|
| PGMS | 100.0 | **93.33** (still "Leading") | −6.67 |
| DSI | 93.45 | **64.85** | **−28.60** |
| AIGMS | 85.0 | 75.0 | −10.0 |
| F-005 (domains present) | 8 | 8 (none dropped) | 0 |
| F-011 percentile (vs CQS-gated n=73) | 100.0 | **97.49** | −2.51 |

Reading: **noise filtering (Part 1) corrects DSI the most** (−28.6; its `count/5` pads straight to saturation on noise). **PGMS-100 is primarily a saturation effect, not noise** — de-noised PGMS is still 93.33 / percentile 97.49, because pillars max out at 3–9 clauses and this notice covers every pillar many times over. So Part 1 alone will not move a comprehensive notice out of the top band; the thresholds are the deeper cause.

### 2.3 Option 1 — Keep thresholds, document the limitation
- **Change:** none to the formula. Add a spec note that presence-count dims measure **breadth/presence, not depth** above 3–9 clauses (PGMS), 5/category (DSI), 2/factor (AIGMS); reflect that in label/confidence wording.
- **Pros:** zero risk to stored scores and formula versions; fully honest via disclosure. **Cons:** the percentile-100 optic persists for any comprehensive notice; the (now available) noise-filtered counts aren't used to differentiate depth.

### 2.4 Option 2 — Scale thresholds with non-noise clause count  *(exact proposed function; no tuning authority claimed)*
Make each saturation threshold scale to the notice's own **non-noise** clause volume `N`, so a pillar can't max out on a handful of clauses when the notice is large.

Let `N = count of clauses with is_noise = false` in the notice, and define one shared scaler:
```
scale(N) = clamp( N / N_ref , 1.0 , S_max )
```
Then:
```
PGMS pillar depth = min( count / ( n_categories × 3 × scale(N) ), 1 )
DSI  presence     = min( count / ( 5 × scale(N) ), 1 )
AIGMS factor      = min( count / ( 2 × scale(N) ), 1 )
```
- **Proposed constants (PROPOSAL — needs expert calibration; these are placeholders, not tuned):** `N_ref = 40`, `S_max = 3.0`. At `N = 40` the thresholds equal today's (`scale = 1`); at the rehearsal's `N ≈ 94` non-noise clauses, `scale ≈ 2.35`, raising PGMS pillar ceilings to ≈ 21 / 14 / 7 / 7 and DSI/AIGMS proportionally — so depth must be earned, not assumed.
- **Mechanics:** ships as a **new formula version** (`profile_version` bump + a `config` version entry, e.g. `presence_saturation_scaling: {N_ref, S_max}`); **all existing profile versions preserved**; only new/opt-in recomputes use it.
- **Pros:** differentiates comprehensive vs thin notices; consumes the Part-1 noise-filtered `N`. **Cons:** shifts the score distribution → the whole benchmark population must be re-profiled for comparability; `N_ref`/`S_max` require expert calibration against a real sample; risk of over-correction. **I am not asserting these constants are correct — that is the expert's calibration.**

### 2.5 Option 3 — Defer
- **Change:** none now. Ship Part 1 (noise filter) first — it already corrects DSI materially — then re-observe the rehearsal + a broader sample before deciding on any threshold change.
- **Pros:** lowest risk; lets real de-noised data inform the threshold decision. **Cons:** the PGMS/percentile optic remains until a later pass.

### 2.6 Recommendation
**None** — per the task, this memo presents evidence and claims no tuning authority. The choice among Options 1 / 2 / 3 (and any calibration of `N_ref`/`S_max`) is the expert's.

---

## What I need to proceed to PHASE B
1. **Noise-filter rule (Part 1):** approve as drafted, or amend (esp. the `list_fragment` 12-word bound and the `too_short`/list-continuation boundary in §1.7).
2. **Calibration (Part 2):** reply **`approved: option 1`** / **`option 2`** / **`option 3`**. If Option 2, also approve or replace `N_ref` / `S_max` (I will not pick them).

On an explicit "approved: option X" **in this session**, Phase B will: implement the approved noise rule behind `decompose-v2-noisefilter` (old assessments untouched); implement the approved calibration as a new formula version with changelog (old versions preserved); land the F01/F03/schema.md spec edits via the spec-update workflow; re-run the rehearsal notice as a labeled diagnostic and append before/after to `REHEARSAL-DIAGNOSIS.md` §2.5 (stored originals untouched); ship the filter tests; and handle the three dead finding paths (enforcement_matches / DC-005 / children_teens) **only** where a spec defines behavior, otherwise list them for the SME.

**STOP — awaiting approval. No code or spec files have been changed in Phase A.**
