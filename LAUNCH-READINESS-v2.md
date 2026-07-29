# Launch Readiness v2

> ⚠️ **SUPERSEDED TOPOLOGY BELOW.** The 2026-07-28 section (single RunPod host
> for API+Ollama+scheduler) is superseded by the **three-host** deploy executed
> 2026-07-29 (Azure VM = API+scheduler+Caddy; RunPod pod = Ollama-only, private;
> Cloudflare = frontend). The current state is the section immediately below;
> the older section is kept for history.

---

## 2026-07-29 — THREE-HOST DEPLOY (current, live)

_owner + Claude (engineer). Living doc; the owner tags `v1.0.0` — engineering does NOT tag._

### Topology (live)

| Host | Role | URL / addr | Status |
|---|---|---|---|
| Cloudflare | Frontend (Worker + static assets, SPA) | `https://visentix-v2-mvp.zssaincoding.workers.dev` | **live, MASKED v1 build** (bundle `index-Cg1OWTAY.js`; targets prod API) |
| Azure VM `visentix` (Standard_B2ls_v2, West Europe) | FastAPI + APScheduler + Caddy | `https://visentix-api.westeurope.cloudapp.azure.com` (IP `4.231.113.178`) | **live, HTTPS (Let's Encrypt)** |
| RunPod pod `1zyg93j5rzy4p4` (RTX 4000 Ada 20GB) | Ollama `qwen3:8b` + embeddings, PRIVATE | tailnet `100.69.10.127:11434` | live (stock Ollama + Tailscale + watchdog) |
| Supabase | Postgres (managed) | `db.jhzkyfitrdxmzyyvqfak.supabase.co` | live, RLS on all 56 public tables |

Private wire: Azure VM (tailnet `100.122.134.63`) ↔ pod (`100.69.10.127`) over Tailscale (userspace). Ollama/Postgres never publicly exposed.

### Security posture (verified)
- **Azure public ports:** 22, 80, 443 only; API `:8000` **closed** publicly (scanned). ufw active; SSH key-only.
- **Pod public ports:** SSH only; Ollama `:11434` NOT publicly reachable (scan closed; http→000).
- **RLS:** 56/56 public tables on; `tests/test_rls_enabled.py` green; migration 0042 at head.
- **TLS:** Caddy/Let's Encrypt, valid to 2026-10-27; HSTS + nosniff + frame-deny + strict CSP.

### v1 surface masking (release system) — VERIFIED
- Build-level masking in `web/src/App.tsx` (lazy import + `import.meta.env.VITE_SURFACE_*` DCE). Secure-by-default: unflagged build = masked v1.
- **Masked & ABSENT from bundle (grep = 0):** bulk, partner, rewrite, vendors, trust, crosswalk. Single chunk; no masked chunks emitted.
- **LIVE artifact audit (Section-B, 2026-07-29, `main` @ PR #14):** deployed bundle `index-Cg1OWTAY.js` — all masked identifiers **0** (Bulk Analysis, Partner Workspace, Vendor Due Diligence, Trust Center, Framework Crosswalk, Trust Language Studio + route paths `/bulk /partner /vendors /crosswalk /trust /rewrite`); v1 surfaces present; frontend targets the prod Azure API.
- **Endpoint audit (customer role, live backend):** `/bulk/jobs` → 403, `/partner/workspaces` → 403. Masked = unreachable by route AND endpoint on the LIVE artifact.
- **v1 live surfaces:** intake (3 modes), reports, monitor (baseline), methodology, codex, `/quarterly` (public, real approved data), `/privacy`, `/terms`; admin reaches admin.
- Encoded: `releases/v1.yaml`..`v5.yaml`; driven by `scripts/release.sh`.

### Model / classifier
- `qwen3:8b` (Q4_K_M, 8.2B, ctx 40960), digest `500a1f067a9f…`.
- `app/services/llm.py` hosted == local byte-for-byte (native `/api/chat`, `think:false`, `num_predict:500`); classifier_version unchanged.
- Azure→pod classify latency (warm 5-clause): **~1.6 s/clause**, all correct; cold ~3.6 s (one-time load).
- `gate_mode=expert_review` (STRICT); `approve_and_freeze` + snapshot-approval paths UNTOUCHED.

### Pod durability (honest)
- Stock Ollama = stable (no crash loop). Tailscale via `podsetup.sh` + `tailscaled` watchdog (auto-heals crashes). Site stays up if pod drops (health decoupled; classify fails-fast, spec 1D). A full pod restart still drops Tailscale → ~1 min reconnect via RunPod API. Bulletproof supervisor start-command deferred (crash-looped — decision-log 2026-07-29).

### Prod rehearsal + eat-own-cooking (2026-07-29, live stack)

**Eat-own-cooking** — our own `deploy/legal/visentix-privacy-notice.txt` through the live pipeline (rehearsal-labeled, admin): 11/11 clauses LLM-classified (0 keyword fallback), scored in 11.8 s. Domain scores called out per the standing requirement:
- **AI-transparency = 15.36 — WEAK** (+ a HIGH-severity `ai_automated_decisions` finding). For an AI-driven product this is a genuine gap.
- **Retention** = MEDIUM-severity finding (intensity 2.5). Not strong.
- Per instruction: notice UNTOUCHED — owner decides whether the notice or the expectation changes.

**Prod rehearsal** (public retail-cohort stand-in, labeled `rehearsal`):
- ✅ **upload mode** → scored, 9/9 LLM-classified, `intake_method: upload`.
- ✅ **cross-org 403** — a customer from another org gets 403 on the rehearsal report (tenant isolation holds).
- ✅ **scheduler machinery** — manual `POST /admin/jobs/refresh_benchmarks/run` → `job_run` **succeeded** (recorded); scheduled jobs stay disabled.
- ✅ **gate STRICT respected** — everything stopped at `status: scored`; nothing approved or frozen.
- ⚠️ **PDF NOT byte-identical** — two pulls of the same (snapshot-backed) report differ by ~1 byte + sha. Cause: WeasyPrint stamps a fresh `/CreationDate` + `/ID` per render. Content (`content_hash`) is stable; file bytes are not. **FIX:** pin PDF metadata in `app/services/report/renderer.py` for reproducible delivery. Blocks the "byte-identity → deliver" guarantee until closed.
- ⚠️ **503 under PDF load** — WeasyPrint rendering on the 4 GB VM spikes resources → `/health` slows → Caddy briefly 503s concurrent requests. Fine for low-traffic pilot; watch under load or bump the VM.

**Config fixes applied to the live DB during rehearsal (v1 compliance):**
- `gate_mode` was **`instant_draft`** (a MUST-NOT) → set to **`strict`**.
- All 3 scheduler jobs were **enabled** → **disabled**.
- (Minor: `alerts_suppressed` flag = 0, but the alert source job — monitor_notices — is disabled, so no alerts fire.)
- These are `platform_setting` rows; `release.sh` applies them from `releases/v1.yaml` on a tagged release.

### OPEN before v1.0.0 tag
- [x] **Deploy masked v1 frontend** — DONE (PR #14 → `main` → CF rebuild; live artifact audited clean, above).
- [ ] **PDF byte-identity** — pin WeasyPrint `/CreationDate` + `/ID` (renderer) OR accept content-hash identity (owner call).
- [ ] **AI-transparency / retention** on our own notice — owner decides (notice vs expectation).
- [ ] **Rotate Supabase keys** (service-role + anon + JWT) — owner, Supabase dashboard.
- [ ] **Backups** — nightly `pg_dump` → object storage + restore drill (RPO 24h/RTO). Needs S3/Azure-Blob creds.
- [ ] **Publish `/privacy` + `/terms`** only after owner confirms mailboxes exist.
- [ ] **PROD REHEARSAL** (STRICT gate; pilot notice; pipeline stops; PDF double-pull byte-identity; cross-org 403; scheduler job_runs).
- [ ] **Owner approves `v1.0.0` tag** — engineering does NOT tag.

### Rotation table
| Secret | Rotated? | Owner action |
|---|---|---|
| Supabase service-role / anon / JWT | ❌ pending | Supabase → Settings → API |
| Tailscale auth key | reusable 90d | rotate at expiry |
| RunPod API key | in `.env` (gitignored) | rotate post-launch |

---

# (SUPERSEDED) Launch Readiness v2 — RunPod deploy prep + launch checklist (2026-07-28)

**By:** deploying engineer. Continues [`LAUNCH-READINESS.md`](LAUNCH-READINESS.md).
**Topology:** RunPod GPU VM hosts **API + Ollama (GPU) + scheduler**; **Cloudflare
Pages** hosts web; **Supabase** stays the managed DB. **I prepared/verified; I
deployed nothing client-facing and approved nothing.**

> This document has two halves: **(A) done + verified here** (artifacts, scans,
> local suites, frontend build) and **(B) owner-gated** (the actual deploy, live
> key rotation, founder wording approval, the pilot notice, the prod rehearsal,
> and the release tag). Every `⟨fill at deploy⟩` marker is a slot the owner/
> engineer completes on the VM.

---

## ⚠️ Pre-flight flag — concurrent-session working-tree changes (resolved: owned elsewhere)

The tree was **clean** at session start, but two app files were modified at
**21:08:47** (identical second → one atomic patch) and were **NOT authored by
this task**:

- `app/routers/assessments.py` — wraps `extract_from_url` in try/except → **422**
  with a helpful message on fetch failure.
- `app/services/intake/discover.py` — parallelizes known-path probing
  (`asyncio.as_completed`, first-hit-wins) + adds an **8s per-probe timeout**.

**Origin (forensics):** the concurrent Claude session `f6fbe370…` — which
references these two files 125× and was actively editing `discover.py` — is the
author. **Owner confirmed it is a live session** and will handle these edits
there. They are therefore **intentionally excluded from the deploy-prep PR**
(left untouched in the working tree; diff backed up to
`scratchpad/orphan-intake-edits-f6fbe370.patch`). Nothing unowned enters
`v1.0-pilot`.

> Note the semantic change in `discover.py`: `as_completed` returns the
> **fastest-responding** path, not the highest-priority one — the owning session
> should add a test for path-preference before it ships. `deploy_runpod.sh` still
> refuses a dirty tree, so a clean-tree checkout at the release tag is required
> for deploy regardless.

---

# A. Done + verified in this session

## A1. Deploy artifacts produced (`deploy/`)

| File | Purpose |
|---|---|
| `deploy/docker-compose.prod.yml` | api (built from Dockerfile) + ollama (GPU reservation) + caddy (443 only). Healthchecks, `restart: unless-stopped`, json-file logging 50m×5. |
| `deploy/Caddyfile` | 443-only public edge; automatic TLS for `${DOMAIN}`; HSTS + nosniff + frame-DENY + CSP; reverse_proxy → api:8000. |
| `deploy/entrypoint-ollama.sh` | Starts ollama, pulls the **pinned** `qwen3:8b` at first boot (idempotent). |
| `deploy/deploy_runpod.sh` | Idempotent: install docker+NVIDIA toolkit → checkout tag (refuses dirty tree) → **.env-completeness gate vs .env.example** → compose up → migrations → healthcheck wait → **port-scan** → smoke summary. |
| `deploy/backup.sh` + `deploy/backup.cron` | Nightly `pg_dump` (schema+data, public) → gzip → S3-compatible via **rclone**; retain **14d**. Cron 03:15 UTC (RPO ≤ 24h) + weekly drill. |
| `deploy/restore_drill.sh` | Restores the latest backup into schema `restore_test`, runs **3 sanity counts** vs live, prints measured wall-clock (→ RTO), drops the throwaway schema. |
| `deploy/FIREWALL.md` | Only 443/80 public; 8000/11434/5432 never exposed; SSH key-only; nmap verification step. |
| `deploy/legal/visentix-privacy-notice.txt` | Plain-text privacy notice for the "eat our own cooking" pipeline run. |

**Model / embedding reconciliation (correction to the brief):** the embedding
model chosen in Prompt 3 is `sentence-transformers/all-MiniLM-L6-v2` (decision-log
2026-07-28), which runs **in-process in the api container via sentence-
transformers — it is NOT an Ollama model.** So the Ollama entrypoint pulls the
**LLM only** (`qwen3:8b`); the embedding weights are cached in the `hf-cache`
volume on first API boot. Pulling the embedding model "via Ollama" (as the brief
phrased it) does not apply to this stack.

- Compose YAML validated (`yaml.safe_load` OK). All four shell scripts pass
  `bash -n`. `docker compose config` deferred to the VM (no Docker locally).

## A2. Env var enumeration → `.env.example`

Rewrote `.env.example` so **every** field in `app/config.py::Settings` is present
(added the previously-missing `RENDERER`, `SCHEDULER_ENABLED`, `SMTP_*`,
`PUBLIC_BASE_URL`, `INGESTION_POLITENESS_SECONDS`, `DATABASE_POOLER_URL`) plus a
`[deploy-only]` block (`DOMAIN`, `ACME_EMAIL`, `GIT_TAG`, `OLLAMA_IMAGE`, and the
rclone/backup vars). `deploy_runpod.sh` refuses to run if any key here is absent
from `.env`, and requires a non-empty critical subset (`APP_ENV`, `SUPABASE_URL`,
`SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWT_SECRET`, `DATABASE_URL`, `DOMAIN`).

## A3. Git-history credential scan (security gate 1)

Scanned all **143 commits** (`git log --all -p`) for JWTs, `sk-` keys, private
keys, and `SERVICE_ROLE`/`JWT_SECRET` assignments.

**Result: no live secret was ever committed.** All `eyJhbGci…` hits are
placeholders in `.env.example`/docs; CI uses dummy values. **One real finding**
(already known): `local_users.json` — added in `a54c598`, removed in `015ff8e` —
contained salted **PBKDF2 hashes** for 3 demo accounts (`admin@`, `sme@`,
`customer@visentix.com`). Salted, not plaintext, and the prod image no longer
ships the file; still, the demo passwords must be treated as burned.

### Credential rotation table (security gate 1 → owner action)

| Credential | In git history? | Action | Rotated (date) |
|---|---|---|---|
| Demo account passwords (admin/sme/customer) | **yes** (`a54c598`, salted hashes) | Do not reuse; provision prod users with fresh passwords via DB (RLS-AUDIT §5 C1b). | ⟨owner⟩ |
| `SUPABASE_SERVICE_ROLE_KEY` | no | **🔴 ROTATE NOW** — active attack surface during the RLS exposure window (incident 2026-07-29). Update `.env`; confirm old key dead. | ⟨owner — now⟩ |
| `SUPABASE_ANON_KEY` | no (placeholder only) | **🔴 ROTATE NOW** — this key could read 38 exposed tables (organization, notice_section, …) during the window before 0042. Rotate; update the web build env. | ⟨owner — now⟩ |
| `SUPABASE_JWT_SECRET` | no | Rotate; all existing tokens invalidate (expected). | ⟨owner⟩ |
| DB password (`DATABASE_URL`) | no | Rotate in Supabase; update `.env` + `DATABASE_POOLER_URL`. | ⟨owner⟩ |
| SMTP creds | no | Set fresh if alerts enabled; else leave blank (suppressed). | ⟨owner⟩ |
| rclone/S3 backup creds | no | Provision a scoped key; store as `RCLONE_CONFIG_BASE64` in `.env`. | ⟨owner⟩ |

> I hold none of these and rotate nothing live. Rotation + "confirm old key dead"
> is an owner step; fill the dates above as each is done.

## A4. Prod-config sanity suite (security gate 2, local)

Ran the cross-tenant + auth suites under a **production config profile**
(`APP_ENV=production`, CORS locked to `https://app.example.com`) against live
Supabase:

```
APP_ENV=production CORS_ALLOWED_ORIGINS=https://app.example.com \
  pytest tests/test_auth.py tests/test_org_isolation.py
→ 19 passed, 1 skipped (13.2s)
```

Covered: no/invalid/expired-token → 401; role gates (customer/sme ✗ admin); RLS
anon read blocked on `risk_finding`; service-key bypass server-side only; **login
rate-limit fires**; and all cross-tenant reads (report, PDF, explain,
list-assessments, dashboard-stats) → **403/empty**. (1 skip =
`test_admin_can_access_all_routes`, self-skips.)

> **Still owner-gated (needs the live stack):** login rate-limit + token-expiry
> verified *live post-deploy* with a **curl transcript** pasted here. Template:
>
> ```
> ⟨fill at deploy⟩  # 6× bad login → expect 429 after the threshold
> for i in $(seq 1 6); do curl -s -o /dev/null -w "%{http_code}\n" \
>   -X POST https://DOMAIN/auth/login -d '{"email":"x@x","password":"bad"}' \
>   -H 'content-type: application/json'; done
> ⟨fill at deploy⟩  # expired token → 401 without leaking verification detail
> ```

## A5. Frontend — Cloudflare Pages build

- Added public routes **`/privacy`** and **`/terms`** (`web/src/pages/legal/`),
  a shared `LegalPage` renderer, and a global **`Footer`** (Privacy · Terms ·
  Methodology) shown on every non-login route.
- **Fixed pre-existing build breakers** that would have failed the Cloudflare
  `tsc -b && vite build` (all confirmed present with my changes stashed —
  independent of this task): `UserRole` union missing `partner_admin`
  (`AuthProvider.tsx`); unused `useEffect` (`NoticeRewrite.tsx`); unused
  `resultByAssessment` (`BulkAnalysis.tsx`).
- **Hardened the API-base fallback** in all 7 call sites (`lib/api.ts`,
  `AuthProvider.tsx`, `ReportPage`, `NewAssessment`, `admin/Console`,
  `PartnerPortal`, `QuarterlyReport`): the `localhost` default is now **dev-only**
  (`import.meta.env.DEV ? … : ""`), so a prod build never carries a localhost API
  target even if `VITE_API_BASE_URL` is unset. Updated the `api.test.ts` env-var
  guard to permit Vite built-ins (`DEV`/`PROD`/`MODE`/`SSR`/`BASE_URL`).
- **Build verified both ways.** With `VITE_API_BASE_URL=https://app.example.com`
  the prod base is baked in; `grep dist/assets/*.js` for `localhost`/`127.0.0.1`
  returns **only** react-router-dom's internal `http://localhost` dummy origin
  (used by `new URL()` when `location` is absent — never a network target).
  **Zero app-level localhost.** Frontend tests: **75 passed**.

> Cloudflare Pages must set `VITE_API_BASE_URL=https://DOMAIN` (and
> `VITE_PREVIEW_SURFACES` unset/false) as **build env vars**. Deploy:
> `cd web && VITE_API_BASE_URL=https://DOMAIN npm run build && npm run deploy`.

## A6. Privacy notice + terms (drafts)

Drafted both in plain language (`/privacy`, `/terms`): data collected (account /
submitted notices+files / usage logs), retention, subprocessors
(**Supabase / RunPod / Cloudflare / SMTP provider**), **no sale**, contact,
effective date. Effective date placeholder **28 July 2026**.

- ✅ **Founder approved wording (2026-07-28)** with 4 required edits — all applied
  to `Privacy.tsx` + `deploy/legal/visentix-privacy-notice.txt` (PR #12 commit
  `ccd46cd`): honest training clause (we DO reuse de-id'd derived data / Rule 7),
  aggregated-benchmark disclosure (≥10 orgs), removed consent-by-inertia from the
  notice, AI-transparency sentence. Retention 90d/12mo logged as policy. Standing
  trigger recorded in `version-ladder.md` (hosted models reopen the clause first).
- ⟨owner action⟩ Confirm `privacy@`/`legal@visentix.ai` mailboxes exist before publish.
- ⟨owner/live⟩ **Eat our own cooking:** run `deploy/legal/visentix-privacy-
  notice.txt` through our **own** pipeline (rehearsal-labeled) and paste the
  per-domain scores into the PR. **Founder requirement: specifically call out the
  RETENTION and AI-TRANSPARENCY domain scores** in the PR. Needs the live stack.

---

# B. Owner-gated — the ordered launch finale

Fill each `⟨…⟩` as you go. Nothing below was done by me.

### B1. Deploy (from a CLEAN tree, at a tag)
1. Resolve the pre-flight flag above (commit or revert the two intake files).
2. Rotate credentials (table A3) → `.env` on the VM (never committed).
3. `sudo ./deploy/deploy_runpod.sh <git-tag>` → records:
   - public URL: `https://⟨DOMAIN⟩`
   - api image digest: `⟨fill⟩`  · ollama image digest: `⟨fill⟩`
   - model versions: qwen3:8b `⟨fill⟩` · embeddings all-MiniLM-L6-v2 (384-dim)
   - migrations applied: 0001–00⟨n⟩ recorded in `schema_migrations`
   - port scan: `⟨paste nmap: only 80,443 open⟩`
4. Confirm `platform_setting` has **no `gate_mode` row** (STRICT default holds).

### B2. Backups (evidence)
- First successful dump: `⟨filename + size + timestamp⟩`
- Restore drill: `⟨3 counts + measured wall-clock⟩` → **RPO 24h / RTO ≤ 2h**
  (RTO = measured drill time `⟨fill⟩`). **Do not skip the drill.**

### B3. Prod rehearsal (STRICT; stops at the human gate)
Verify `gate_mode=expert_review` **live**, then submit the pilot notice URL (or a
rehearsal-labeled stand-in) through **production** intake and record evidence:
- verified-source badge · decomposition · classification · cohort (live n) ·
  scores+VCI · findings in SME queue · **gate → 403** · cross-org **403** ·
  PDF byte-identical on double-pull · scheduler `job_runs` exist · alert email to
  a test inbox **iff** F-013 thresholds set (else suppressed rows present) ·
  `approve_and_freeze` **untouched**.
- Evidence (screenshots/curl): `⟨fill⟩`
- **MUST NOT** run `instant_draft` on prod; approve/freeze nothing.

### B4. The human finale (engineering never does this)
SME works queue → **approve** → snapshot **freeze** → deliver **PDF** →
**Success Metric #1**.

### B5. Release
- ⟨owner ok⟩ then: push branch, open PR (privacy scores in the body), and
  **tag `v1.0-pilot`** — only after your explicit go-ahead.

---

## Files changed this session
- New: `deploy/*` (8 files), `web/src/pages/legal/{LegalPage,Privacy,Terms}.tsx`,
  `web/src/components/Footer.tsx`, this doc.
- Modified: `.env.example`; `web/src/App.tsx` (+routes/footer);
  `web/src/{auth/AuthProvider,lib/api}.ts` + 5 pages (localhost-fallback harden);
  `web/src/test/api.test.ts`; `web/src/pages/{bulk/BulkAnalysis,rewrite/NoticeRewrite}.tsx` (build fixes).
- **Not mine** (pre-flight flag): `app/routers/assessments.py`,
  `app/services/intake/discover.py`.

**I did not push, deploy, rotate any live key, approve any wording, or tag.**
