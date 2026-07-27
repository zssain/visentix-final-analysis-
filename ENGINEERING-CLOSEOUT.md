# Engineering Closeout — 2026-07-27

**Prepared by:** implementing engineer. Continues [`PILOT-READINESS.md`](PILOT-READINESS.md) (the data-readiness pass). This pass is the **engineering closeout**: finish every remaining MVP mock-tracker item (M-01..M-14), close the two Workstream B report-section gaps, and leave the app ready for hardening + pilot delivery.

> Everything here is code-verified with the full suite green. No client snapshot was approved or frozen (human gate). No formulas, weights, thresholds, or the OD-09 mapping were changed. `approve_and_freeze` and every snapshot-approval path were left untouched.

---

## 1. KNOWN STATE re-verified live (before any change)

All claims from the readiness pass confirmed against live Supabase:

| Claim | Result |
|---|---|
| Cohorts retail / healthcare / fintech | **25 / 31 / 23** ✓ |
| `disclosure_clause.is_exemplar=true`, all `approved` | **16** ✓ |
| `formula_version.description` populated | **14/14, 0 NULL** ✓ |
| Gate-mode real at `/review/gate-mode` | ✓ |
| `/admin/trigger-assessment` was a stub | ✓ (`not_implemented`) |

**Drift found** (documented in schema.md §5.4): the live `monitoring_event` table has **no `organization_id`** (schema.md §2.8 declared one, never applied) and `trigger_type='hash_change'`; the declared **`alert` table does not exist** live; F-013→severity band thresholds are **undefined** (`formula_version.thresholds` is NULL). Handled honestly (see §2), never fabricated.

---

## 2. Endpoints added

| Method + path | Purpose | Source of truth |
|---|---|---|
| `GET /api/monitoring/trend?org_id` | F-012 trend deltas (M-06) | stored `derived_data_item` history → versioned `compute_f012`; single snapshot → `baseline_established` |
| `GET /api/monitoring/events?org_id` | Change feed (M-07) | `monitoring_event`, org-scoped via `source_record.url`↔`organization.domain`; `trigger_type` normalized |
| `GET /api/monitoring/alerts?org_id` | Alert center (M-08) | stored F-013 `alert_escalation` + **resolved** `enforcement_record` only |
| `POST /admin/trigger-assessment` | Real batch re-assessment (M-14) | reconstructs `DecomposedNotice` from stored rows → `score_and_persist`; run_id = `ingestion_run` row |
| `GET /api/formulas` | Plain-English formula descriptions (M-10) | `formula_version.description` (14/14) |
| (extended) `POST /assessments` | now returns `ssrf_protected` (M-02) | true only when the source URL passed SSRF validation |

All monitoring/formula routes are org-scoped per F10 (customer → own org; sme/admin pass `org_id`) and carry VCI + `formula_version` on every scored payload.

New backend files: `app/routers/monitoring.py`, `app/services/monitoring.py`, `app/routers/formulas.py`, `app/services/reassessment.py`.
New frontend: `web/src/pages/customer/MonitoringHero.tsx`.

---

## 3. Mock-tracker deltas (M-01..M-14 all Replaced)

| Mock | Was | Now |
|---|---|---|
| M-01, M-04, M-11 | Replaced (prior) | unchanged |
| **M-02** | Open (badge absent) | Real `ssrf_protected` "✓ Verified source" badge (register-safe) |
| **M-03** | In progress | BenchmarkLanguage exemplars from `disclosure_clause.is_exemplar`; honest absence per domain |
| **M-05** | Open | AdvisorNote prose from frozen snapshot only; no house-voice fallback + regression test |
| **M-06/07/08** | Open (surface absent) | Monitoring backend + `MonitoringHero` (sparkline/feed/alerts) |
| **M-09** | Open (`S-2041`) | Authoritative `report_snapshot.id`/frozen-at threaded into the provenance ribbon |
| **M-10** | In progress | `GET /api/formulas` → real descriptions in lineage drawers |
| **M-12** | Open | Fixtures cleaned; exit-gate grep (`S-2041`/`n=30`/`142/31/12`) clean across `src/` |
| **M-13** | In progress | Console GET/POST the real `/review/gate-mode` |
| **M-14** | Open (stub) | Real batch → `ingestion_run` run_id; Console button wired |
| M-15..M-28 | Open | **stay Open** (post-MVP F11–F16 surfaces) — verified their `mockData.ts` is imported only by their own page dirs, never by report sections or the customer/sme/admin core routes |

## 4. Workstream B (report-section gaps) closed

1. **BenchmarkLanguage diff toggle** — word-level LCS diff; gold = exemplar adds, warm-gray strikethrough = your notice drops; **off by default**, `aria-pressed` accessible.
2. **Guardrail coverage** — `guardrails.test.ts` now renders `Recommendations.tsx` + `RiskReduction.tsx` and scans their static copy against `scripts/data/banned_terms.txt`.
3. **Exit gate B re-verified** — byte-identity + PDF-render tests present (`test_report_assembly.py`); DDR-007 `IntelligenceMark` on **all 12** section components (grep-confirmed).

---

## 5. Tests

- **Backend:** `pytest` **764 passed / 15 skipped / 0 failed** (+18 vs the readiness pass: `test_monitoring_api.py` ×12, `test_reassessment.py` ×6, `test_formulas_api.py` ×2 — some overlap counted once).
- **Frontend:** `vitest` **86 passed** (+7: monitoring/report-section behaviors); `tsc -b` clean; `vite build` clean.
- Every bug/behavior added a regression test (trend baseline, unresolved-enforcement exclusion, org-isolation 403, advisor-absence, diff-toggle state, trigger validation).

---

## 6. Deferred (with reasons)

| Item | Why |
|---|---|
| Full **AdvisorNote expansion from an alert** (F07 AC-3) | The alert payload carries F-013 + finding lineage + resolved-enforcement refs, but not the full finding record. The alert center surfaces those honestly; opening a complete AdvisorNote needs a finding join — a follow-up, not faked. |
| `monitoring_event.organization_id` column + backfill | Backfilling each event's org from `source_record.url` would be fuzzy; scoping at query time is honest today. A future additive migration can add the column. |
| F-013 → severity **band thresholds** | Undefined anywhere (expert-owned). Severity shown only from stored `monitoring_event.severity`; not invented. |
| **Part-B / `clause_obligation`** | Untouched — blocked on the clause-embedding backfill (2.8% populated), per PILOT-READINESS. |
| M-15..M-28 backends, SaaS cohort | Out of MVP scope. |

---

## 7. Remaining checklist for hardening + pilot delivery

**Human-gated (must clear before client delivery):**
- [ ] **SME re-review** of every `ai_reviewed` item: the 16 exemplars — ⚠️ several are **non-English or appear domain-mismatched** (data quality, surfaced by M-03 wiring), the sic/ftc crosswalk rows, and the OD-01..05 closures (owner Teams confirmation).
- [ ] **OD-09** (Entertainment & Media industry) — still open; exclude affected orgs from cohorts until resolved.
- [ ] **SaaS-gap** decision — pilot is a retailer (n=25), so covered either way; confirm.
- [ ] **F-013 severity thresholds** — expert to define the band mapping (or confirm severity stays event-sourced).
- [ ] **Client report snapshot approval / freeze** (`approve_and_freeze`) — never performed here; human only.

**Engineering hardening (Workstream D):**
- [ ] Auth hardening — move seed users to DB, token rotation/expiry review, rate-limit login, RLS audit.
- [ ] Deployment — production API host, Cloudflare Pages deploy, env-split config, secrets audit.
- [ ] Runbook — re-run `DEMO_RUNBOOK.md` end-to-end against production; record a fallback demo.
- [ ] (nice-to-have) Consider hiding the post-MVP F11–F16 routes (still on mock data, M-15..M-28) from pilot nav.
- [ ] Pilot delivery — one real design-partner notice through the full pipeline with SME review gate ON, delivered as an approved (teal-ribbon) PDF.

---

## 8. Files & spec sync

- **Code:** new files in §2; edits to `app/main.py`, `app/routers/admin.py`, `app/routers/reports.py`, `app/routers/assessments.py`, and the report/customer/admin frontend.
- **Specs (via spec-update discipline):** `mock-tracker.md` → v2.1; `F01`/`F05`/`F07`/`F09` status + changelogs; `schema.md` → v1.3.3 (§5.4 monitoring reconciliation); `AGENTS.md` regenerated + `--check` clean; `logs/decision-log.md` appended.
- **Not touched:** `approve_and_freeze`, formulas/weights/thresholds, OD-09 mapping, `clause_obligation`, historical snapshots, `web/src/App.tsx` + `extraction_report.json` (pre-existing).
