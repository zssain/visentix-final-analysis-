# Lessons Ledger — Permanent Memory of What Bit Us

**Rule:** every accepted lesson gets a row, and a lesson isn't **Closed** until it links to the change that makes it unrepeatable. Prefer guards in this order: (1) CI/automated guard → (2) spec / AGENTS.md change → (3) checklist/onboarding change. Rows are appended by the weekly audit loop (audit report → feedback issue → spec PR → row here); humans may also add rows directly.

When someone asks "why does the spec insist on X?" — the answer should be findable here.

| ID | Date | What happened (one line) | Root cause | Guard created | Level | Status |
|---|---|---|---|---|---|---|
| L-001 | 2026-02 | RLS policies caused infinite recursion / NULL `auth.uid()` broke access | Policies referenced themselves; auth context assumptions untested | Regression tests kept in suite; RLS re-audit item in F10 | CI guard | Closed |
| L-002 | 2026-03 | JWT verification errors leaked internal detail in responses | Error handler returned raw library messages | Security gate removed detail leakage; rule folded into F10 hardening | Spec + code | Closed |
| L-003 | 2026-06 | Early UI colored a falling exposure score red (improvement shown as bad news) | Delta colors keyed to direction, not meaning | DDR-009 + single `trendColor` helper in `scoreBands.ts`; rule in AGENTS.md design quick-reference | Spec + single-source constant | Closed |
| L-004 | 2026-06 | Static `n=30` cohort sizes appeared across screens | Display values hardcoded during prototyping, never registered | MOCK TRACKER discipline (M-12) + AGENTS.md Hard Rule 7 (honest displays); spec-guard PR checks | Spec + CI habit | Closed |
| L-005 | 2026-07 | "SSRF-Protected" badge nearly shipped to customer UI | Engineer register leaked into customer register | Register rule in design-system.md §4 + AGENTS.md Hard Rule 8 | Spec | Closed |
| L-006 | 2026-07 | `organization_intelligence_profile` writes silently 400'd for weeks, masking unapplied migration 0014 | A REST POST in `_ensure_org_profile` had no status check, so failed inserts were swallowed (no raise, no log) | `_ensure_org_profile` now raises/logs on non-2xx + regression test `tests/test_ensure_org_profile.py` (mocked failing POST → error surfaced) | CI guard | Open (until PR merged) |

| L-007 | 2026-07 | Permissive test double masked a type mismatch: framework wrote text into `source_record.version_id` (INTEGER) — tests green, live 400'd | In-memory fake stored any Python value without checking the real column type | Schema-typed fakes (`tests/ingestion_fakes.py`): reject writes whose type wouldn't survive Postgres; type map derived from `db/migrations` (+ live snapshot for pre-existing `source_record`), with a migration↔live drift test | CI guard | Open (until PR merged) |

<!-- Append new rows above this line. Next ID: L-008 -->

## How a row gets here (the loop)
1. Incident filed or pattern spotted by the weekly audit (`logs/audits/`).
2. Audit files a `feedback` issue phrased as a lesson.
3. Triage agent drafts the spec/guard PR; expert/engineer approve.
4. The merging PR appends the row here with links, status **Closed** (or **Open** if the guard is still pending — the next audit's "Ledger check" will chase it).
