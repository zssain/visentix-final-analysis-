# Visentix — Implementation Pack

**Written:** 2026-09-03
**Against:** `github.com/zssain/visentix-final-analysis-` @ `d26f410` (branch `feat/shadcn-ui-system`)
**Grounding rule:** every file path, function name, table, constant and script named in this document was read in that commit. Anything to be created is marked **NEW**. Nothing else is assumed to exist.

---

# PART 0 — Scope

## 0.1 What "implement all the features" actually means here

F01–F21 are shipped or in-progress. The buildable surface is:

| Class | Count | Notes |
|---|---|---|
| Defects in standing guarantees | 4 | Found by reading the code; each restores a promise the docs already make |
| Prerequisites | 2 | Nothing commercial can be built until these land |
| New commercial features | 4 | F22, F24, F25, F26 |
| Protection / infrastructure | 2 | Abuse detection, crawler egress |
| Report rendering | 2 | OD-17 concrete half, then the design comp |
| **Total prompts in this pack** | **14** | |
| Cannot be prompted | 7 | Blocked on a decision; §PART 5 lists what closes each |

## 0.2 Hard blockers found in the current setup

These will stop a feature dead. Each is addressed by a prompt below.

1. **User accounts are a JSON file, not a table.** `app/routers/auth.py:31` sets `_USERS_FILE = Path(__file__).parent.parent.parent / "local_users.json"`. Migration `0011_local_users.sql` created a `local_users` table that **no application code reads** (grepped `app/` — zero hits). You cannot count seats, attach a role to a seat, or write a `user_id` foreign key while the authoritative user record is an ungitted file on disk. **Blocks F22 and F26.** → Prompt P1.1.
2. **The rate limiter is per-replica.** `app/services/ratelimit.py` holds counters in a module-level `_buckets: dict`. Its own docstring carries `TODO(SEC-005)`. On N replicas the effective limit is N × limit. **Any quota built on it is not a quota.** → Prompt P1.2.
3. **The runtime guardrail is missing two Hard Rule 1 terms.** `config/banned_terms.txt` has no `compliant` and no `complies with`. Verified by executing the pattern: "The notice is compliant with CCPA." passes. → Prompt P0.1.
4. **No guard script runs in CI.** Ten `scripts/check_*.py|mjs` exist; grepping `.github/`, `tests/`, `Makefile` and `.claude/` for each returns zero. Five documents claim they run. → Prompt P0.2.
5. **Migration 0049 is unapplied**, so `/admin/trigger-assessment/async` and `/admin/quarterly/build/async` cannot run. → Prompt P0.4.

## 0.3 Where the stack makes this harder than it needs to be

- **Service-role key + no RLS at runtime.** `app/db.py` talks to Postgres as the service role, so RLS is bypassed and `app/services/tenancy.py::customer_org_scope` is the *only* isolation. Every new tenant-scoped table inherits that: the app-layer filter is the guarantee, so every new route must join `CAPTURE_ROUTES` in `tests/test_org_isolation.py`. On a normal Postgres app you would get a second line of defence for free.
- **In-process everything.** Rate limiting, login throttling and the APScheduler job store are all single-process assumptions. Container Apps scales horizontally; three separate subsystems must move to shared state before you scale past one replica.
- **WeasyPrint cannot read `oklch()`** and Tailwind cannot reach it, so the PDF permanently keeps a second stylesheet. That is not fixable, only manageable — hence P4.1 generating it rather than hand-maintaining it.
- **Two auth paths.** `app/auth.py` verifies Supabase ES256 tokens and reads `profiles`; `app/routers/auth.py` issues local HS256 tokens from a JSON file. Every account feature has to decide which path it serves. P1.1 collapses this.

---

# PART 1 — System specification

## 1.1 Feature inventory (current state)

| ID | Feature | State in code |
|---|---|---|
| F01 | Intake & decomposition | Shipped. `app/services/intake/{extract,decompose,persist,discover}.py` |
| F02 | Corpus ingestion & monitoring pipelines | Partial. `app/services/ingestion/connectors/{ftc,edgar,openweb,princeton,state_ag,hhs_ocr,cppa,_enforcement}.py` |
| F03 | Profiling, benchmarking, normalization | Shipped. `app/services/profiling/`, `app/services/benchmark/population.py`, `app/services/normalization/engine.py` |
| F04 | Scoring, findings, confidence | Shipped. `app/services/scoring/{formulas,formulas_advanced,findings,obligation_match}.py`, `app/services/live_scoring.py` |
| F05 | Report generation | Shipped. `app/services/report/{assembly,renderer,explain,clause_data}.py` |
| F06 | SME workbench & review gate | Shipped. `app/services/review.py`, `app/routers/review.py` |
| F07 | Continuous monitoring | Partial. `app/services/monitoring.py`, `app/services/alerts.py`; UI blocked on populated endpoints |
| F08–F10 | Codex, admin console, auth/tenancy | Shipped |
| F11 | White-label APIs | **Superseded by F20** — spec not marked |
| F12 | Quarterly + bulk | **Superseded by F19 + F21** — spec not marked |
| F13 | Framework crosswalk | UI on mock M-25 |
| F14 | Rewrite prompts | **Superseded by F18** — spec not marked |
| F15 | Trust center | UI on mock M-27 |
| F16 | Vendor due diligence | UI on mock M-28 |
| F17 | Evaluation harness | Backend only, no UI. `app/routers/eval.py` |
| F18 | Clause rewrite | Shipped. `app/services/rewrite.py` |
| F19 | Bulk screening | In progress. `app/services/bulk.py`, `app/routers/bulk.py` |
| F20 | Partner portal | In progress. `app/services/partner.py`, `app/routers/partner.py` |
| F21 | Quarterly report | In progress. `app/services/quarterly.py`, `app/routers/quarterly.py` |
| **F22** | **Accounts, seats, entitlements** | **NEW** |
| **F24** | **Scheduled reassessment** | **NEW** |
| **F25** | **Usage metering** | **NEW** |
| **F26** | **Firm RBAC & audit log** | **NEW** |

*(F23 — third-party assessment — is deliberately unnumbered in the build order; see §PART 5.)*

## 1.2 Data model additions

Only what this pack adds. Existing tables are read-only inputs per AGENTS.md §2.

| Table | Prompt | Purpose |
|---|---|---|
| `app_user` **NEW** | P1.1 | The queryable user record replacing `local_users.json` |
| `plan` **NEW** | P2.1 | Purchasable tier catalog |
| `organization_entitlement` **NEW** | P2.1 | Which plan an org holds, plus overrides |
| `usage_event` **NEW** | P2.1 | Append-only record of every metered action |
| `audit_event` **NEW** | P2.2 | Append-only record of every user action |
| `scheduled_check` **NEW** | P2.3 | Per-org recurring reassessment configuration |
| `submission_entity_flag` **NEW** | P3.1 | Multi-organization submission detections |

Every one requires, per `db/migrations/_TEMPLATE.sql`:
```sql
ALTER TABLE public.<t> ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.<t> FROM anon, authenticated;
```

## 1.3 API surface additions

| Method | Path | Router file | Prompt |
|---|---|---|---|
| GET | `/account/entitlements` | `app/routers/account.py` **NEW** | P2.1 |
| GET | `/account/usage` | `app/routers/account.py` **NEW** | P2.1 |
| POST | `/account/seats` | `app/routers/account.py` **NEW** | P2.1 |
| DELETE | `/account/seats/{user_id}` | `app/routers/account.py` **NEW** | P2.1 |
| GET | `/admin/entitlements` | `app/routers/admin.py` (modify) | P2.1 |
| POST | `/admin/entitlements` | `app/routers/admin.py` (modify) | P2.1 |
| GET | `/account/audit` | `app/routers/account.py` (modify) | P2.2 |
| GET | `/account/schedule` | `app/routers/account.py` (modify) | P2.3 |
| PUT | `/account/schedule` | `app/routers/account.py` (modify) | P2.3 |
| GET | `/partner/usage` | `app/routers/partner.py` (modify) | P2.4 |

## 1.4 Non-functional requirements

- **Auth.** Two token paths exist today; P1.1 keeps both but gives them one user store. New routes use the existing `require_role()` dependency from `app/auth.py`.
- **Tenancy.** Every tenant-scoped read derives its filter from `customer_org_scope()`. Every new route is added to `CAPTURE_ROUTES` in `tests/test_org_isolation.py`. Cross-tenant reads return **403** (verified: `tests/test_org_isolation.py` lines 46, 57, 83, 402).
- **Validation.** URL intake goes through `ssrf.resolve_and_validate` at save *and* send, resolving once and connecting to the pinned IP.
- **Error handling.** Quota denial is `402`, not `403` — the caller is authorized, the allowance is spent. Seat denial is `409`.
- **Honest numbers.** Every displayed count is live-queried or absent. No default plan, no cached counter, no zeroed chart standing in for missing data.
- **Migrations.** Additive only, idempotent, RLS on every new table, applied via `scripts/db/apply_and_record.py`, appended to `APPLY_NOW` in that file. Next free prefix after 0049 is **0050**.
- **Performance.** `usage_event` and `audit_event` are append-only and queried by aggregation; both need `(organization_id, at DESC)` indexes from day one or the account panel degrades linearly with usage.

---

# PART 2 — Dependency order

```
WAVE 0 — restore standing guarantees (no dependencies, ~1.5 days total)
  P0.1  Reconcile the banned-term lists
  P0.2  Wire the ten guard scripts into CI
  P0.3  Mark F11/F12/F14 superseded + add a spec-drift guard
  P0.4  Apply migration 0049

WAVE 1 — prerequisites (blocks everything commercial, ~4 days)
  P1.1  Move auth off local_users.json onto a table      ← blocks P2.1, P2.2
  P1.2  Shared-store rate limiter                         ← blocks any real cap

WAVE 2 — commercial core
  P2.1  F22 Accounts, seats, entitlements                 ← needs P1.1, P1.2
  P2.2  F26 Firm RBAC + per-user audit log                ← needs P1.1
  P2.3  F24 Scheduled reassessment                        ← needs P2.1 + OD-28
  P2.4  F25 Usage metering (partner + consumption)        ← needs P2.1

WAVE 3 — protection & infrastructure (independent of Wave 2)
  P3.1  Multi-organization submission detection
  P3.2  Crawler egress separation

WAVE 4 — report rendering
  P4.1  Generate report.css from theme.css                ← independent
  P4.2  Adopt the design comp (unblocked sections only)   ← needs P4.1
```

---

# PART 3 — Execution prompts

Each block below is self-contained and can be handed to a coding agent as-is. Each assumes the agent first obeys `AGENTS.md` §1.1 — load `visentix-specs/01-foundation/{schema,intelligence-logic,business-logic,design-system}.md` plus the named feature spec.

---

## P0.1 — Reconcile the banned-term lists

**Goal.** Make one banned-term list the single source for the runtime guardrail, CI, and tests, so a Hard Rule 1 term cannot pass a report build.

**Why here.** It is the cheapest fix in the pack and it repairs a live gap in the product's central safety claim. Nothing depends on it, so it should not wait.

**Context an agent needs.** `app/services/guardrail.py` loads its terms at import from `config/banned_terms.txt` (line: `CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"`). `.github/workflows/spec-guard.yml` reads a *different* file, `scripts/data/banned_terms.txt`. `tests/test_guardrail.py:17-20` hand-copies a *third* subset into a `@pytest.mark.parametrize`. All three differ. `config/banned_terms.txt` is missing `compliant` and `complies with`; `scripts/data/banned_terms.txt` is missing `violate`, `violated`, `violating`, `violations`, `in violation of`, `found guilty`, `legally liable`. AGENTS.md Hard Rule 1 names the authoritative set.

**Files to modify**
- `config/banned_terms.txt` — become a generated artifact; add the missing terms so it is a superset of Hard Rule 1.
- `scripts/data/banned_terms.txt` — designate this the source of truth (its own header already claims to be) and add the missing inflections.
- `tests/test_guardrail.py` — replace the hardcoded `@pytest.mark.parametrize` list at lines 17-20 with a list read from the source file, and add a new test asserting set equality between the two files.

**Files to create**
- `scripts/build_banned_terms.py` **NEW** — reads `scripts/data/banned_terms.txt`, writes `config/banned_terms.txt` with a generated-file header. Mirror the pattern in the existing `scripts/build_agents_md.py`.

**How the modifications work**
1. In `scripts/data/banned_terms.txt`, add: `violate`, `violated`, `violating`, `violations`, `in violation of`, `found guilty`, `legally liable`. Keep `compliant`, `complies with`, `non-compliant`, `noncompliant`, `violation`, `violates`, `illegal`, `unlawful`, `breach of law`, `guilty`, `liable`.
2. `scripts/build_banned_terms.py` writes `config/banned_terms.txt` from it, prefixed with `# GENERATED by scripts/build_banned_terms.py — do not edit by hand.`
3. In `tests/test_guardrail.py`, the parametrize list becomes `load_banned_terms()` (already imported at line 11).
4. Add `test_banned_term_lists_are_identical()` asserting the two files' non-comment, non-blank lines are equal as sets.
5. Add `test_hard_rule_1_terms_all_blocked()` asserting each of the eleven terms named in AGENTS.md Hard Rule 1 produces a non-empty `check_generated_prose()` result.

**Migration.** None.
**Dependencies.** None.
**Env vars.** None.

**Acceptance criteria**
- `python3 -c "from app.services.guardrail import check_generated_prose; assert check_generated_prose('The notice is compliant with CCPA.')"` — non-empty.
- Same for `"This disclosure complies with GDPR requirements."`.
- `pytest tests/test_guardrail.py` green.
- Editing `scripts/data/banned_terms.txt` and re-running the build script changes `config/banned_terms.txt`.
- The set-equality test fails if either file is edited alone.

**Edge cases**
- `_build_pattern` sorts by length descending so multi-word terms match first — adding `compliant` must not shadow `non-compliant`. The parametrized test over both terms proves it.
- Adding `liable` risks matching inside "reliable". `_build_pattern` wraps in `\b(...)\b`, so it does not; add a negative test asserting `"a reliable source"` passes.
- Report builds that previously passed may now fail if authored templates contain `compliant`. Run a full report build before merging and fix any template that trips, using the approved-alternative mapping in `business-logic.md` §2 — do **not** weaken the list.

---

## P0.2 — Wire the guard scripts into CI

**Goal.** Make the ten `scripts/check_*` guards actually run, so the guarantees five documents attribute to them become true.

**Why here.** Every later prompt in this pack relies on those guards to catch drift. Wiring them after building features means the features ship unguarded.

**Context.** `.github/workflows/ci.yml` runs pytest, `npx tsc --noEmit` and `npx vitest`. `.github/workflows/spec-guard.yml` runs three inline checks. Neither invokes any of: `check_acronyms.py`, `check_colors.py`, `check_contrast.mjs`, `check_dead_css.py`, `check_docs_layout.py`, `check_hedging.py`, `check_labels.py`, `check_masking.py`, `check_mocks.py`, `check_routes.py`. `Makefile` has one target (`census`).

**Files to modify**
- `.github/workflows/ci.yml` — add a third job, `guards`.
- `Makefile` — add a `guards` target so the same set runs locally.

**How**
1. New job `guards` in `ci.yml`, `runs-on: ubuntu-latest`, checkout + `setup-python@v5` (3.13) + `setup-node@v4` (20). Install `requirements-ci.txt` and run `npm ci` in `web/` (needed by the `.mjs` guard and the TSX-reading Python guards).
2. Run each script as its own named step so a failure names the guard.
3. **Run each script once first and record the result.** Guards that have never run in CI will very likely fail on existing debt. Any guard that fails on the unmodified tree gets `continue-on-error: true` **plus a tracking row in `visentix-specs/00-plan/remaining-work.md` §1** naming the debt. Do not weaken a guard to make it pass — that is the failure mode `AGENTS.md` §1.6 names.
4. `Makefile`: `guards:` target invoking the same list via `$(PY)`.

**Migration / dependencies / env.** None.

**Acceptance criteria**
- A PR that adds a hardcoded hex outside `web/src/theme.css` fails the `check_colors` step.
- A PR adding a `mockData` import without a `<MockBadge>` fails the `check_mocks` step.
- `make guards` reproduces the CI result locally.
- Every guard placed in `continue-on-error` has a corresponding row in remaining-work §1.

**Edge cases**
- `check_contrast.mjs` reads `web/src/theme.css`; if it needs `node_modules`, the job must `npm ci` before running it.
- Some guards may expect a repo-root CWD. Set `working-directory` explicitly per step.
- Do not make the `guards` job required in branch protection until every guard passes without `continue-on-error`.

---

## P0.3 — Mark superseded specs and add a drift guard

**Goal.** Stop an agent implementing from a retired spec.

**Why here.** Every prompt in this pack tells an agent to load feature specs. Three of them describe surfaces that no longer exist.

**Context.** `visentix-specs/02-features/F21-quarterly.md:9` says it replaces F12's mocks M-15–M-18. `F19-bulk.md:9` replaces M-23/M-24. `F20-partner.md:78` replaces M-19–M-22. `F18-rewrite.md:3` is shipped over F14's studio. `00-plan/mock-tracker.md` already records the ownership transfer in its owner column (`F12→F21`, `F11→F20`, `F14→F18`). The feature specs carry no supersession banner. The only `mockData` importers left in `web/src` are the crosswalk, trust and vendors pages, carrying M-25, M-27, M-28.

**Files to modify**
- `visentix-specs/02-features/F11-white-label-and-intelligence-apis.md` — status line → `superseded by F20 (2026-07-28)`; add a banner under the title.
- `visentix-specs/02-features/F12-quarterly-report-and-bulk-analysis.md` — → `superseded by F21 (quarterly) + F19 (bulk)`.
- `visentix-specs/02-features/F14-notice-rewrite-prompts.md` — → `superseded by F18 (2026-07-28)`.
- `visentix-specs/README.md` — line 28 (`F01 … F12 … the feature catalog`) → `F01 … F22`; line 57 (`Current product context (July 2026)`) → current date.
- `AGENTS.md` — regenerate via `python3 scripts/build_agents_md.py` so the spec index reflects the new statuses. Do not hand-edit inside the `<!-- BEGIN GENERATED -->` markers.

**Files to create**
- `scripts/check_specs.py` **NEW** — fails if any `mock-tracker.md` row's owner column contains `Fxx→Fyy` while `02-features/Fxx-*.md` carries no supersession banner.

**Migration / dependencies / env.** None.

**Acceptance criteria**
- `grep -l "superseded by" visentix-specs/02-features/*.md` returns F11, F12, F14.
- `python3 scripts/check_specs.py` exits 0.
- Reverting one banner makes it exit non-zero.
- `python3 scripts/build_agents_md.py` produces no diff after the run (AGENTS.md is fresh).
- Add `check_specs.py` to the `guards` job from P0.2.

**Edge cases**
- F12's supersession is split across two successors — the banner must name both, and the guard must accept a banner naming several.
- Do not delete the retired specs. Git history is not a substitute for a reader seeing why a spec stopped being live.

---

## P0.4 — Apply migration 0049

**Goal.** Land `assessment_job.kind` so the two async admin endpoints can run.

**Why here.** One command, and two endpoints plus two deselected tests are waiting on it.

**Context.** `db/migrations/0049_assessment_job_kind.sql` exists and is registered in `APPLY_NOW` in `scripts/db/apply_and_record.py:64`. `remaining-work.md` §2 states it is additive and idempotent, and that `/admin/trigger-assessment/async` and `/admin/quarterly/build/async` cannot run until it lands. Two ledger tests are deselected meanwhile because the same test name exists in `tests/test_migrations.py` and `tests/test_f02_ingestion_foundation.py`.

**Command**
```bash
python3 scripts/db/apply_and_record.py
```

**Files to modify.** After the migration lands, remove the two deselections (search the pytest config / `pytest.ini` / `pyproject.toml` for the deselect entries and delete only those two).

**Acceptance criteria**
- `assessment_job.kind` exists in `information_schema.columns`.
- A row for `0049_assessment_job_kind.sql` exists in `schema_migrations`.
- `POST /admin/trigger-assessment/async` returns 202.
- Both previously-deselected ledger tests run and pass.

**Edge cases**
- Re-running must change nothing (idempotency). Verify by running it twice.
- If the ledger row appears but the column does not, the applier's statement split has failed — do not paper over it by hand-applying; fix the applier.

---

## P1.1 — Move authentication onto a database table

**Goal.** Replace the `local_users.json` file with a queryable `app_user` table, so users can be counted, joined to and referenced by foreign key.

**Why here.** F22 needs to count seats. F26 needs to attach a role to a user and write `user_id` on audit rows. Neither is possible against a JSON file. This is the single largest blocker in the pack.

**Context.** `app/routers/auth.py:31` reads `_USERS_FILE = Path(__file__).parent.parent.parent / "local_users.json"` and issues HS256 tokens. `app/auth.py:107-145` verifies Supabase ES256 tokens and loads role from the `profiles` table via PostgREST. Migration `0004_phase2_profiles_rls.sql:17` created `profiles`. Migration `0011_local_users.sql` created a `local_users` table with `CHECK (role IN ('customer','sme','admin'))` that **no code reads**. Migration `0039_f20_partner_portal.sql:11` added `partner_admin` to the `user_role` enum.

**Decision required before starting.** Two viable targets: extend the existing `profiles` table (already read by the Supabase path, unifies both paths) or promote the dead `local_users` table. **Recommendation: `profiles`**, because it collapses two auth paths into one user store instead of leaving two. This prompt assumes `profiles`; if the owner rules otherwise, substitute the table name throughout. **Do not proceed without this ruling.**

**Files to create**
- `db/migrations/0050_app_user_credentials.sql` **NEW** — add nullable credential columns to `profiles`: `email text UNIQUE`, `password_hash text`, `salt text`, `created_at timestamptz DEFAULT now()`, `disabled_at timestamptz`. Additive and nullable so existing Supabase-auth rows are untouched.
- `scripts/db/migrate_local_users.py` **NEW** — one-shot importer reading `local_users.json` and upserting into `profiles` with `ON CONFLICT DO NOTHING`. Prints a count. Never deletes the JSON file.
- `app/services/users.py` **NEW** — `get_user_by_email()`, `list_users_for_org()`, `count_seats(org_id)`, `create_user()`, `disable_user()`. All via the existing DB access pattern used by `app/auth.py:107` (PostgREST, service role).

**Files to modify**
- `app/routers/auth.py` — the login handler currently loads `_USERS_FILE`. Replace the file read with `app.services.users.get_user_by_email()`. **Keep the password hashing scheme byte-identical** (read the existing hash/salt verification in this file and reuse it unchanged) or every existing credential breaks. Delete `_USERS_FILE` and its `Path` import only after the last reference is gone.
- `app/auth.py` — no change to token verification. Both token types continue to work.
- `db/migrations/` registration — append `0050_app_user_credentials.sql` to `APPLY_NOW` in `scripts/db/apply_and_record.py`.

**Migration command**
```bash
python3 scripts/db/apply_and_record.py
python3 scripts/db/migrate_local_users.py   # one-shot import
```

**Dependencies.** None new — reuse the hashing already in `app/routers/auth.py`.
**Env vars.** None new.

**Acceptance criteria**
- An existing credential from `local_users.json` logs in successfully after the import, with no password reset.
- `count_seats(org_id)` returns the number of enabled users for that org.
- A user with `disabled_at` set cannot log in.
- Cross-tenant: `list_users_for_org` derives its filter from `customer_org_scope()`; add its route (when P2.1 exposes one) to `CAPTURE_ROUTES`.
- `grep -rn "local_users.json" app/` returns nothing.
- `pytest tests/` green, including `tests/test_auth.py` (note: this module is in `_LIVE_DB_MODULES` in `conftest.py` and auto-skips without a reachable Supabase — run it locally with a live DB, or the gate is decorative).

**Edge cases**
- **The JSON file may contain users with no `organization_id`.** Today that yields `allowed=False` at query time. Import them with a null org and leave the deny behaviour intact — do not invent an org.
- `profiles.user_id` is the PK on the Supabase path; the local path's ids must not collide. Generate UUIDs on import and record the mapping in the script's output.
- `partner_admin` exists in the `user_role` enum but not in `local_users`'s CHECK. Since this migration targets `profiles`, confirm `profiles.role` accepts the full enum before importing.
- Keep `local_users.json` readable behind a feature flag for one release so a failed cutover is reversible.

---

## P1.2 — Shared-store rate limiter

**Goal.** Make rate limits cluster-wide so a limit means what it says on more than one replica.

**Why here.** F22 quotas and F25 metering both need an enforcement point that survives horizontal scaling. Building them on a per-replica counter produces limits that silently multiply by replica count.

**Context.** `app/services/ratelimit.py` holds `_buckets: dict[str, deque[float]]` in module memory with a `Lock`. Its docstring carries the `!!! MULTI-REPLICA MARKER !!!` and `TODO(SEC-005)`. `app/routers/auth.py:38-46` has a *second*, separate in-process limiter (`_rl_fail`, `_rl_check`) for login attempts with the same caveat. Consumers: `app/routers/assessments.py:219,311` (`_CREATE_LIMIT = 10`/60s), `app/routers/reports.py:328` (`_PDF_LIMIT = 20`/60s), `app/routers/bulk.py:80` (`_BULK_JOBS_LIMIT = 3`/60s).

**Files to modify**
- `app/services/ratelimit.py` — keep `check_rate_limit()`'s signature exactly as it is (`key`, `*`, `limit`, `window_s`, `now`) so no caller changes. Add a backend abstraction inside: if `settings.redis_url` is set, use a Redis sorted-set sliding window; otherwise fall back to the existing `_buckets` path and log a warning once at startup. Keep the `now` injection for deterministic tests.
- `app/config.py` — add `redis_url: str = Field(default="")` in the same style as the existing fields.
- `app/routers/auth.py` — migrate `_rl_check`/`_rl_record_failure` onto the same backend so there is one limiter, not two.
- `requirements.txt` — add `redis==5.2.1`.
- `.env.example` — add `REDIS_URL=` with a dummy value and no real credential.

**Dependencies**
```bash
pip install redis==5.2.1
```

**Env vars.** `REDIS_URL` — e.g. `redis://localhost:6379/0`. Empty means in-process fallback.

**Acceptance criteria**
- With `REDIS_URL` unset, existing behaviour and all current tests are unchanged.
- With Redis running, two processes sharing the key hit the limit at the combined count, not twice the limit.
- A Redis connection failure **fails open with a logged error**, never a 500 — a monitoring outage must not take the API down. Record this choice explicitly in the module docstring.
- `Retry-After` is still returned on 429.
- The `TODO(SEC-005)` comment is removed only once the Redis path is the default in production config.

**Edge cases**
- Sliding-window via sorted set needs `ZREMRANGEBYSCORE` + `ZADD` + `ZCARD` in a pipeline or a Lua script, or two concurrent requests can both pass at the boundary.
- Key namespacing: prefix with the app env so staging and production do not share counters.
- Redis latency is now on the request path for every limited endpoint. Set a short socket timeout (e.g. 100ms) and treat a timeout as fail-open.
- This does **not** make quotas transactional — see P2.1's edge cases for why the quota reservation needs the database, not Redis.

---

## P2.1 — F22: Accounts, seats and entitlements

**Goal.** Give each organization a plan that grants seats and a periodic report allowance, enforced at one server-side chokepoint.

**Why here.** It is the substrate for metering (P2.4), scheduled checks (P2.3) and in-firm roles (P2.2). It cannot start before P1.1 (seats need a user table) or P1.2 (a cap needs a real enforcement point).

**Context.** No entitlement, quota, plan or billing table exists — grepped `app/`, `db/`, `web/src` for `entitlement|quota|billing|subscription|seat_limit|plan_tier` with no structural hits. `business-logic.md` §3 defines T1–T4 with price ranges but nothing enforces them. `version-ladder.md` gates surfaces by *role*, not tier. Existing caps: `app/routers/bulk.py` rejects >200 rows (F19 §78). The full spec draft is in `F22-accounts-seats-and-entitlements.md` (delivered separately) — **read it before starting; this prompt implements it.**

**Files to create**
- `db/migrations/0051_f22_entitlements.sql` **NEW** — `plan`, `organization_entitlement`, `usage_event` per §1.2 above, each with RLS enabled and `REVOKE ALL … FROM anon, authenticated` per `_TEMPLATE.sql`. Indexes: `usage_event (organization_id, at DESC)`, `organization_entitlement (organization_id) WHERE status = 'active'`.
- `app/services/entitlements.py` **NEW** — `resolve(org_id)` returning effective plan values with overrides applied; `check_and_reserve(org_id, user_id, kind)` returning allow/deny plus remaining, writing the `usage_event`; `usage_summary(org_id, period)`.
- `app/routers/account.py` **NEW** — the four `/account/*` routes from §1.3.
- `web/src/pages/customer/Account.tsx` **NEW** — plan, seats used/limit, reports used/remaining, period end, states per the spec's Behavior section.
- `tests/test_entitlements.py` **NEW**.

**Files to modify**
- `app/main.py` — add `from app.routers import account` to the import block (line 10-13 area) and `app.include_router(account.router)` alongside the existing includes.
- `app/routers/assessments.py` — call `entitlements.check_and_reserve()` at the top of both create handlers, immediately after the existing `check_rate_limit(...)` calls at lines 219 and 311.
- `app/routers/admin.py` — add the two `/admin/entitlements` routes.
- `scripts/db/apply_and_record.py` — append `0051_f22_entitlements.sql` to `APPLY_NOW`.
- `tests/test_org_isolation.py` — add all four `/account/*` routes to `CAPTURE_ROUTES`.

**Migration command**
```bash
python3 scripts/db/apply_and_record.py
```

**Dependencies / env vars.** None new.

**Acceptance criteria.** AC-1 through AC-11 of the F22 spec, with **AC-6 amended** (the original said seats are computed from `local_users`; after P1.1 they are computed from the `profiles`/`app_user` table). Additionally:
- Denial returns `402` with plan name, allowance and period end in the body.
- No default plan is applied anywhere — an org with no entitlement row is refused and shows honest absence.
- Every `/account/*` route returns 403 for a cross-org caller.

**Edge cases**
- **Reservation must be atomic.** Two concurrent requests at allowance − 1 can both pass a read-then-write check. Do the reservation in a single SQL statement that inserts the `usage_event` conditional on the current count, and return the post-insert count. Do **not** use the Redis limiter for this — an abuse throttle may fail open, a billing quota may not.
- A failed assessment's charge is **OD-27, unresolved.** Until it closes, write the `usage_event` with `counted = false` and `not_counted_reason = 'pending_policy'` so no customer is charged for an outcome the policy has not yet defined, and the rows can be recounted retroactively once ruled.
- Period boundaries are **OD-25, unresolved.** Do not implement rollover until it closes; scope this prompt to a fixed `period_start`/`period_end` on the entitlement row.
- Plan values are **OD-24, unresolved.** Seed no rows. Ship the tables and the enforcement, and let the first `plan` row be inserted by an admin once the owner confirms the numbers in writing.
- Suspended entitlements must still permit report re-pulls — a customer must never lose an artifact they may already have forwarded.

---

## P2.2 — F26: In-firm roles and per-user audit log

**Goal.** Let a firm distinguish its own users' permissions, and record every user action in a queryable, append-only log.

**Why here.** Needs P1.1's user table. Independent of P2.1, so it can run in parallel.

**Context.** Roles today are platform-level: `customer`, `sme`, `admin`, plus `partner_admin` in the `user_role` enum (migration 0039). `require_role()` in `app/auth.py` gates routes. There is **no request-level audit middleware** — nothing records that a user viewed or exported a report. The nearest existing records are `training_label` (SME corrections) and `assessment_review` (who approved, when), both review-scoped.

**Files to create**
- `db/migrations/0052_f26_audit_and_firm_roles.sql` **NEW** — `audit_event(id, organization_id, user_id, action, resource_type, resource_id, at, request_id)` with RLS + revoke, index `(organization_id, at DESC)`. Add a nullable `firm_role text` column to the user table from P1.1.
- `app/middleware/audit.py` **NEW** — FastAPI middleware writing one `audit_event` per authenticated request. Buffer and write asynchronously; a logging failure must never fail the request.
- `tests/test_audit_log.py` **NEW**.

**Files to modify**
- `app/main.py` — register the middleware after `CORSMiddleware` (line ~53).
- `app/routers/account.py` — add `GET /account/audit`, org-scoped, paginated.
- `tests/test_org_isolation.py` — add `/account/audit` to `CAPTURE_ROUTES`.

**Migration command.** `python3 scripts/db/apply_and_record.py`

**Acceptance criteria**
- Every authenticated request produces exactly one `audit_event` with the acting user and org.
- Unauthenticated requests produce none.
- A customer reading `/account/audit` sees only their org's rows; a cross-org read returns 403.
- Audit writes never appear in the request's latency path in a way that can fail it — kill the DB and confirm requests still succeed.
- No request body, notice text, or credential is written to `audit_event`. Assert this in a test.

**Edge cases**
- **This is the feature that most easily becomes a privacy problem.** `business-logic.md` §6 and the published notice constrain what you retain. Log the action and the resource id, never the content.
- "Learn patterns from usage" is explicitly **out of scope** for this prompt. Using audit data to adapt behaviour is a purpose change over data collected for audit, and `version-ladder.md`'s governance trigger requires the privacy notice and subprocessor list to be reopened and re-approved *before* it ships. Capture only.
- Retention: the published commitment is usage/audit logs for 12 months. Add the retention job in the same PR or record it as a tracked follow-up — an append-only log with no expiry silently breaks a published promise.
- `firm_role` must not widen platform authority. A firm admin manages seats within their org and nothing else; `require_role()` still governs platform routes.

---

## P2.3 — F24: Scheduled reassessment

**Goal.** Run recurring reassessments per organization on a plan-determined cadence.

**Why here.** Needs P2.1, because a scheduled run consumes allowance and the boundary question (OD-28) must be answered first.

**Blocked until OD-28 closes.** Whether a scheduled re-assessment consumes a report from the allowance is unresolved. Do not start without a ruling — implementing either answer bakes a billing policy into code.

**Context.** `app/services/scheduler.py` runs APScheduler with a SQLAlchemy job store, started **only** from the FastAPI lifespan when `SCHEDULER_ENABLED=true`, never at import. Existing jobs in `app/services/jobs/`: `monitor_notices.py`, `pull_regulators.py`, `refresh_benchmarks.py`, plus `framework.py` (with `reap_stale_runs()` called from `app/main.py`'s lifespan). Cron and enabled state come from `platform_setting` rows (`job.<name>.cron` / `.enabled`), so ops toggle without a deploy. `app/services/reassessment.py` already holds `trigger_reassessment` — the verified multi-notice batch kernel F19 reuses.

**Files to create**
- `db/migrations/0053_f24_scheduled_checks.sql` **NEW** — `scheduled_check(id, organization_id, notice_id, cadence, next_run_at, last_run_at, enabled, created_at)` with RLS + revoke.
- `app/services/jobs/scheduled_reassessment.py` **NEW** — a `run()` following the exact shape of `monitor_notices.py`; selects due rows, calls the existing `trigger_reassessment`, calls `entitlements.check_and_reserve()` per the OD-28 ruling.
- `tests/test_scheduled_reassessment.py` **NEW**.

**Files to modify**
- `app/services/scheduler.py` — add the new job to `JOB_FUNCS` (the dict at module level, so the SQLAlchemy job store can serialize it by import path) and to `JOB_DEFAULTS` in `app/services/jobs/framework.py`.
- `app/routers/account.py` — `GET`/`PUT /account/schedule`.

**Env vars.** `SCHEDULER_ENABLED=true` is required for any of this to fire; it is currently false in the pilot.

**Acceptance criteria**
- A due `scheduled_check` triggers exactly one reassessment per period; a second scheduler tick in the same period does not double-run.
- Allowance interaction matches the OD-28 ruling exactly.
- With `SCHEDULER_ENABLED=false` nothing fires and no test spins up a scheduler.
- A crashed worker leaves no permanently-`running` job — `reap_stale_runs()` reclaims it at next boot.

**Edge cases**
- Multiple replicas each running APScheduler will double-fire. The SQLAlchemy job store does not by itself provide leader election. Either pin the scheduler to one replica or add a `platform_setting` advisory lock — decide explicitly and document it in the module docstring.
- An org whose allowance is exhausted at schedule time: the run must be skipped with a recorded reason, not silently dropped and not run for free.
- Cadence must come from the plan, not be hand-set per org, or the tier means nothing.

---

## P2.4 — F25: Usage metering

**Goal.** Turn logged partner usage into metered usage with enforceable per-contract limits.

**Why here.** F11 AC-3 is unmet and mock-tracker M-20 names it as future work. Needs P2.1's `usage_event` and P1.2's shared limiter.

**Context.** Migration `0039_f20_partner_portal.sql:58-67` created `feed_access_log` (partner_id, api_key_id, endpoint, timestamp, row_count) and `partner_api_key` (sha256 hash only, plaintext returned once). Every `/feed/white-label` call is **logged but not limited** — there is no rate-limit check on that route. `app/routers/feed.py` serves it; `app/services/partner.py` holds the key logic. The partner portal usage meter is UI-mocked only.

**Files to create**
- `db/migrations/0054_f25_partner_limits.sql` **NEW** — add nullable `rate_limit_per_min int` and `monthly_call_allowance int` to `partner` (additive, nullable, so existing partners are unconstrained until set).
- `tests/test_partner_metering.py` **NEW**.

**Files to modify**
- `app/routers/feed.py` — after the existing `X-Partner-Key` hash comparison, call `check_rate_limit()` keyed on `partner_id` with the partner's configured limit, then the monthly allowance check aggregated from `feed_access_log`.
- `app/routers/partner.py` — add `GET /partner/usage` returning calls this period, allowance, remaining, all aggregated live.
- `visentix-specs/00-plan/mock-tracker.md` — mark M-20's rate-limit half Replaced once this lands.

**Acceptance criteria**
- A partner exceeding `rate_limit_per_min` receives 429 with `Retry-After`.
- A partner exceeding `monthly_call_allowance` receives 402.
- A partner with both columns null is unlimited (existing behaviour preserved).
- `GET /partner/usage` figures are aggregated from `feed_access_log`, never cached.
- F11 AC-3 can be marked met.

**Edge cases**
- Aggregating `feed_access_log` per request will get slow; index `(partner_id, at DESC)` and consider a period-scoped count.
- Suppression still applies to what the feed serves (DIR-006, `n < 10`); metering must not become a way to infer suppressed cohorts by counting `row_count` across queries.

---

## P3.1 — Multi-organization submission detection

**Goal.** Detect when one submitted page contains several organizations' notices, so it is neither scored as one nor counted as one.

**Why here.** Independent of the commercial waves. It becomes urgent the moment quotas exist, because "one submission = one report" turns a data-quality bug into a billing exploit.

**Context.** `app/services/intake/decompose.py` has the decompose-v2 noise filter (`_section_structural_noise`, `DECOMPOSE_VERSION = "decompose-v2-noisefilter"`) which flags nav/heading/metadata/list fragments as `is_noise` but keeps them for lineage. There is **no** detection of multiple organizations in one document. All text on one URL merges into a single assessment, producing a blended profile, a wrong cohort match, and one score across several companies.

**Files to create**
- `db/migrations/0055_submission_entity_flag.sql` **NEW** — `submission_entity_flag(id, assessment_id, detected_entities jsonb, confidence numeric, flagged_at)` with RLS + revoke.
- `app/services/intake/entity_scan.py` **NEW** — a **deterministic** scan over decomposed sections for multiple distinct legal-entity signals (distinct company names in "we"/"our" self-reference positions, multiple distinct "Last updated" blocks, multiple distinct contact/DPO addresses, repeated section-header sequences).
- `tests/test_entity_scan.py` **NEW** — fixtures: a normal notice, two concatenated notices, a notice quoting another company's name in passing (must not flag).

**Files to modify**
- `app/services/intake/persist.py` — write the flag row after decomposition.
- `app/routers/assessments.py` — when flagged above threshold, return the assessment in a `needs_review` state rather than scoring it.

**Acceptance criteria**
- A page with two concatenated notices is flagged and not scored.
- A single notice mentioning a partner company by name is **not** flagged.
- The flag is visible in the assessment response with the detected entity names.
- Deterministic — the same input flags identically across runs. No LLM call (Hard Rule 2: the model classifies and phrases, it never invents; a scoring-gate decision is not a phrasing task).

**Edge cases**
- **The threshold is a number, and numbers that gate scoring are expert-owned (Hard Rule 3).** Ship the detector with the threshold read from `platform_setting`, default to flag-only (no blocking) and open an OD for the blocking threshold. Do not hardcode a cutoff — that is precisely how OD-23 happened.
- Corporate families legitimately name several entities in one notice ("Acme Inc. and its subsidiaries"). The scan must key on self-reference position, not name frequency.
- A false positive blocks a paying customer's legitimate assessment. Default to flagging for review, never silent rejection.

---

## P3.2 — Crawler egress separation

**Goal.** Route crawler traffic through egress that is not the application's IP, so a WAF block on scanning does not take the API down with it.

**Why here.** Independent, and the risk grows with success rather than with feature count.

**Context.** The open-web crawler is `app/services/ingestion/connectors/openweb.py`. It is rate-polite (robots.txt, per-domain delay, honest User-Agent) and only crawls DB-seeded `crawl_target` rows — OD-22's 22 SaaS domains were never approved, never seeded, never crawled. There is **no proxy or separate-egress configuration anywhere** in `app/` or `deploy/`. Tailscale appears in `deploy/` only for RunPod LLM inference traffic, not crawling.

**Files to modify**
- `app/config.py` — add `crawler_proxy_url: str = Field(default="")` in the existing style.
- `app/services/ingestion/connectors/openweb.py` — route its HTTP client through the proxy when configured. **The proxy must not bypass SSRF validation:** `ssrf.resolve_and_validate` resolves a host once and connects to the pinned IP (AGENTS.md §3, second pass). A proxy re-resolves by design, which is exactly where that guarantee is lost. Validate before handing the URL to the proxy, and reject any proxy configuration that cannot be given a pinned address.
- `.env.example` — add `CRAWLER_PROXY_URL=` with a dummy value.
- `deploy/` — document the egress topology.

**Env vars.** `CRAWLER_PROXY_URL`. Empty = direct (current behaviour).

**Acceptance criteria**
- With the var unset, crawling behaves exactly as today.
- With it set, crawl requests exit via the proxy and API requests do not.
- SSRF protections still reject private/link-local/loopback and the cloud metadata address *through the proxy path*. Test this explicitly — it is the whole risk of the change.
- Robots.txt compliance and per-domain delay are unchanged.

**Edge cases**
- **This is a security-sensitive change.** A proxy that resolves DNS itself reintroduces SSRF. If the proxy cannot accept a pinned IP, this design does not work and the alternative is a separate worker with its own egress, not a proxy.
- Egress IP rotation interacts with robots.txt politeness — rotating to evade rate limits would break the honest-crawler posture the connectors currently maintain. Rotate for resilience, never for evasion.
- Cost and latency: every crawl now has an extra hop.

---

## P4.1 — Generate `report.css` from `theme.css`

**Goal.** Make the PDF stylesheet a generated artifact so screen and print colours cannot drift.

**Why here.** It is already in `remaining-work.md` §1 as unblocked, and P4.2 depends on it.

**Context.** `app/services/report/report.css` (358 lines) is hand-maintained. `app/services/report/renderer.py:69` holds `_RAMP` with four hand-written hexes (`low #2E9E6B`, `moderate #E9A23B`, `high #D9534F`, `elevated #C0392B`) and `_ramp_key()` at line 298 bands at **25/50/75**, while `web/src/lib/scoreBands.ts` bands at **45/70** using `var(--standing-*)` tokens. WeasyPrint does not parse `oklch()` and Tailwind does not reach it, so the second stylesheet is permanent (owner-confirmed).

**Scope limit — read carefully.** This prompt covers the **palette** only. The 25/50/75-vs-45/70 threshold mismatch is the expert-owned half of OD-17 (Hard Rule 3: bands come only from `intelligence-logic.md`). **Do not change `_ramp_key`'s cut-points.** Convert the colours; leave the numbers exactly as they are and note the remaining divergence in the generator's output header.

**Files to create**
- `scripts/build_report_css.py` **NEW** — parses `web/src/theme.css`, converts each `oklch()` value to sRGB hex, writes `app/services/report/report.css` with a `/* GENERATED … do not edit */` header and the source token name in a comment beside each value.

**Files to modify**
- `app/services/report/renderer.py` — replace the literal `_RAMP` dict at line 69 with values read from the generated stylesheet (or a small generated Python constants module the same script emits).
- `Makefile` — add a target invoking the generator.
- Add the generator to the `guards` job from P0.2 as a **drift check**: regenerate and fail if the working tree differs.

**Dependencies.** A colour-space conversion. `coloraide` handles oklch→sRGB correctly; if you prefer no new dependency, implement the OKLab→linear sRGB→sRGB transform directly and unit-test it against three known values from `theme.css`.

**Acceptance criteria**
- Running the generator twice produces no diff.
- Every colour in `report.css` traces to a `theme.css` token named in a comment.
- Editing a token in `theme.css` and regenerating changes `report.css`.
- CI fails if `report.css` is edited by hand.
- **A rendered PDF is visually unchanged where the tokens already agreed**, and every place it changes is a place they had drifted — enumerate those in the PR.
- `_ramp_key` cut-points are byte-identical to before.

**Edge cases**
- oklch→sRGB can produce out-of-gamut values. Clamp and log any token that clamps; do not silently shift a colour.
- `tests/test_pdf_determinism.py` fails 5-6 runs in 10 on the unmodified tree (OD-18, a font-subsetter defect). **Judge this change on ten runs against a ten-run baseline**, never on one, or you will attribute a pre-existing flake to your change.

---

## P4.2 — Adopt the PDF design comp

**Goal.** Bring the rendered PDF to the owner's design comp for the sections that are not blocked.

**Why here.** Last, because it depends on P4.1's generated palette, and because five of its elements are blocked on decisions.

**Context.** The full amendment is in `F05-amendment-2026-09-03-pdf-visual-direction.md` (delivered separately) — **read it first**. `app/services/report/renderer.py` (1400 lines) builds the HTML; `_render_disclosure()` at line 564 already emits the closing Disclosure block, and its docstring at 568 describes the scope-statement-front / single-Disclosure-end pattern.

**Buildable now (comp §1):** cover treatment, three-card executive strip, six-card dashboard with gauges, risk-dimension bars, regulator cards + heatmap, findings table, side-by-side language comparison, severity-tiered guidance, source traceability table, closing page, per-page footer.

**Not buildable — do not attempt:** the "1,250+ organizations" strings (Hard Rule 7 — render live cohort n or suppress), "Below Industry Average" and every peer-position comparative (OD-14), the finding codes `DSP-003` and `CRR-005` (Hard Rule 3 — the governed prefixes are `SH` and `CR`; `AI-004` and `TRK-007` are valid), the three-series trend chart (OD-20), teal as a "Low Risk" swatch (OD-13 removed teal from the standing scale).

**Files to modify**
- `app/services/report/renderer.py` — the section render functions and `_DASHBOARD_METRICS` (line 89).
- `app/services/report/report.css` — **via the P4.1 generator only**, never by hand.
- `tests/test_report_design.py` — extend for the new structure.

**Acceptance criteria**
- Section render order is a presentation mapping; stored block ids and `section-N` anchors are unchanged, and a snapshot frozen before this change regenerates with identical content (Hard Rule 6).
- No fixed corpus-scale figure appears anywhere in the output.
- Every rendered finding code resolves to a `finding_type` row; an unresolvable code fails the build.
- The scope statement renders at the front and the single Disclosure at the close.
- No comparative peer-position word renders while OD-14 is open.

**Edge cases**
- Renumbering sections in the comp (Trend moves 12→8, Next Steps added as 12) must not touch stored ids — legacy snapshots would stop regenerating.
- The comp's "Last 12 Months" trend has no data source (assessment history has no endpoint). Render an explicit baseline state, never an interpolated or empty chart.
- The comp's marketing panel will appear in white-label renders unless F20 branding suppresses it. Confirm before shipping.

---

# PART 4 — Verification sequence

After each wave:
```bash
pytest -q                     # note conftest.py auto-skips 15 modules without a live Supabase
cd web && npx tsc --noEmit && npx vitest run
make guards                   # after P0.2
```

**Before claiming a green run:** `conftest.py` skips by TCP probe to the Supabase host on port 443 with a 3-second timeout. A transient network failure silently converts fifteen modules — including `test_rls_enabled` — to skips, and the run still reports green. Print the skip count and treat a non-zero count on a local pre-merge run as a failed gate.

---

# PART 5 — What cannot be prompted, and what closes it

| Item | Blocked by | What closes it |
|---|---|---|
| Peer-position words on any surface | **OD-14** | Expert confirms the vocabulary *and* the percentile cut-points for each word |
| Any customer-facing "must" | **OD-16** | Decide where obligation modality lives (column at ingest / per-requirement_type default / SME-labelled) and who owns it |
| Categorical chart colour | **OD-20** | Adopt a validated categorical palette, or forbid categorical encoding and require faceting |
| PDF band cut-points | **OD-17** (threshold half) | Expert rules on 25/50/75 vs 45/70. Hard Rule 3 |
| The 12-word `list_fragment` bound | **OD-23** | Expert confirms, replaces, or restates it as deliberate. It is live and unconfirmed today |
| Presence-count saturation | **OD-21** | Expert calibration |
| Byte-identity claim | **OD-18** | Pick one of (a) pin the subsetter, (b) embed fonts unsubsetted, (c) canonicalize post-render, (d) narrow the printed claim to content-identity |
| **F23 third-party assessment** | **OD-22 policy + dispute path** | OD-22 currently asks you to approve a *named list* of 22 crawl domains. If any customer can submit any company's URL, an allowlist cannot hold and the model must become a policy. Separately, scoring a non-customer for a customer is the published-score posture, and the dispute/appeal path stops being optional |

---

# PART 6 — Questions I need answered before P1.1 and P2.1 start

1. **P1.1 target table** — `profiles` (recommended: collapses two auth paths into one store) or promote the dead `local_users` table? Everything downstream references this choice.
2. **OD-28** — does a scheduled re-assessment consume a report from the allowance? P2.3 cannot start without it.
3. **OD-27** — does a failed extraction cost the customer a report? P2.1 ships a `pending_policy` placeholder without it.
4. **OD-24** — the Standard tier's seat limit, and the values for tiers above it. You gave 5 reports/month verbally; the rest is unstated. No `plan` row is seeded until this is confirmed in writing.
5. **P1.2 failure mode** — I have specified fail-open on a Redis outage for abuse throttles. Confirm, because fail-closed on a cache outage would take the API down.
