# INTELLIGENCE-QUALITY.md

**Generated:** 2026-07-28 · F17 evaluation harness (measurement only).
This report **measures**; it changes no weight, threshold, taxonomy, or formula. Numbers are real where data exists, else "awaiting SME labels". Every recommendation carries an owner — **[SME]**, **[ENG]**, or **[EXPERT]**.

## 1. Gold set
- Frozen stratified sample: **200 clauses** (8 domains × 5 §8 bands × 3 sources; `is_noise` excluded; **no labels pre-filled**).
- Under-populated strata cells: **94** (reported, not back-filled).
- Human gold labels applied so far: **0**.
- **[SME]** Label the gold set (`GET /eval/gold-set/export.csv` → fill → `POST /eval/gold-set/import.csv`). Until then, accuracy/VCI-calibration below are *awaiting*.

## 2. Classifier eval (gated on labels)
- **awaiting SME labels** — 0 of 200 labeled. No accuracy, confusion matrix, per-source split, or VCI-calibration number is fabricated.
- **[SME]** provide labels; **[ENG]** the harness (`scripts/eval/classifier_eval.py`) runs automatically once labels exist.
- Stability (3× on 50): reported separately as **stability, not accuracy** (deterministic keyword classifier = 1.0 by construction; LLM-path stability is an **[ENG]** follow-up requiring the local model).

## 3. Score validity (perturbation + cited monotonicity)
- **Asserted & passing** (`tests/test_f17_score_validity.py`): **M-1** §7 F-005 (maturity falls when a domain is weakened), **M-3** §7 F-010 (100 − risk), **M-4** §7 F-006 (transparency product), **M-5** §8 VCI (<40 → very-low band, monotone in confidence). Untouched domains stay within tolerance.
- **F-002 — REPORTED, NOT ASSERTED.** `compute_f002` defines *DS = proportion of clauses in each domain* (coupled, Σ=1), so the verbatim §7 formula does not license a clean "weaken → exposure worsens" direction. **[EXPERT]:** confirm whether regulatory severity should track disclosure **volume** (current) or **quality**. The harness reports this; it fixes nothing.

## 4. Golden notices
- 3 **engineer-PROPOSED** retail-cohort notices frozen (strong/mid/weak) with stated rationale; CI diff active (`tests/test_f17_eval.py`). Only a cited `formula_version` change may legitimately alter a golden file.
- **[SME]** bless or swap the 3 picks (OQ-1) — see SME-REVIEW-CHECKLIST.

## 5. Benchmark sanity
- Percentile distributions are checked for well-formedness (monotone, sensible spread); a synthetic strong org lands in the upper half and leaves **no residue** (in-memory only). `tests/test_f17_eval.py`.

## 6. Finding precision (from real SME review actions)
- **no SME review actions yet** — confirm/edit/dismiss rates appear here once findings are reviewed.
- **[SME]** review findings in the workbench to populate this.

## Owners summary
- **[SME]** label the 200-clause gold set; bless/swap the 3 golden notices; review findings for precision data.
- **[EXPERT]** F-002 severity semantics (volume vs quality); any VCI threshold change if calibration warrants.
- **[ENG]** LLM-path stability run; wire the Admin precision panel UI; keep the CI golden diff green.

_The harness fixes nothing based on these results — measurement only._

## Known analysis-depth limitation — presence-proxy scoring (AI-003)

**What it is (accurate, not a bug).** Several scoring dimensions currently measure
disclosure **presence**, not disclosure **quality**. F-005 disclosure-maturity counts
a domain as "present" if the notice has ≥1 clause mapped to it (`present_count` in
`app/services/scoring/formulas.py:217`, comment "proxy — actual element detection is
Phase 5"); PGMS/DSI/AIGMS pillars use `min(count/saturation, 1)`; specificity uses a
readability proxy. So a notice that *mentions* a topic scores like one that discloses
it *well*.

**Why it's not changed here.** These are governed formulas (`intelligence-logic.md` +
the `formula_version` table); depth is a modelling upgrade, not a remediation bug fix.
Redesigning them is out of scope for hardening and requires spec/SME sign-off.

**Consequence.** Alongside empty org context (ARCH-001), this is a second reason
output can read generic. Element-level presence + clause-quality signals are the
**Phase-5** upgrade (a new formula version, old versions preserved per Hard Rule 6),
to be specified via the spec-update workflow. Accuracy of the current classifier is
measured by EVAL-001/F17, not asserted.
