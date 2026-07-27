# SME / Owner Review Checklist — before pilot delivery

**Prepared by:** implementing engineer (`ai_reviewed`). Everything below is staged and reversible; **none of it has been approved or frozen** — those acts are reserved for the human owner/SME. Work through top to bottom; the final act (approve → snapshot freeze → teal ribbon) is the last line.

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
