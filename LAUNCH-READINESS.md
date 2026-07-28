# Launch Readiness — Stage 3 (2026-07-27)

**By:** implementing engineer. Continues [`ENGINEERING-CLOSEOUT.md`](ENGINEERING-CLOSEOUT.md). Scope: production hardening, exemplar triage, deploy prep, and a dress rehearsal that stops at the human gate. **You approve nothing client-facing; neither did I.**

Branch `F02-unify-classification` — Stage-3 commits: `0824c7d` (pilot nav), `2502bf9` (exemplar triage), `015ff8e` (auth hardening + isolation), `81794f5` (shadowed-route fix), plus docs. Suites green: **backend 776 passed / 15 skipped**, **frontend 86 passed**. A local dress rehearsal was run to the human gate (below).

---

## 🚩 GATING FLAG — Section B: non-v1 surface reachability (BLOCKING, verify from the PRODUCTION build)

**Do NOT trust the `VITE_PREVIEW_SURFACES` default.** A commit **`dfb4b56` ("always show Vendors, Partner, Bulk in nav — remove PREVIEW_SURFACES gate")** de-gated preview surfaces for a demo. The flag was later re-instated (default off) for the **nav**, but **routes stay registered and URL-reachable** by design (comment in `App.tsx`: "reachable by URL for internal QA"). So nav-hiding is **not** an access control — the launch audit must verify the **route role-guards** from the built artifact.

**Current route-guard state (`web/src/App.tsx`, snapshot 2026-07-28 — informational; the audit is the source of truth):**

| Route | Current guard | Customer reachable by URL? | Intended? |
|---|---|---|---|
| `/quarterly` | **none** | yes (public) | ✅ F21 public quarterly report — verify it serves only approved+suppressed data |
| `/trust` | **none** | yes (public) | ✅ F15 public Trust Center — verify no security jargon / private data |
| `/crosswalk` | **none** | **yes** | ⚠️ F13 (M-25 mock) — **non-v1, customer-reachable → FLAG** |
| `/vendors` | `customer,sme,admin` | **yes** | ⚠️ F16 (M-28 mock) — **non-v1, customer-reachable → FLAG** |
| `/rewrite` | `customer,sme,admin` | yes | ✅ F18 real customer feature (shipped) |
| `/partner` | `partner_admin,admin` | no | ✅ blocked for customer |
| `/bulk` | `admin` | no | ✅ blocked for customer |

**Section-B audit requirement (blocking pre-launch):** from the **production build** (not dev), authenticated as a **customer** role, confirm every **non-v1** surface is unreachable (HTTP/route-level, not just hidden from nav). At minimum resolve the two ⚠️ flags above (`/crosswalk`, `/vendors`) — either role-gate the routes for prod or confirm they are intended v1. Public-by-design surfaces (`/quarterly`, `/trust`) must be confirmed to expose only approved/anonymized data. **Treat this table as a lead, not a guarantee** — the built artifact's behavior is authoritative.

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

## Local rehearsal — 2026-07-27 (labeled **rehearsal**, stopped at the gate)

Ran the Workstream-E dress rehearsal against a **local** hardened stack (gate mode **STRICT**, Ollama up). **Notice:** 1‑800‑Flowers (`https://www.1800flowers.com/About-Us-Privacy-Policy`) — a real retailer in `retail-2026Q3-v2`, direct/current privacy URL, substantive notice. Submitted through real URL intake as `organization_name="1-800-Flowers (rehearsal)"`. **Nothing was approved or frozen.**

**Rehearsal artifacts (live DB — clean up when done):** assessment `91a04e55-b825-46b9-924b-3ca44ff4fe5b`, org `066745ed-3a22-48bb-94e4-e3f002787bdb`, snapshot `46c49843…`. Plus a bogus `assessment_review` row `assessment_id="gate-mode"` left by the pre-fix shadowed-route smoke test — safe to delete.

### Pipeline stops — all verified ✅
| Stop | Result |
|---|---|
| Verified-source badge (M-02) | `ssrf_protected: true` |
| Decomposition | 186 sections / 176 clauses |
| Classification | **176 LLM-classified, 0 keyword fallback** (Ollama) |
| Cohort assignment (live n, M-12) | `cohort_size: 90` (minor relaxation; dynamically built) |
| Scores + VCI | overall **70.99**, VCI **high**, percentile 100 |
| Report | 12 sections (admin view) |
| **Gate (STRICT)** | owning customer → **403** "pending expert review" |
| **Cross-tenant isolation** | other-org customer → **403** "Not permitted" (Stage-3 fix, live) |
| approve_and_freeze | **untouched** — no `/approve`, status `draft` |
| SME workbench (code-verified) | three panes (source+de-id / finding+Confirm·Edit·Dismiss / Advisor+Codex); **de-id lock** disables Confirm while PII unresolved |
| PDF export | 200, valid, **byte-identical on double pull** |
| Monitoring | trend → `baseline_established` (single assessment → honest, no fake trend); alerts → `no_alerts` |
| Guardrail | verdict language → `GuardrailError` |

> Under STRICT/expert_review the customer is **blocked entirely (403)** — stronger than a watermarked draft (the gold DRAFT watermark is the *instant_draft* behavior). The report is not client-deliverable.

### Issues / observations found (for the pilot)
1. **Handoff:** the `assessment_review` row is created **lazily** (on first open), not at intake — a fresh assessment isn't in the SME `/review/queue` until opened by id. Under STRICT this can orphan an assessment (customer blocked + not queued). *Recommend intake enqueue, or derive the queue from unapproved snapshots.*
2. **Advisor prose absent in the draft** — correct by design (the SME **authors** the Advisor Note in the workbench; M-05 shows honest absence until then). Note for the SME: advisor notes must be written before delivery.
3. **Low finding yield:** 1 finding (`AI-004`, high) for a 176-clause notice + percentile 100 — SME should sanity-check whether more domains should flag.
4. **Over-segmentation:** 186 sections for 176 clauses — the decomposer created many tiny/nav sections from the live page. Data-quality note.
5. **Cohort is dynamically built (n=90), not the retail-25 demo cohort** — because the rehearsal org is new (no retail profile). The n is honest/live, just not the demo cohort.

**DEMO_RUNBOOK re-walk:** steps hold against this run (health, intake, scores, report, PDF, SME flow, monitoring, guardrail). The doc was already drift-fixed (STRICT default, live cohort n, monitoring step). Real URL intake yields large section/clause counts vs the tiny sample-text path — expected.

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
3. [ ] Build/push image → `az containerapp update`; run migrations **0001–0039** against the prod DB (via `scripts/db/apply_and_record.py`); confirm `/health` + `/docs`.
4. [ ] Deploy web to Cloudflare pointing at the prod API; smoke-test login → intake → report → monitoring → admin **logged in**.
5. [ ] Confirm prod `platform_setting` has **no** `gate_mode` row (or it's `strict`) so the safe default applies.
6. [ ] **Wire `logo_url` to object storage (Supabase storage bucket)** — **required before any partner demo.** F20 branding persists the `logo_hash` (the freeze anchor) but not the logo bytes; `PUT /partner/branding` must upload the validated image to a Supabase storage bucket and set `partner.logo_url` to its public URL. Until then, branded PDFs render the partner **name + brand-color band only** (no logo image). Touchpoints: `app/routers/partner.py::set_branding` (upload step) + `app/services/report/renderer.py::_branding_band` (already reads `logo_url`).

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
