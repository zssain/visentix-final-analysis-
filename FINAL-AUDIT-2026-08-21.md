# Final Repository Audit — 2026-08-21

**Branch:** `F01-F05-qa-remediation`  
**Pre-fix commit:** `5347dd7`  
**Assessment:** **NO-GO for external pilot delivery.** The engineering remediation is necessary and locally verified, but migration 0048 is not applied, the live census could not run from this restricted environment, and the intelligence layer still has 0/200 human gold labels and no SME finding-review actions.

## 1. Command summary

| Gate | Result |
|---|---|
| Empirical pre-fix backend baseline | 1,060 passed · 15 skipped · 35 failed. This was measured before the remediation; the failures were predominantly live-DB/schema/persistence checks. |
| Final backend `./.venv/bin/pytest -q` | 894 passed · 264 skipped · 0 failed · 23 warnings (235.21s) |
| Focused report safety gate | 104 passed (`pdf_determinism`, report/finding reproducibility, tenant isolation, guardrail, report design, integration pipeline) |
| QA/adversarial focused gate | 128 passed; later missing-VCI focused gate 44 passed, 1 pre-existing skip |
| Integration pipeline | 10 passed: the requested eight scenarios plus PDF-contention and missing-report adversarial cases |
| Frontend TypeScript | Pass (`npx tsc -b`) |
| Frontend tests | 11 files · 94 passed |
| Frontend lint | Pass (`npm run lint`) |
| Frontend production build | Pass; masked-surface grep is zero. Vite reports a non-blocking 763.59 kB chunk-size warning. |
| Python syntax | Pass for every changed Python module and script |
| Generated instructions | `scripts/build_agents_md.py --check` passes; AGENTS.md regenerated from schema v1.3.10 |
| Diff hygiene | `git diff --check` passes; no added TODO/FIXME/XXX/HACK/debugger/debug print |
| Corpus census | **Blocked.** `make census` could not resolve the configured Supabase host. The required network escalation was rejected because the tool account hit its usage limit. No workaround was attempted. |

The current run collects more tests than the baseline because this work adds integration, integrity, intake, VCI, heatmap, and concurrency regressions. The high final skip count is produced by the unchanged `conftest.py` external-service/ML auto-skip mechanism while Supabase and sentence-transformers are unavailable. No skip marker or `conftest.py` entry was added.

## 2. Prompt 1–15 implementation evidence

| Prompt | Result | Primary implementation | Regression evidence |
|---|---|---|---|
| 1–2 Heatmap evidence | Evidenced state is structural; empty cells render neutral while regulator baseline remains lineage | `app/services/scoring/heatmap.py`; `app/services/report/renderer.py`; `RegulatorExposure.tsx` | `test_heatmap.py`; `test_qa_report_integrity.py::test_heatmap_render_counts_real_evidence_and_neutralizes_empty_cells` |
| 3 Representative clause | Substantive, minimum-length, highest-confidence selection with stable tie break | `app/services/report/clause_data.py:44` | `test_qa_report_integrity.py::test_representative_clause_is_true_max_wins` and exclusion/tie test |
| 4 Template cleanup | Generated-prose tokens fail closed; customer evidence braces and markup remain escaped evidence | `app/routers/reports.py::_enforce_snapshot_prose`; renderer cleanup | template/customer-evidence tests in `test_qa_report_integrity.py` |
| 5 Compound drivers | Renderer and React read the stored `risk_scores` lineage and stable descending drivers | report renderer; `CompoundRisk.tsx` | compound/report integration tests |
| 6 Clause read path | One notice-section-scoped clause load feeds every report consumer; live schema has no `disclosure_clause.notice_id` | `app/routers/reports.py:238`; `app/services/report/clause_data.py:1` | full-rich and sparse pipeline integration tests |
| 7 Comparator gate | Approved exemplar, same domain, persisted embeddings, governed F-004 floor, and non-weaker maturity signal are all required | `app/services/report/clause_data.py:107`; read-only exemplar-domain audit script | comparator and audit tests in `test_qa_report_integrity.py` |
| 8 Finding traceability | `finding_clause` links resolve to frozen clause/section/source excerpts; no blanket traceability claim | `app/routers/reports.py:624`; Section 6/11 renderers and React | finding/traceability integration tests |
| 9 Cohort methodology | Stored population key/version/date/relaxations/scored counts surface; small cohort is labelled | `app/services/live_scoring.py`; `app/routers/reports.py:764`; Section 4 consumers | tiny-cohort integration test and report integrity tests |
| 10 Direction/taxonomy | Interactive report uses shared polarity logic and controlled domain labels; PDF dashboard uses one explicit registry | `web/src/lib/scoreBands.ts`; `web/src/lib/domainLabels.ts`; renderer dashboard registry | frontend report tests and report integrity tests |
| 11 Recommendation basis | Basis derives from selected-scope obligations, enforcement references, or stored peer context; evidence and authored source note render | `app/routers/reports.py:825`; recommendations renderers | recommendation/guardrail tests |
| 12 Governance questions | No formula change; F-005, F-002, and Section-4 semantics are proposed as OD-10–OD-12 | `DECISION-NEEDED-F005-PRESENCE-PROXY.md`; `open-decisions.md` | source/diff inspection |
| 13 Intake backend | Governed validation, distinct footprint/law scope, immutable per-notice scope, provenance, and race-safe idempotency | `app/routers/assessments.py:250`; `app/services/intake/jobs.py:43`; migration 0048 | intake filter/async tests, including unique-conflict race |
| 14 Intake frontend | Optional progressive profile/practice fields, review/confirm, deliverable copy, and independent multi-job polling | `web/src/pages/customer/Intake.tsx` | `web/src/test/Intake.test.tsx`; TypeScript/lint/build |
| 15 Assessment Scope | Stable inputs and provenance are frozen into Cover front matter and content hash; legacy absence stays honest | report assembly, PDF Cover, React Cover | scope rendering/hash tests and minimal-intake integration test |

## 3. Failures found and fixes

1. **Idempotency race — production defect.** Two same-key requests could both pass the preliminary lookup; the unique-index loser returned the winning job but the route still scheduled a second pipeline. `jobs.create_job()` now marks that conflict as an internal replay and the route returns without scheduling work. Two regression tests cover the store and endpoint.
2. **Missing VCI default — hard-rule defect, pre-existing.** Live report assembly used 25 when confidence was absent, and the interactive dashboard converted absence to 0. Both now preserve `None`/`not_recorded`; PDF and React render honest absence.
3. **Org-axis exemplar tests — stale tests.** Old fixtures expected comparator rows without an assessed organization clause. Fixtures now provide the required org-axis input; approval/de-identification assertions were retained.
4. **Frontend comparator fixture — stale contract.** A fabricated `pending` domain row was replaced with an actual organization clause and an honest no-approved-comparator state.
5. **Network-coupled discovery/URL tests — deterministic test defect.** DNS resolution was mocked only at the external boundary; the full SSRF suite still exercises real validation logic with controlled address fixtures.
6. **Repository lint debt — pre-existing gate failure.** Initial-load effects were deferred to the next task without changing data flow, a Set toggle's unused conditional expression became an explicit branch, quarterly fallback navigation uses `location.assign`, and a constant opacity map moved out of render scope. Full lint is now clean.
7. **Integration test assumptions.** CSS comments contained `url()` and unevidenced cells correctly retain a regulator baseline intensity internally. Assertions were corrected to inspect report body content and neutral rendered classes; production behavior was not weakened.

## 4. Senior-engineer checklist

### Correctness

- [x] Prompt 1–15 behavior is present and covered across modules; see §2.
- [x] Fixes operate on the underlying data path, not cosmetic hiding: the one clause set drives all consumers and mismatch gates suppress unsupported values.
- [x] No TODO/FIXME/XXX/HACK introduced.
- [x] No added debug prints, commented-out replacement implementation, or scratch code. The audit CLI's deliberate JSON stdout is its command output.

### Governance

- [x] Hard Rule 1: canonical guardrail tests pass; scanning added app/web lines against `scripts/data/banned_terms.txt` returned zero matches. Customer evidence containing guarded vocabulary is escaped and remains evidence, not generated prose.
- [x] Hard Rule 3: no formula body, formula weight, scoring threshold, or profiling constant changed. `heatmap.py` adds evidence metadata only. Config additions are intake/display vocabularies plus the already-governed OD-05 value 10.
- [x] Hard Rule 4: displayed findings, comparator language, cohort methodology, recommendation basis, confidence, and scope all carry stored references/provenance or honest absence.
- [x] Hard Rule 5: VCI below 40 suppression and 40/59 boundaries pass; missing VCI no longer receives a plausible default.
- [x] Hard Rule 6: snapshot/content-hash and raw PDF byte-identity tests pass; stored snapshot double-pull does not call live assembly.
- [x] Hard Rule 7: no added `S-2041`, `n=30`, `142/31/12`, or `1,250+` display value. Cohort counts remain stored/live-derived.
- [x] Hard Rule 8: comparator retrieval requires `is_exemplar=true` and `exemplar_status=approved`; approval remains server-enforced through the existing review/de-identification path.
- [x] Hard Rule 9: new customer copy is plain-language; no attack-class name was added to customer screens.
- [x] Migration 0048 is additive/idempotent: one new table, index, RLS enablement, and revoked client grants. No DROP/TRUNCATE/DELETE/destructive ALTER.
- [x] Secret scan of added lines returned no key, token, URL, connection string, or credential.

### Contracts

- [x] Optional intake fields are submitted by `Intake.tsx`, validated by both sync/async endpoints, persisted in 0048, and consumed by report scope/cohort context.
- [x] `HeatmapCell.evidenced`, evidence arrays, methodology, and assessment scope have PDF and React consumers; old snapshots have compatible honest fallbacks.
- [x] TypeScript is clean; no orphaned newly-added field was found.
- [x] Idempotency replay metadata is internal to the intake service/route response and is regression-tested.

### Tests

- [x] Every implemented QA seam has a regression test; `test_integration_report_pipeline.py` exercises cross-module behavior without a live DB/model.
- [x] Empirical pre-fix and final counts are recorded; environmental differences are not presented as fixed live-DB failures.
- [x] No coverage was silently removed. Three old frontend expectations were deliberately replaced: legacy `jurisdictions` became separately asserted footprint/law fields, and two fabricated pending-comparator assertions became organization-language plus honest-absence assertions. External DNS was mocked only at its boundary; no tolerance was loosened.
- [x] No skip was added; `conftest.py` is unchanged.

### Documentation and process

- [x] No mock was introduced; mock tracker therefore requires no new entry.
- [x] OD-10–OD-12 are in the open-decision register and the decision memo.
- [x] F01/F05 specs now state the shipped behavior and testable ACs; schema is v1.3.10.
- [x] Decision log records the report/scope judgments and idempotency race.
- [x] AGENTS.md generated blocks were regenerated, not edited manually.
- [ ] The source-document requirements audit is not produced: both required QA DOCX files are absent. The prompt explicitly prohibits reconstruction.

### Deployment safety

- [x] Production build grep found zero occurrences of all six masked surface names and `/bulk`, `/partner`, `/vendors`, `/crosswalk`, `/trust`, `/rewrite` route literals.
- [x] `gate_mode` and `approve_and_freeze` were not changed.
- [x] SSRF, rate limiting, RLS, and tenancy controls were not weakened; related tests pass.
- [ ] Migration 0048 is authored and registered but not applied to live.
- [ ] Live census/schema validation could not complete because the configured database was unreachable from the sandbox.

## 5. Remaining risks, ranked

1. **Critical — intelligence validity (SME).** `INTELLIGENCE-QUALITY.md:9-13,28-29` records 0/200 human gold labels and no SME review actions. Classifier accuracy, calibration, and finding precision remain unvalidated. Correct plumbing does not prove correct intelligence.
2. **High — deployment state (operator).** Migration 0048 must be introspected against live again, applied through the migration ledger, and verified before the new optional scope fields are accepted in production.
3. **High — requirements-audit evidence (owner).** Supply `Visentix_One_Time_Report_QA_Review_2026-08-18.docx` and `Visentix_Privacy_Notice_Intake_QA_Review_2026-08-18.docx`; only then can `QA-REQUIREMENTS-AUDIT-2026-08-21.md` be created from source.
4. **High — governed score semantics (expert/SME/product).** OD-10–OD-12 must decide F-005 observed elements, F-002 disclosure severity, and PGMS versus F-010 peer position. No proposal has been applied.
5. **High — exemplar content validation (SME).** `PILOT-READINESS.md:77` requires human re-review of approved/AI-reviewed exemplars before client delivery.
6. **Medium — PDF/interactive palette drift (design/product).** The PDF `_RAMP` hex values differ from the canonical TypeScript score-band palette. Direction/polarity is now consistent, but visual color tokens should be reconciled through the design-system/spec process, not silently changed here.
7. **Medium — external integration coverage (engineering/operator).** The final sandbox run skips live-DB/model parametrizations. Run the same suite in the approved networked environment after migration 0048 and retain the output.
8. **Low — bundle size (frontend).** Vite warns that the main bundle exceeds 500 kB; masked surfaces are absent, but future performance work may split the remaining bundle.

## 6. Go / no-go

**Engineering remediation:** ready for review and controlled migration application. Local backend, frontend, lint, type-check, deterministic PDF, guardrail, tenancy, and masked-build gates pass.

**External pilot delivery:** **NO-GO.** Apply and verify migration 0048, run the live census/full external-service suite, obtain the missing source-document audit, close or explicitly accept OD-10–OD-12, and complete human SME validation. Most importantly, external delivery without gold labels and finding-review evidence would demonstrate a reproducible pipeline over an unvalidated classifier—not validated privacy intelligence.

## 7. Second-engineer review focus

Review the one-read clause query against the live PostgREST schema and row limits; verify the 0048 migration/ledger/RLS state; inspect snapshot freeze boundaries for finding excerpts and recommendation evidence; reproduce same-key concurrent intake against live Postgres; and compare PDF/interactive output on rich, sparse, and legacy snapshots. Then have an SME audit the comparator exemplars and begin the 200-clause gold set.
