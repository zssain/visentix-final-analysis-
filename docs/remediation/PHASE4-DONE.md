# PHASE 4 — Hardening & Technical Debt — Completion Record

**Date:** 2026-08-04 · **Commit before:** `8c4ed92` · **Commit after:** working tree, **no commits / no branch** per owner instruction (conflicts with `AGENTS.md` §1.4/§1.7 — logged in `logs/decision-log.md`).

## Findings addressed
| ID | What changed | Files | Tests | Status |
|---|---|---|---|---|
| SEC-005 | New in-process rate limiter (`ratelimit.py`): `check_rate_limit` + `client_key` (keys on `user.user_id`, honors `X-Forwarded-For` ONLY when `settings.trusted_proxy`; docstring flags multi-replica ⇒ needs shared store). Throttles: `POST /assessments/` & `/async` (10/min/user), `POST /bulk/jobs` (3/min), `GET /reports/{id}/pdf` (20/min). | `app/services/ratelimit.py` (new), `assessments.py`, `bulk.py`, `reports.py`, `config.py` | `tests/test_sec005_ratelimit.py` (8) | **TESTED** |
| SEC-006 | `brand_color` validated against strict hex/rgb allowlist (anchored regex rejects `}`/`;`/`@import`/`expression()` → falls back to default); `logo_url` allowlisted to `https:` + SSRF host-check (drops on any failure, never crashes). Covers both WeasyPrint + Playwright `set_content` (sanitized at source). | `app/services/report/renderer.py` | `tests/test_sec006_branding.py` (19) | **TESTED** |
| SEC-009 | Partner keys now HMAC-SHA256 with a server-side pepper (`PARTNER_KEY_PEPPER`); verify accepts legacy-sha256 OR HMAC (migration-safe until re-issue); never stores raw keys; rotate/revoke preserved. | `app/services/partner.py`, `config.py`, `.env.example` | `tests/test_sec009_010.py` (9) | **TESTED** (rotation to HMAC = external re-issue) |
| SEC-010 | Untyped `dict` bodies → explicit Pydantic models on `partner.create_workspace/create_api_key`, `quarterly.build`, `eval.post_gold_label` (typed fields + `max_length` + 422s). | `partner.py`, `quarterly.py`, `eval.py` | (in the 9) + 46 partner/quarterly/eval tests | **TESTED** |
| SEC-011 | Webhook URL validated at **save** (`resolve_and_validate`, https-only → 400) and re-validated + **IP-pinned at send** (rebinding defense; refuses + records `failed`, never silently sends). No `logo_url` in notifications (confirmed — only partner/renderer, already SEC-006-guarded). | `app/routers/notifications.py`, `app/services/alerts.py` | `tests/test_sec011_webhook_ssrf.py` (13) + 15 notif/alert | **TESTED** |
| BACK-003 | Narrowed the bare `except:` / silent `except Exception: pass` in `reports.py` (×2), `explain.py` (×2), `live_scoring.py` (×1) → `except Exception` (KeyboardInterrupt/SystemExit propagate) + context logging (no secrets); fallbacks unchanged. Left the ~68 correctly-logging blocks alone. | `reports.py`, `explain.py`, `live_scoring.py` | import + explain (22) + scoring (10) | **TESTED** |
| SEC-008 | Corrective additive migration `0046` re-applies 0011's absent notice-table SELECT policies (idempotent DROP-IF-EXISTS+CREATE; never rewrites history). Drift-guard test + documented live `pg_policies` verify query. | `db/migrations/0046_reapply_notice_rls_policies.sql`, `scripts/db/apply_and_record.py` | `tests/test_sec008_rls_policies.py` (4) | **IMPLEMENTED** (prod apply + live verify = BLOCKED-EXTERNAL) |
| AI-003 | **Governed — documented, not changed.** Accurate presence-proxy limitation note added to methodology (F-005/PGMS count presence, not quality; Phase-5 element-level upgrade = new formula version via spec-update). No formula touched. | `INTELLIGENCE-QUALITY.md` | n/a | **DOCUMENTED** |
| F14-001 | F-014 lineage now labeled `review_stage:"pre_review"` + `validated_basis` note on the fresh path, so the `validated==total` ratio is never presented as completed human validation. Governed formula math unchanged; recompute post-SME-clear is its lifecycle. | `app/services/pipeline.py` | pipeline/score_validity (43) | **TESTED (labeled)** |
| DB-001 | Numbering/order rule + historical aliases documented in the apply manifest (`apply_and_record.py`): order is the explicit manifest (not filename sort), applied files never renamed (checksum ledger), next free = 0048. No renames (would break deployed checksums). | `scripts/db/apply_and_record.py` | (manifest partition test) | **DOCUMENTED** |
| DB-002 | Data-safe migration `0047`: `CHECK (assessment_id IS NULL OR ~ uuid-regex) NOT VALID` on the 5 text tables (constrains new rows, never fails legacy). Full `text→uuid`+FK conversion is destructive → **staged external plan documented** in the migration. | `db/migrations/0047_assessment_id_uuid_check.sql`, `apply_and_record.py` | (manifest partition test) | **IMPLEMENTED** (type conversion = BLOCKED-EXTERNAL, staged) |
| MAINT-001 | Verified zero callers, then deleted `web/src/pages/NewAssessment.tsx` (unrouted, the only `127.0.0.1:8000` fallback) and `app/services/onedrive.py` (no importers); removed dead `VITE_SUPABASE_*` vars from the gitignored `web/.env`. | (deletions) | web gate green | **RESOLVED** |

## Gate (vs baseline)
```
cd web && npx tsc --noEmit → 0
cd web && npx vitest run    → Test Files 11 passed (11) · Tests 94 passed (94)
cd web && npm run build     → 0
./.venv/bin/python -m pytest -q → 5 failed, 1058 passed, 15 skipped in 214.48s (exit 1)
```
### Full backend suite
- **Phase 3:** `1007 passed, 4 failed, 15 skipped`.
- **Phase 4:** `1058 passed, 5 failed, 15 skipped` (+51). New backend tests: SEC-005 (8), SEC-006 (19), SEC-009/010 (9), SEC-011 (13), SEC-008 (4). **Failure accounting (all explained; no new code regression):** 3 environmental live-DB (`test_embeddings` ×2, `test_schema_p1[disclosure_clause]` — PostgREST 500 statement-timeout) + 2 migration-ledger (`test_f02_ingestion_foundation::test_schema_migrations_rows_match_file_checksums`, `::test_apply_now_order_and_step_a_first` — now covering 0043–**0047**, all registered-but-not-applied per the owner's Leave-BLOCKED-EXTERNAL choice; green once applied).

## Migrations (all additive/idempotent; introspected against committed schema first)
- `0046_reapply_notice_rls_policies.sql` (SEC-008) · `0047_assessment_id_uuid_check.sql` (DB-002). Both registered in `APPLY_NOW`; **prod apply = external** (`PYTHONPATH=. ./.venv/bin/python -m scripts.db.apply_and_record`).

## BLOCKED — EXTERNAL / GOVERNED (honest, not faked)
1. Apply migrations 0043–0047 to the live DB (one `apply_and_record` run) → clears the 2 ledger reds.
2. SEC-008 live `pg_policies` verify (query in the test) + SEC-009 key rotation to HMAC (re-issue) + DATA-004 VALIDATE/NOT NULL + DB-002 `text→uuid` conversion — all after a live-DB session/audit.
3. Carried: SEC-007/CRED-001 rotations; EVAL-001 F17 labels + backfill; FIND-001 SME ruling; SEC-003 full RLS.

## AI-003 / DB-001 note
These two are **documentation outcomes by design** (governed formula depth = Phase-5 spec work; migration renumber unsafe on a deployed DB) — recorded accurately rather than changed unsafely.

## Notes for the next prompt (Phase 5 — final verification)
- The one external action that clears the most (2 ledger tests + makes async intake / industry_source / FKs / RLS policies / uuid-checks live) is applying migrations 0043–0047.
- Remaining governed/external items are enumerated above; none block the pilot.
