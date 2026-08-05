# DEPLOYMENT — STATUS: 🟢 BACKEND LIVE · ⛔ FRONTEND PENDING

**Date:** 2026-08-05 (backend deployed 2026-08-06)
**Prompt:** PROMPT 7 — Backend + Frontend to Production.

> ## 2026-08-06 — BACKEND DEPLOYED (owner-directed; credential rotation risk accepted)
> Tag **`v1.0.0-pilot.1`** (commit `cfe238c`) is live on the Azure VM.
> Transport was git-bundle → scp → clone on VM (no VM GitHub credential).
>
> **Verified (real output):**
> - external TLS `GET /health` → **200** `{"status":"healthy","db":"ok","model_backend":"hosted","model_status":"ok","ollama":"ok"}`
> - `GET /docs` → **404** (not exposed in prod)
> - migration head → **`0047_assessment_id_uuid_check.sql`**
> - port self-scan → 80/443 open; **8000, 5432, 11434 closed**
> - running image `visentix-api:v1.0.0-pilot.1` (**CPU-torch, 2.94GB**), container healthy
>
> **Host-prep done during deploy** (gaps found live): installed `python3-psycopg` +
> `python3-dotenv` on the VM host (deploy.sh step 3); switched the image to **CPU-only
> torch** (Dockerfile) because the 29GB VM couldn't build the ~9.5GB CUDA image — this
> VM has no GPU (inference is on RunPod), so CUDA torch was pure waste.
>
> **Known issues / follow-ups:**
> - `deploy.sh` step 5 died on its OWN bug — `docker compose ps` is called without
>   `--env-file`, so `${DOMAIN}` fails to interpolate. Steps 1–4 (migrations, build,
>   recreate) completed and the container is healthy; step 5–7 self-verification was
>   done manually (above). Fix deploy.sh to pass `--env-file` in `wait_healthy`.
> - Old image `visentix-api:local` (9.48GB) kept as the rollback fallback.
> - **⚠️ Credentials NOT rotated (SEC-007)** — owner explicitly accepted the risk for
>   the pilot. Seeded-account/service-role/JWT/DB secrets remain in git history and are
>   now pointed at production. Rotate before broadening access. (See risk write-up in
>   the session record.)
> - **`.env` deployed "lite":** the 3 secret keys (`PARTNER_KEY_PEPPER`,
>   `RCLONE_CONFIG_BASE64`, `SMTP_PASS`) are EMPTY → partner-key auth fails closed
>   (masked surface, fine), and **backups + SMTP alerts are non-functional**.
> - **Off-VM backup still BLOCKED** (`pg_dump`/`rclone` + keys) — deploy ran without a
>   fresh backup, per accepted risk.
>
> **Frontend:** NOT deployed — blocked on Cloudflare auth (see below).
>
> ---
> *(Original preflight record retained below for history.)*

> **2026-08-05 update (PROMPT 7A preflight-unblock):** several blockers cleared —
> see [PREFLIGHT-UNBLOCK-DONE.md](PREFLIGHT-UNBLOCK-DONE.md). Migration ledger
> **confirmed accurate** (50 rows, 0043–0047 all State A + checksums match — the
> "diverged ledger" premise was stale); `python`→`python3` fixed in `deploy.sh`;
> a `--record-only` ledger path + `--print-head` added; **SEC-009 partner-key
> pepper now fails closed in production** (was silently degrading to unsalted
> sha256); attributable work committed in 2 units (Phase 6 + preflight), the
> unvetted multi-select-intake WIP intentionally excluded. **Still NOT DEPLOYED.**
> Remaining owner-BLOCKED gates: credential rotation, VM `.env` (18 keys), off-VM
> backup (pg_dump/rclone + keys), and cutting `v1.0.0-pilot`.

> **2026-08-05 test-count note (PROMPT 7B — [TEST-RECONCILIATION.md](TEST-RECONCILIATION.md)):**
> the full suite is `1045 passed · 34 failed · 15 skipped`. The 34 are an
> **environment change, not a regression and not an "unchanged pre-existing env
> class"**: the live DB advanced after the Phase-4 gate — 0047's UUID CHECK now
> rejects tests' non-UUID `assessment_id` fixtures (28), `count=exact` on the
> ~691k-row `disclosure_clause` 500s (3), and 3 are live data-state assertions.
> An A/B diff against the excluded WIP is identical (regression ruled out). The
> committed code is clean; the baseline needs re-stating against this DB.
**Outcome:** Deployment was **not executed.** Preflight (STAGE 0) found multiple
hard-stop gates unmet. Per Hard Rule 4 ("if a stage fails, stop and report — do
not fix forward into production") and Hard Rule 5 ("nothing is deployed until
verified by command output"), no tag was cut, no migration applied, no container
built, no frontend published, no credential rotated. This file records the
**verified** preflight state and the exact steps to resume.

**No secret value was printed at any point** — every check used key **names**
(`grep -oE '^[A-Z_]+='`) and counts only. Confirmed.

---

## What WAS done (read-only, non-destructive)

- Ran the local STAGE 0 preflight gates.
- Reached the Azure VM over the existing `~/.ssh/visentix_deploy` key and took a
  **read-only** inventory of every `deploy/azure/deploy.sh` precondition.
- Confirmed the current production stack is **live and healthy** and left it
  untouched: `azure-api-1` (Up, healthy) + `azure-caddy-1` (Up) — pre-remediation
  image.

## What was NOT done (and why)

| Action | Not done — reason |
|---|---|
| `git tag v1.0.0-pilot` | Working tree dirty (17 files); owner is handling commits/tag. |
| `git commit` / `git stash` | Owner owns commits; STAGE 0.1 forbids stashing/forcing past the gate. |
| `deploy.sh` (backend) | Preconditions unmet (below); would die at step 1/2/3. |
| Frontend build + `release.sh` + `wrangler deploy` | Gated behind a verified backend. |
| Credential rotation (SEC-007) | Still pending; owner action. Not performed. |
| Migrations | `0043–0047` reportedly already applied via Supabase SQL editor in a prior session; deploy.sh’s `apply_and_record.py` path was **not** run (it needs host `python`). |
| Any change to the VM (`.env`, `python` symlink, GitHub creds) | Owner elected to handle host gaps; no VM state modified. |

---

## Preflight matrix (real results)

### Local (this Mac)
| Gate | Result |
|---|---|
| 0.1 Clean tree | ❌ **17 uncommitted files** on `remediation-2026-08-04` (Phase 6 work + earlier WIP). |
| 0.1 Release tag | ❌ Only `v1` exists (predates Phase 6). No `v1.0.0-pilot`. HEAD = `ef3f992`. |
| 0.2 CI green on tag | ❌ N/A until a release commit is tagged + pushed. |
| 0.3 `.env` (local) | ⚠️ Local dev `.env` is a subset; prod `.env` lives on the VM (checked there). |

### Azure VM (`azureuser@4.231.113.178`, host `visentix`)
| Precondition | Result | Blocks |
|---|---|---|
| VM reachable | ✅ key works; `HOST=visentix`, kernel `6.17.0-1020-azure` | — |
| Prod stack | ✅ `azure-api-1` healthy (2d), `azure-caddy-1` (7d) — untouched | — |
| `~/visentix` is a git checkout | ❌ rsync’d copy, `is_git=NO` | deploy.sh needs a real checkout |
| VM → GitHub auth | ❌ no `~/.ssh` key, no credential helper, github.com not a known_host | **clone** |
| Host `python` (deploy.sh steps 3 & 7 call `python`) | ❌ missing; only `python3` 3.12.3, no venv | **deploy step 3** |
| Prod `.env` present | ✅ `~/visentix/.env` | — |
| Prod `.env` completeness vs remediation `.env.example` | ❌ **18 keys missing** (list below) | **deploy step 2** |
| `.env` criticals present + non-empty | ✅ APP_ENV, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_JWT_SECRET, DATABASE_URL, DOMAIN, HOSTED_QWEN_BASE_URL | — |
| `db/schema_dumps/` writable + `backup.sh` present | ✅ both present | — |

**18 `.env` keys missing on the VM** (must be added before deploy.sh step 2 passes):
`BACKUP_BUCKET`, `BACKUP_PREFIX`, `BACKUP_RCLONE_REMOTE`, `BACKUP_RETAIN_DAYS`,
`ENABLE_LIVE_F004`, `GIT_TAG`, `INGESTION_POLITENESS_SECONDS`, `OLLAMA_IMAGE`,
`PARTNER_KEY_PEPPER`*, `RCLONE_CONFIG_BASE64`*, `RENDERER`, `SCORING_MODEL_VERSION`,
`SMTP_FROM`, `SMTP_HOST`, `SMTP_PASS`*, `SMTP_PORT`, `SMTP_USER`, `SOURCE_CORPUS_VERSION`.
`*` = secret value the owner must supply (cannot be invented).

**Resolved question:** `HOSTED_QWEN_API_KEY` empty is **fine** — `deploy.sh`'s
critical list requires only `HOSTED_QWEN_BASE_URL`. Empty API key is correct for
the local/hosted Ollama topology.

---

## Blockers → owner actions (ordered)

1. **Commit + tag the release.** Resolve the 17-file working tree (Phase 6 is
   complete + tested; earlier WIP — `assessments.py`, `intake_options.py`,
   `Intake.tsx`, `MultiSelectDropdown.tsx`, `org_profile_weights.json`,
   `build_review_pdf.py` — is unrelated and must be triaged by owner), then
   `git tag -a v1.0.0-pilot`, and push.
2. **Rotate credentials (SEC-007 / CRED-001)** — DB password, service-role key,
   JWT secret, Tailscale key, seeded `admin@/sme@/customer@` accounts. Confirm no
   null-`organization_id` customer remains (SEC-001 interaction).
3. **Add the 18 `.env` keys on the VM** (owner elected to handle). Secrets
   marked `*` must be real values.
4. **Provide `python` on the VM PATH** (owner elected to handle) — e.g.
   `apt install python-is-python3` or a venv on PATH — so `apply_and_record.py`
   runs in deploy.sh step 3.

## Agreed resume plan (once #1–#4 are done)

- **VM checkout via git bundle** (owner’s choice — no long-lived GitHub credential
  on the box): once the tag exists, `git bundle create` locally → `scp` over the
  deploy key → `git clone` from the bundle into a fresh checkout dir on the VM →
  drop the completed prod `.env` at its root.
- **Backend:** run `./deploy/azure/deploy.sh v1.0.0-pilot` on the VM — let its 7
  steps run; do not bypass. Then run the STAGE-1 post-deploy verifications
  (health/docs, `schema_migrations` head = 0047, SEC-001 / GRD-002 / QA-011 /
  SEC-008 checks).
- **Frontend:** `npm ci && npm run build` (prod `VITE_API_BASE_URL`), then
  `../scripts/release.sh` **before** `npm run deploy` — treat a release-gate
  failure as a hard stop.
- **STAGE 3–4:** four cross-cutting journeys against the deployed stack, install
  `backup.cron`, run `backup.sh` + `restore_drill.sh` (record RTO), document the
  tag-based rollback + the forward-only nature of migrations `0043–0047`.

## Rollback note (pre-recorded)

Deploy is tag-based: rollback = `./deploy/azure/deploy.sh <previous-tag>`.
**Migrations `0043–0047` are forward-only** — rolling the app back does **not**
roll the schema back. Additive columns + `NOT VALID` constraints are expected to
be tolerated by the prior app version; **verify before relying on it.**

---

**Bottom line:** the deploy tooling is sound and the VM is reachable, but four
owner-owned preconditions (commit+tag, credential rotation, `.env` keys, host
`python`) must land first. This document will be updated to a true "DONE" record
— with real health/smoke output, migration head, the four journey results, and
the restore-drill RTO — only after the deploy actually runs and is verified.
