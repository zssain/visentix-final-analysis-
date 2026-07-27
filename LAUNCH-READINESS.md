# Launch Readiness — Stage 3 (2026-07-27)

**By:** implementing engineer. Continues [`ENGINEERING-CLOSEOUT.md`](ENGINEERING-CLOSEOUT.md). Scope: production hardening, exemplar triage, deploy prep, and a dress rehearsal that stops at the human gate. **You approve nothing client-facing; neither did I.**

Branch `F02-unify-classification` — commits this stage: `0824c7d` (pilot nav), `2502bf9` (exemplar triage), `015ff8e` (auth hardening + isolation). Suites green: **backend 775 passed / 15 skipped**, **frontend 86 passed**.

---

## What's done (verified)

### Workstream A — git hygiene
- Uncommitted `App.tsx` explained (partial nav-masking of mock surfaces) and **completed**: all post-MVP surfaces (M-15..M-28: Quarterly, Bulk, Crosswalk, Rewrite, Trust Center, Partner, Vendors) hidden from nav behind `VITE_PREVIEW_SURFACES` (default off → pilot-clean). Branch pushed; PR to open at the link below.

### Workstream B — exemplar triage
16 exemplars → **9 kept** (English, de-id-passing), **7 deactivated** (reversible): 6 non-English + 1 de-id leak. Per-domain now: AI 1 · CR 2 · RT 2 · TRK 1 · DC 2 · XB 1; SH/SEC honest absence. Details + domain-fit flags: [`logs/audits/exemplar-triage-2026-07-27.md`](logs/audits/exemplar-triage-2026-07-27.md). Content sign-off is human — see [`SME-REVIEW-CHECKLIST.md`](SME-REVIEW-CHECKLIST.md) §1.

### Local smoke test (post-hardening)
Booted the backend locally and exercised the Stage-3 changes: `/health` OK; `/api/formulas` → 14; monitoring org-scoping enforced (admin w/o `org_id` → 400); login rate-limit fires. **Caught a real bug:** `GET /review/gate-mode` was shadowed by `GET /review/{assessment_id}` (registered first) — so M-13's gate-mode *read* was broken in the shipped closeout (and `/review/exemplars` too). **Fixed** (`81794f5`): catch-all registered last; verified live `{"mode":"strict"}` + regression test. Confirmed **live prod gate mode = STRICT** (no `platform_setting.gate_mode` row → safe default).

### Workstream C — auth hardening + tenant isolation
Full audit: [`RLS-AUDIT.md`](RLS-AUDIT.md).
- **5 cross-tenant gaps fixed** (a customer could read other orgs via `list_assessments`, `dashboard-stats`, `get_report`, `/pdf`, `explain`) + 7 regression tests. RLS verified enforced live (anon probe: 0 rows leaked).
- **Login rate-limiting** (per-account/per-IP, honest copy) + test.
- **Gate mode defaults to STRICT** (expert_review) — a fresh prod never shows drafts + test.
- **`local_users.json`** untracked + ignored + removed from the Docker image.

---

## Deploy status (Workstream D) — **owner action required**

Backend target: **Azure Container Apps** (`visentix-api.salmoncoast-f5a3917f.eastus.azurecontainerapps.io` per `web/.env.example`). Frontend: **Cloudflare Pages** (`cd web && npm run deploy`). Runbook: [`docs/DEPLOYMENT_AZURE.md`](docs/DEPLOYMENT_AZURE.md).

Prepared here:
- ✅ Env split verified (`app/config.py`: `app_env` / `is_production` / `cors_origins`).
- ✅ Secrets audit: **no real secret is committed** — `.env.example` uses dummy placeholders; `.env`/`web/.env` are gitignored. **One finding:** `local_users.json` (demo PBKDF2 hashes) is in **git history** → rotate demo passwords before prod; history rewrite needs your ok.
- ✅ Dockerfile no longer bakes `local_users.json` into the image.

**I did not deploy** — it needs credentials/access I don't have and shouldn't handle:
1. [ ] Owner supplies prod env vars to Azure (Supabase URL + **service-role key**, `SUPABASE_JWT_SECRET`, `APP_ENV=production`, CORS origins) — never in git.
2. [ ] **Provision users in prod** (the image no longer ships them): DB seed users (RLS-AUDIT §5 "C1b") or mount `local_users.json` as an Azure secret. Until then `/auth/login` returns 401 for everyone.
3. [ ] Build/push image → `az containerapp update`; run migrations 0001-0032 against the prod DB; confirm `/health` + `/docs`.
4. [ ] Deploy web to Cloudflare pointing at the prod API; smoke-test login → intake → report → monitoring → admin **logged in**.
5. [ ] Confirm prod `platform_setting` has **no** `gate_mode` row (or it's `strict`) so the safe default applies.

## Dress rehearsal (Workstream E) — **blocked on owner inputs**

Cannot run: it needs (a) the deployed prod stack above and (b) a **pilot notice** (`PILOT_ORG_NAME + NOTICE_URL`, or your go-ahead to use a public retail notice labelled "rehearsal") — that input was left as an unresolved placeholder in the brief.

When ready, the rehearsal (gate mode **STRICT**) must verify each stop live — verified-source badge → decomposition → classification → cohort assignment (live n) → scores+VCI → findings in the SME queue — then **STOP**: report shows the gold DRAFT watermark, not client-deliverable. Then re-run the (drift-fixed) [`docs/DEMO_RUNBOOK.md`](docs/DEMO_RUNBOOK.md) end-to-end. I can drive a **local** rehearsal instead if you'd prefer — say the word and name the notice.

---

## Remaining human actions, in order

1. **Open the PR** (branch pushed): https://github.com/zssain/visentix-v2--MVP/pull/new/F02-unify-classification
2. **Approve the push of** `2502bf9` + `015ff8e` (local-only; I held them pending your ok).
3. **Deploy** (Workstream D checklist above) — provide prod secrets + provision users.
4. **Provide the pilot notice** (or approve a public-notice rehearsal); then run the rehearsal to the gate.
5. **SME re-review** — work [`SME-REVIEW-CHECKLIST.md`](SME-REVIEW-CHECKLIST.md): exemplar domain-fit repick, crosswalk rows, OD-01..05 confirmation.
6. **Product decisions** — OD-09 (industry), F-013 severity thresholds, OD-07/08.
7. **Rotate demo passwords** (git-history exposure) before real users.
8. **The final act** — SME approves → snapshot freeze → teal ribbon → pilot delivery (Success Metric #1). Engineering never does this.

## Deferred (with reasons)
- **C1b** seed-users→DB + **C2** token-version role-change rejection — touch the live login path; documented with a plan in RLS-AUDIT §5, to do with you.
- **Login rate-limit is per-replica** (in-memory) — fine for a single-replica pilot; shared store needed for multi-replica.
- **Part-B / `clause_obligation`** — still blocked on the clause-embedding backfill (untouched).
