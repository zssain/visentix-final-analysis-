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

| L-008 | 2026-07 | 38 of 56 public tables shipped with RLS disabled → the Supabase anon key could read them via PostgREST (proven: organization 26,690 rows, notice_section 540,912 rows) | RLS was never a migration-governance rule; tables created without `ENABLE ROW LEVEL SECURITY` inherit Supabase's default anon/authenticated grants and are exposed through PostgREST | Migration 0042 (ENABLE RLS + REVOKE anon/authenticated on all 38, deny-by-default); schema.md §5.2 rule 4; `tests/test_rls_enabled.py` asserts rowsecurity=true on every public table; `db/migrations/_TEMPLATE.sql` checklist; anon+service keys rotated | CI guard + Spec | Open (until PR merged) |

| L-009 | 2026-08 | A named measure ("Overall") did not read the same across the report — the same score presented with different precision/label depending on the surface, so a reader could not tell whether two mentions were the same number | Rounding and label choice were made per-section instead of once at the source; no rule said a named measure must be identical everywhere | design-system §2 "one name, one number"; F05 AC-12 (identical value, band, label and color on Cover / Dashboard / sections / PDF / monitoring hero for one snapshot) | Spec | Open (until the AC-12 check exists in the test gate) |
| L-010 | 2026-08 | Bare 0–100 scores were the headline on customer surfaces; a reader cannot act on "60 → 70", and the precision implied a confidence the method does not claim | Presentation inherited the engine's internal resolution; no rule separated *what is computed* from *what is shown* | intelligence-logic §3 presentation rule + design-system §2 "the band leads; the number follows"; F05 AC-11 | Spec | Open (until AC-11 ships) |

<!-- Append new rows above this line. Next ID: L-011 -->

## How a row gets here (the loop)
1. Incident filed or pattern spotted by the weekly audit (`logs/audits/`).
2. Audit files a `feedback` issue phrased as a lesson.
3. Triage agent drafts the spec/guard PR; expert/engineer approve.
4. The merging PR appends the row here with links, status **Closed** (or **Open** if the guard is still pending — the next audit's "Ledger check" will chase it).
