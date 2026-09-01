# PREFLIGHT UNBLOCK — DONE (deploy still NOT executed)

**Date:** 2026-08-05
**Prompt:** PROMPT 7A — Ledger Reconciliation, Commit Hygiene & Deploy Readiness.
**Scope:** clear the STAGE-0 blockers so `07-DEPLOYMENT` can run later. **Nothing
was deployed.** No secret value was printed anywhere (names/counts only).

---

## 1 — Ledger reconciliation

### 1a — Diagnosis (read-only, live DB via IPv4 pooler)

**Headline: the premise was stale — the ledger is NOT diverged.** The prior
session already recorded 0043–0047 via `apply_and_record.py`'s record path. Live
`schema_migrations` has **50 rows** (= 20 historical + 30 applied-now, the full
expected manifest). Every 0043–0047 row is present with a checksum that **matches
the current file**, and every live object matches its migration file:

| Migration | Ledger row | Checksum vs file | Live schema evidence | Verdict |
|---|---|---|---|---|
| 0043_assessment_job | present | **match** | `assessment_job` table + `assessment_job_pkey`, `idx_assessment_job_assessment`, `idx_assessment_job_org_created`, `uq_assessment_job_idem`; RLS enabled | **State A** |
| 0044_org_industry_source | present | **match** | `organization.industry_source` column present | **State A** |
| 0045_org_notice_fks | present | **match** | all 4 FKs present, `convalidated=false` (NOT VALID), `pg_get_constraintdef` matches file | **State A** |
| 0046_reapply_notice_rls_policies | present | **match** | `privacy_notice_select` / `notice_section_select` / `disclosure_clause_select` present, RLS on, USING expressions match | **State A** |
| 0047_assessment_id_uuid_check | present | **match** | all 4 `*_assessment_id_is_uuid` CHECKs present, NOT VALID, defs match | **State A** |

**No State B (drift) and no State C (unapplied) among 0043–0047.** All five are
**State A — applied and matching**, and already recorded. **No reconciliation
write was required.**

### 1b — Record-only path (added as requested; not needed this time)

`apply_and_record.py` did **not** have a record-only path; I added
`--record-only FILENAME`. It:
- computes the checksum via the SAME `checksum()` the normal path uses,
- inserts one `schema_migrations` row (`ON CONFLICT (filename) DO NOTHING`),
- **executes NO DDL** (only the ledger INSERT),
- refuses unless a single explicit **tracked** filename is passed (no bulk, no
  unknown/untracked files — raises `ValueError`),
- refuses if `schema_migrations` doesn't exist yet,
- logs loudly that it recorded WITHOUT applying, and why.

Also added `--print-head` (deploy.sh step 7 calls it but the script lacked it — it
was silently degrading to "see step 3"); it now prints the latest recorded
migration. Demonstrated live: recording 0043 reported **"already recorded — no
change"** (idempotent no-op), and `--print-head` → `0047_assessment_id_uuid_check.sql`.

New/updated tests (green): `test_record_only_is_guarded_and_uses_file_checksum`
(dry-run guard + checksum), and the stale static `test_apply_now_order_and_step_a_first`
updated to include 0043–0047 (a sync to the correct manifest, **not** a loosening).
The live `test_schema_migrations_rows_match_file_checksums` passes (ledger accurate).

### 1c — Backup

Since **no ledger write was made** (all rows already present), the
"backup-before-write" safety step protects nothing here. The deploy-readiness
off-VM backup is **BLOCKED — EXTERNAL**: on the VM, `pg_dump` and `rclone` are
both missing, and `backup.sh`'s required keys (`BACKUP_RCLONE_REMOTE`,
`BACKUP_BUCKET`, `RCLONE_CONFIG_BASE64`) are absent. **No backup artifact exists.**
Owner steps: `apt-get install -y postgresql-client`; install `rclone`; add the 3
keys; run `./deploy/azure/backup.sh` and confirm the object lands off-VM.

---

## 2 — Commit hygiene (owner decisions: "I commit the 2 units" + "exclude WIP")

23 working-tree paths classified:

**Committed — Unit A (Phase 6 report design):** `report/assembly.py`,
`report/renderer.py`, `report/report.css`, `report/assets/*`,
`tests/test_report_design.py`, `PHASE6-REPORT-DESIGN-DONE.md`,
`docs/remediation/assets/phase6-sample-report.pdf`.

**Committed — Unit B (Prompt 7A preflight):** `scripts/db/apply_and_record.py`,
`scripts/db/dump_column_types.py`, `deploy/azure/deploy.sh`,
`app/services/partner.py`, `tests/test_f02_ingestion_foundation.py`,
`tests/test_f20_partner.py` (SEC-009 tests + a Phase-6 cover-routing test — mixed;
kept with `partner.py`), `DEPLOY-DONE.md`, `PREFLIGHT-UNBLOCK-DONE.md`,
`logs/decision-log.md`.

**EXCLUDED from the release (left uncommitted, flagged) — unattributable
"multi-select intake" WIP:** `app/routers/assessments.py`,
`app/services/intake_options.py`, `config/org_profile_weights.json`,
`web/src/pages/customer/Intake.tsx`, `web/src/test/Intake.test.tsx`,
`web/src/components/MultiSelectDropdown.tsx`, `web/src/components/multiselect.css`.
Reason: not a completed/reviewed phase; it makes a **behaviour-affecting scoring
change** (`org_profile_weights.json` removes `US-NY` and rebalances RSS weights
across ~22 states). Must not enter the pilot tag unvetted. Owner: review + green
web tests + a scoring-weights sign-off, then commit separately.

**EXCLUDED — stray tooling (not remediation):** `scripts/build_review_pdf.py`,
`scripts/review_pdf.css` (one-off codebase-review PDF builder).

Branch/PR waiver (AGENTS.md §1.4) re-recorded in `logs/decision-log.md`.

---

## 3 — `python` → `python3` (fixed in the repo, not the VM PATH)

The VM has only `python3`. Fixed the invocations that run **on the VM host**:
- `deploy/azure/deploy.sh`: 3 host calls (`dump_column_types.py`,
  `apply_and_record.py`, `--print-head`) `python` → `python3`.
  (Lines that run *inside* the `python:3.13-slim` container — the healthcheck and
  the `exec api python -c …` — were left; the container has `python`.)
- Added `#!/usr/bin/env python3` shebangs to `scripts/db/apply_and_record.py` and
  `scripts/db/dump_column_types.py`.
- The `scripts/*.py` bare-`python` mentions are usage **docstrings** (prose) and
  were left per instruction.

`bash -n deploy/azure/deploy.sh` passes.

---

## 4 — `.env` completeness + PARTNER_KEY_PEPPER

**18 keys missing on the VM `.env`** (names only), classified:

| Key | Purpose | Class |
|---|---|---|
| `PARTNER_KEY_PEPPER` | SEC-009 HMAC pepper for partner API keys | **SECRET — owner** |
| `RCLONE_CONFIG_BASE64` | base64 rclone creds for off-VM backup upload | **SECRET — owner** |
| `SMTP_PASS` | SMTP password for alert email | **SECRET — owner** |
| `BACKUP_BUCKET` | off-VM backup bucket | owner config |
| `BACKUP_RCLONE_REMOTE` | rclone remote name | owner config |
| `SMTP_HOST` / `SMTP_USER` / `SMTP_FROM` | alert email transport/identity | owner config |
| `BACKUP_PREFIX` | backup path prefix | safe default `prod` |
| `BACKUP_RETAIN_DAYS` | backup retention | safe default `14` |
| `SMTP_PORT` | SMTP port | safe default `587` |
| `RENDERER` | report renderer | safe default `weasyprint` (matches active) |
| `ENABLE_LIVE_F004` | F-004 live-enforcement flag | safe default off |
| `INGESTION_POLITENESS_SECONDS` | crawler politeness delay | safe default |
| `OLLAMA_IMAGE` | ollama image (not deployed on Azure — RunPod hosts the model) | safe default / n/a |
| `SCORING_MODEL_VERSION` / `SOURCE_CORPUS_VERSION` | version stamps | repo-set value |
| `GIT_TAG` | deploy tag | set by `deploy.sh` at runtime |

deploy.sh step 2 requires each key **present** (value may be empty for
non-criticals; only APP_ENV/SUPABASE_*/DATABASE_URL/DOMAIN/HOSTED_QWEN_BASE_URL are
checked non-empty — all present). Owner elected to populate these (from Prompt 7
answer "You handle both").

**`HOSTED_QWEN_API_KEY` empty is confirmed FINE** — deploy.sh's criticals require
only `HOSTED_QWEN_BASE_URL`. Not to be re-raised.

**PARTNER_KEY_PEPPER fail-closed finding (FIXED).** As found, `verify_api_key`
**silently fell back to legacy unsalted sha256 when the pepper was unset** —
i.e. in production with no pepper, partner keys would verify under the weak scheme,
quietly undoing SEC-009. Fixed in `app/services/partner.py`:
- `verify_api_key`: pepper set → accept HMAC **or** legacy (migration-safe); pepper
  **unset in production** → **reject (return None) before any DB lookup**; unset in
  dev/local → legacy allowed for convenience.
- `_hash_key` (mint/store): pepper unset **in production** → raises
  `PartnerKeyPepperMissing` (never store a weak legacy key in prod); dev → legacy
  with a loud warning.
Four tests added (green): fail-closed verify (asserts NO DB call), fail-closed
store (raises), dev legacy still allowed, and pepper-set uses HMAC + keeps the
legacy candidate.

---

## 5 — STAGE 0 re-run (readiness)

| Gate | Status | Evidence |
|---|---|---|
| Ledger accurate for 0043–0047 | ✅ PASS | 50 rows, checksums match, schema objects match (§1a); live ledger test green |
| Migration-ledger tests green (right reason) | ✅ PASS | `test_f02_ingestion_foundation.py` all green incl. live checksum test + updated order test |
| `python3` on deploy path | ✅ PASS (repo) | deploy.sh + shebangs fixed; VM host still needs `python`/venv only if running scripts outside deploy.sh — but deploy.sh now uses `python3` which the VM has |
| SEC-009 pepper fail-closed | ✅ PASS | partner.py hardened + 4 tests |
| Clean tree | ⏳ after commits | Units A+B committed; WIP + tooling intentionally excluded (uncommitted) |
| CI green on tagged commit | ⛔ BLOCKED | tag not cut yet |
| `.env` complete on VM | ⛔ BLOCKED — EXTERNAL | 18 keys (3 secret) — owner |
| Credentials rotated (SEC-007) | ⛔ BLOCKED — EXTERNAL | owner; not claimed |
| Fresh off-VM backup | ⛔ BLOCKED — EXTERNAL | `pg_dump`/`rclone` + 3 backup keys missing on VM |

**Tag NOT created.** Per item 5, `v1.0.0-pilot` is cut only once 1–4 pass; several
gates remain owner-BLOCKED (rotation, VM `.env`, backup). Handing back for those.

> **Full-suite counts — corrected (see [TEST-RECONCILIATION.md](TEST-RECONCILIATION.md), Prompt 7B):**
> `1045 passed · 34 failed · 15 skipped`. The 34 are **NOT** an "unchanged
> pre-existing env class" and **NOT** a commit regression (A/B diff with the
> excluded WIP is identical). They are an **environment change** — the live DB
> advanced after the Phase-4 gate: (28) test fixtures write non-UUID
> `assessment_id`s that migration **0047**'s live UUID CHECK now rejects
> (`23514 check_violation` → HTTP 400); (3) REST `count=exact` on the ~691k-row
> `disclosure_clause` 500s and is misreported as "empty" (data present);
> (3) live data-state assertions. Verdict **A**. The committed code has no
> regression; the count needs re-baselining against the current environment.

---

## Remaining BLOCKED — EXTERNAL (exact owner steps)

1. **Rotate credentials (SEC-007/CRED-001):** DB password, service-role key, JWT
   secret, Tailscale key, seeded `admin@/sme@/customer@` accounts. Confirm no
   null-`organization_id` customer remains.
2. **Populate VM `.env`:** add the 18 keys (secrets `PARTNER_KEY_PEPPER`,
   `RCLONE_CONFIG_BASE64`, `SMTP_PASS` need real values; the rest per the table).
3. **Enable backups on the VM:** `apt-get install -y postgresql-client`; install
   `rclone`; then `./deploy/azure/backup.sh` and verify the object off-VM.
4. **Cut + push the tag** (after 1–3): `git tag -a v1.0.0-pilot`; hand the tag name
   back so `07-DEPLOYMENT` runs `git bundle` → `scp` → clone on VM →
   `./deploy/azure/deploy.sh v1.0.0-pilot`.

**Nothing was deployed. No secret value was printed.**
