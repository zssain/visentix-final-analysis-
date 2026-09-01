# RLS & Tenant-Isolation Audit — 2026-07-27 (Stage-3 Workstream C4)

**By:** implementing engineer. **Scope:** F10 org isolation for every client-readable path before pilot. **Result:** RLS is enforced live (defense-in-depth); the **primary** control — application-level org-scoping in the FastAPI routers — had **5 cross-tenant gaps, all now fixed with regression tests.**

## 1. Trust boundary (important)

The React app **never reads Supabase tables directly** — there are no `supabase.from().select()` calls; every data read goes through the FastAPI `api` client (`web/src/lib/api.ts`). The server uses the **service-role key**, which **bypasses RLS**. Therefore:

- **Primary control = application-level authorization** in each FastAPI route (`require_role` + org-scoping). This is where isolation must be enforced.
- **RLS = defense-in-depth** for the anon-key path (and any future direct client reads).

## 2. Application-level audit — gaps found & fixed

Each was a customer able to read another org's data via a valid token (F10 AC-1 violation). Fixed + covered by `tests/test_org_isolation.py` (7 tests).

| Endpoint | Gap | Fix |
|---|---|---|
| `GET /assessments/` | No org filter — returned **all orgs'** notices | Customer → `organization_id=eq.{own}`; no-org customer → `[]`; sme/admin → all |
| `GET /findings/dashboard-stats` | No org filter — every customer saw the **globally-latest** org's scores/findings/snapshot | Customer → all queries scoped to own org; no-org customer → empty stats |
| `GET /reports/{id}` | `customer_can_view` checked only gate/approval, **not ownership** — any assessment's report was readable | `assert_customer_owns()` runs **before** the gate check → 403 on cross-tenant |
| `GET /reports/{id}/pdf` | No ownership check — any org's PDF exportable | `assert_customer_owns()` |
| `GET /reports/{id}/explain[/all]` | No ownership check | Customer org must match the notice's org → 403 |

`sme`/`admin` are unaffected (they oversee all orgs by design). The monitoring routes (`/api/monitoring/*`) already enforced org-scoping (`_resolve_org`, shipped in the closeout).

## 3. RLS layer — present and enforced live

Policies exist (migrations `0004_phase2_profiles_rls`, `0011_live_assessment_isolation`): RLS **ON** with per-org `SELECT USING (… profiles.organization_id = auth.uid() … OR sme/admin OR organization_id IS NULL public-seed)` on `profiles`, `risk_finding`, `report_snapshot`, `derived_data_item`, `organization_intelligence_profile`, `privacy_notice`, `notice_section`, `disclosure_clause`.

**Live verification (anon-key probe, 2026-07-27):** an unauthenticated anon `GET` returns **0 rows** from `report_snapshot`, `risk_finding`, `derived_data_item`, `organization_intelligence_profile` — RLS filters everything (no `auth.uid()` → only public rows, of which these have none). **No cross-org leak via the anon path.** ✅

**Caveat:** RLS keys off Supabase `profiles.organization_id = auth.uid()`. The app's **custom local JWT** (local_users.json / DB) is verified by FastAPI, not Supabase, so `auth.uid()` does not resolve for local users — which is why direct anon reads see nothing. This is safe *today* only because the client never uses the anon key for data. If direct client reads are ever added, local users need real Supabase `profiles` rows (ties into §5).

## 4. Secrets finding — `local_users.json`

`local_users.json` (PBKDF2 password hashes + salts for demo users) **was committed** and remained tracked despite being in `.gitignore` (gitignore doesn't untrack). **Fixed:** `git rm --cached` (now untracked + ignored). **⚠️ Still in git history** — the demo hashes are recoverable from past commits. History rewrite needs owner approval (not done unprompted). **Recommendation:** rotate all demo passwords before/at production; when real users exist, none of these seed credentials should be valid.

## 5. Recommended follow-ups (prod-gated — need Supabase access + owner in the loop)

Not applied here because they touch the live login path / prod DB and carry lockout risk; they should be executed with the owner:

- **C1b — move seed users to the DB.** Add a `local_user` table (or Supabase `auth.users` + `profiles`), import from `local_users.json`, and have `/auth/login` read from the DB (JSON fallback during transition). Delete the file from the deployable image (already gitignored). Plan: additive migration + one-time import script + `_load_users()` DB-read.
- **C2 — reject tokens on role change.** Add a `token_version` (per user) to the login payload and re-check it in `get_current_user`; bump on any role change → outstanding tokens rejected. Depends on C1b (DB users). Token TTL is already short (24h).
- **Rate-limit is per-replica.** The new login limiter (`app/routers/auth.py`, C3) is in-process; Azure Container Apps can run multiple replicas, so hard limits need a shared store (e.g. `platform_setting`/Redis). Adequate for a single-replica pilot.

## 6. Done in this pass

- ✅ 5 application-level cross-tenant gaps fixed + 7 regression tests (`tests/test_org_isolation.py`).
- ✅ Login rate-limiting (per-account + per-IP, honest register-safe copy) + test.
- ✅ Gate mode **defaults to STRICT** (expert_review) when `platform_setting` is empty — prod never shows drafts by default + test.
- ✅ `local_users.json` untracked + ignored; history exposure flagged for rotation.
- ✅ RLS confirmed enforced live via anon-key probe.

## 7. Remediation update (2026-08-04 — Phases 1–4)

- ✅ **SEC-001 (Critical) closed** — `GET /findings/` was returning every org's findings to any customer; now org-scoped via the new centralized `app/services/tenancy.py::customer_org_scope` (no-org customer → empty, never platform-wide).
- ✅ **SEC-003 minimum backstop** — a single `customer_org_scope` chokepoint (used by findings list + dashboard-stats) instead of per-route ad-hoc filters; a backend sweep of every router found **no cross-tenant leak beyond SEC-001**. The permanent guard is the extended cross-tenant contract test (`tests/test_org_isolation.py`, `CAPTURE_ROUTES` — org A vs B, scoped/empty/platform-wide, + SME-route role rejection). **Full RLS-under-user-JWT remains the Phase-2/architectural direction (deferred).**
- ✅ **SEC-008 corrective** — migration `0046_reapply_notice_rls_policies.sql` re-applies 0011's absent `privacy_notice/notice_section/disclosure_clause` SELECT policies (ledger drift); `tests/test_sec008_rls_policies.py` guards the migration set. **Live `pg_policies` verify + prod apply = BLOCKED-EXTERNAL** (query in the test).
- ✅ **SEC-011** — the alert `webhook_url` SSRF sink is closed: validated at save (https + SSRF check) and re-validated + IP-pinned at send.
- Runtime still uses the service-role key (RLS bypassed at runtime by design); the app-layer chokepoint + contract test is the interim isolation guarantee until the user-JWT/RLS path lands.
