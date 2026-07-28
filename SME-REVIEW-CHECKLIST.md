# SME / Owner Review Checklist — before pilot delivery

**Prepared by:** implementing engineer (`ai_reviewed`). Everything below is staged and reversible; **none of it has been approved or frozen** — those acts are reserved for the human owner/SME. Work through top to bottom; the final act (approve → snapshot freeze → teal ribbon) is the last line.

---

## 0. F17 evaluation harness — SME inputs (gates results, not the build)

The measurement harness is built and green, but its **results are honestly "awaiting SME labels"** until you do these. The harness pre-fills nothing and fixes nothing.

- [ ] **Label the gold set (OQ-2).** 200 stratified, `is_noise`-excluded clauses are frozen (`logs/eval/gold_set_v1.json`). Export the CSV (`GET /eval/gold-set/export.csv`), fill `gold_domain` / `verdict` / `note` by hand, import (`POST /eval/gold-set/import.csv`). Until then classifier accuracy + VCI calibration are *awaiting* (no number is fabricated). 94 strata cells are under-populated and reported honestly — do not expect all cells filled.
- [ ] **Bless or swap the 3 golden notices (OQ-1).** Engineer proposed `retail_strong` / `retail_mid` / `retail_weak` (rationale in `tests/golden/notices/*.json`, marked PROPOSED). Confirm they're representative retail notices spanning strong/mid/weak, or swap them; then re-freeze (`python scripts/eval/golden_notices.py`). The CI diff protects them thereafter (only a cited `formula_version` change may alter a golden file).
- [ ] **[EXPERT] F-002 severity semantics.** The harness reports (does not assert) that `compute_f002` treats disclosure severity as clause **proportion** (volume), so "weaken a domain → exposure worsens" does not hold cleanly. Confirm whether severity should track disclosure **volume** or **quality** — any change is expert-owned (F17 changes nothing). See `INTELLIGENCE-QUALITY.md` §3.

---

## 1. Exemplars (F06 / M-03) — content sign-off

Full audit: [`logs/audits/exemplar-triage-2026-07-27.md`](logs/audits/exemplar-triage-2026-07-27.md). 16 → **9 kept** (English, de-id-passing). 7 were deactivated (reversible) for objective failures — confirm you agree, then move on:

- [ ] Agree with the 7 deactivations (6 non-English + 1 de-id leak `f95bbc0b` "Aetna"). To reverse any: set `is_exemplar=true, exemplar_status='approved'`.
- [ ] **Domain-fit repick (the real content call):** these kept exemplars read off-domain — repick or deactivate each:
  - `e8c4cc3b` (AI) — accessibility/format notice, not automated-decisions
  - `1bee4446` (XB) — financial-info collection, not cross-border
  - `f48f5e3a` (RT) — Argentina regulator contact, not retention
  - `19957a08` (RT) — cookie-table fragment
- [ ] **SH + SEC have no exemplar** (honest absence in the report). Optional vetted candidates to clean + approve are listed in the triage doc (SH: `6ef2219a`/`131be3cc`/`343004ac`; SEC: `7304264e`/`8e0d1794`).
- [ ] **De-id gap** to note: `validate_deidentification` only blocks a known-org token list — names like "Aetna"/"Brex" slip through. Eyeball every exemplar for company names before delivery.

## 2. Expert-gated config (ai_reviewed) — confirm

- [ ] **`sic_industry_map`** — 11 rows corrected to the canonical 10-industry taxonomy (`ai_reviewed`). Promote to `approved` (SME) before they feed profiling/cohorting; 2 "Entertainment & Media" rows remain `draft` pending **OD-09**.
- [ ] **`ftc_topic_domain_map`** — 25 rows (11 domain-mapped, 14 honest NULL). Confirm the descriptive mappings.
- [ ] **OD-01 … OD-05** — Decided as `ai_reviewed`, adopted verbatim; needs owner **Teams confirmation** to close (see `logs/open-decisions.md`).

## 3. Open decisions — owner/expert only (do NOT let engineering pick)

- [ ] **OD-09** — no canonical industry for "Entertainment & Media" (SIC 2700-2799, 7800-7999). Add an industry or remap; until then those orgs stay excluded from cohorts.
- [ ] **F-013 alert severity thresholds** — undefined anywhere (`formula_version.thresholds` is NULL). The alert center currently surfaces severity only from a stored `monitoring_event.severity` and invents no bands. Decide the F-013-score → High/Medium/Severe mapping (expert-owned), or confirm severity stays event-sourced. (schema.md §5.4)
- [ ] **OD-07 / OD-08** — benchmark_cluster naming; gate-mode enum names (`strict` vs `expert_review`). Still open from the prior audit.

## 4. The pilot report — findings review (F06 workbench)

Run during the dress rehearsal (see `LAUNCH-READINESS.md` §Rehearsal). Gate mode **STRICT**, so the report is not customer-visible until you approve.

- [ ] Open the SME queue: `GET /review/queue` (SME/admin token).
- [ ] For each finding: **Confirm** (`{"action":"confirm"}`), **Edit** (`{"action":"edit","edited_fields":{…}}`), or **Dismiss** (`{"action":"dismiss"}`) via `POST /review/finding/{assessment_id}/{finding_id}`.
- [ ] Verify dismissed findings are absent from the approved report; edits persist.

## 5. The final act — human only

- [ ] When satisfied: **approve** the assessment (`POST /review/{assessment_id}/approve`) → this calls `approve_and_freeze` (approval + immutable snapshot in one transaction) → the report flips to the **teal Reproducible ribbon** and becomes client-deliverable.

> Engineering never performs this step. Until it happens, the report carries the gold **DRAFT** watermark and is not a deliverable.

---

## 6. Rehearsal diagnosis items (from `REHEARSAL-DIAGNOSIS.md`, 2026-07-28)

Surfaced by the 1‑800‑Flowers rehearsal. The one clear bug (cohort CQS gate) is already fixed; the rest are **expert/SME judgment** (no tuning was done):

- [ ] **Sanity-check `AI-004` on the rehearsal report** — it fired solely because the AI domain had thin coverage (3 clauses → maturity 45 < 70), not because of a specific defect. Confirm that reads correctly for a comprehensive notice.
- [ ] **PGMS-100 — cause diagnosed (`REHEARSAL-DIAGNOSIS.md` §4), two expert decisions needed.** Not a degenerate-default bug (empty input → 0.0, verified). The percentile-100 has two independent, formula-owned drivers: **(a)** 46% segmentation-noise clauses inflate the presence-count dimensions (DSI −28.6 when excluded, PGMS −6.67, AIGMS −10) → **decide: approve a decomposer noise-filtering rule (spec-first)**; **(b)** PGMS pillar-saturation thresholds (`n_categories × 3` = 3–9 clauses) max out on a modest notice — de-noised PGMS is still 93.33/"Leading", percentile 97.49 → **decide: whether the PGMS/DSI presence-count thresholds should scale with notice depth/quality** (a calibration decision, not engineering). No tuning was done.
- [ ] **Finding-coverage gaps** (§2) — decide priority: (a) enforcement lineage on findings is **dead** (`pipeline.py` passes `enforcement_matches=[]`); (b) `DC-005` can't fire for ≥4-domain notices; (c) `children_teens` has no finding-type; (d) firing is dominated by clause **count**, not quality (ambiguity trigger 0.05 rarely crosses). Any threshold/rule change is expert-owned.
  - **Phase B determination (2026-07-28, engineer — none code-fixable, all need the spec/codex):** Checked against the governed `finding_type` catalog (8 codes live: AI-004, CR-001, XB-001, SH-002, DC-005, RT-003, SEC-002, TRK-007) and F08 (finding codes are governed methodology — engineer must not invent one).
    - **(a) Enforcement lineage** — `select_findings` already builds `finding.enforcement_ids` from an `enforcement_matches` list, but intake hardcodes `[]`. **Missing from the spec:** F-004 is defined at the **notice** level (`_compute_live_f004`), and no spec defines a **per-finding** enforcement-match rule (which enforcement records attach to which finding, at what similarity/domain threshold). Needs an expert-defined matching rule before wiring — **not** an engineer default.
    - **(b) DC-005** — the catalog defines it as *"Privacy Notice Completeness Deficiency"* on domain `other`; firing only when `<4` non-other domains is **consistent with that definition** (a thin/incomplete-notice finding). **By-design, not a dead path** — no change unless the expert redefines DC-005.
    - **(c) `children_teens`** — the governed catalog has **no** finding code for this domain (7 domains + `other`→DC-005; children_teens absent). A `children_teens` finding needs an expert-authored codex entry (code, title, definition, default severity, `regulator_relevance`, recommendation link). **Cannot add a mapping without the code — listed for the SME, not invented.**
- [ ] **Segmentation noise** (§3) — 49% of sections and 46% of clauses on the rehearsal notice were nav/heading/list-fragment noise, which inflates the coverage proxy and suppresses findings. Decide (SME + eng) whether to filter noise sections pre-extraction. *Decomposer is expert-owned — not changed here.*
- [ ] **Cohort-relaxation disclosure wording** — the dynamic population now discloses the CQS hold-out on the cohort label as `cqs_gated_excluded_N`. Confirm the customer-facing wording for this token (register-safe) before delivery.
