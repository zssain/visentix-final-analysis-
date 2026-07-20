# Change Report — F02 Ingestion Foundation (migrations, seed, tests)

**Branch:** `F02-ingestion-foundation` (off `feedback/ingestion-arch-schema-v1.3`) · **Date:** 2026-07-21 · **Author:** engineer (AI-assisted) · **Merge:** NOT merged (as instructed)

> **UPDATE 2026-07-21 (second pass) — APPLIED TO LIVE.** A DDL-capable IPv4 session pooler (`DATABASE_POOLER_URL`) was added to `.env`, so the apply that was blocked in the first pass has now run end-to-end. This report is updated throughout; the original "blocked" narrative is preserved in §1 for the record. Live-apply results: **§0**.

---

## 0. Live apply results (2026-07-21, via IPv4 session pooler)

- **All four migrations applied** in order (0020 → 0017 → 0014 → 0021) in a single transaction; **24 `schema_migrations` rows recorded** (20 backfilled historical + 4 applied-now), `applied_at = 2026-07-20 22:15:47Z`.
- **Seed:** `source_registry` seeded with 7 families (only `hhs_ocr` enabled).
- **`tests/test_f02_ingestion_foundation.py`: 16 passed, 0 skipped** (the 9 live tests now execute for real: checksum-match, RLS-denies-anon ×5, 0017 present+writable, alias-uniqueness, seed-idempotent).
- **`local_users` ambiguity RESOLVED (read-only):** the table **does not exist** in the database — `to_regclass('public.local_users')` is NULL. Migration 0011_local_users was **never applied** (the REST 404 was genuine absence, not revoked grants). Local JWT auth runs off `local_users.json`. Correctly excluded from backfill.
- **`.env` fix (no secret shown):** the pooler password had **stray surrounding `[ ]` brackets** — the Supabase dashboard `:[YOUR-PASSWORD]@` placeholder was filled in but the literal brackets were kept, which broke both `urlparse` and libpq. Stripped programmatically (the value never appeared in any output). **Action for the human:** confirm `.env` is correct going forward.

## TL;DR

**Applied to live and verified: 4 migrations, 24 ledger rows, 7 seed rows, 16/16 F02 tests green.** The connection uses the IPv4 session pooler; the runner parses the URL by hand and passes psycopg keyword args (the pooler password contains URL-hostile characters). Not a permission problem in the first pass — a network one (direct host is IPv6-only, no route here); resolved by the pooler. Details §1.

---

## 1. Live reachability (introspection method + the blocker)

Per the task, **PostgREST OpenAPI reflection** (`GET /rest/v1/` with the service-role key) was used for all live introspection — noted here as instructed. It is read-only and cannot execute DDL.

For **applying** DDL, all four possible paths were tested and all failed:

| Path | Result |
|---|---|
| Direct Postgres (`DATABASE_URL`, `db.<ref>.supabase.co:5432`) | Host is **IPv6-only** (AAAA records only); this machine has **no IPv6 route** (`connect → OSError 65 No route to host`; `getaddrinfo → Errno 8`). |
| IPv4 pooler (`aws-0-<region>.pooler.supabase.com`) | No pooler URL in `.env`, and no region to construct one. Not attempted (guessing regions = sending the DB password to unknown hosts; a workaround AGENTS.md §3 warns against). |
| PostgREST SQL-exec RPC | Only RPC exposed is `get_my_role`. `exec_sql`/`execute_sql`/`exec`/`sql`/`query`/`run_sql` all 404. |
| Supabase Management API (`/v1/projects/{ref}/database/query`) | Rejects the service-role key (`401 JWT could not be decoded`) — needs a personal access token, which is not in `.env`. |

**Conclusion:** DDL cannot be issued from here. The apply must run from an IPv6-capable host (or via a pooler/PAT), or the SQL files must be pasted into the Supabase SQL editor. The runner then records the ledger.

## 2. Pre-apply live state (PostgREST reflection, 2026-07-20/21)

Confirms the audit exactly — every target object is absent:

- `source_registry`, `parser_version`, `security_event`, `organization_alias`, `schema_migrations` → **ABSENT**.
- `ingestion_run` → **PRESENT** in its 0011c shape (`run_id, source_name, run_type, started_at, finished_at, rows_inserted, rows_updated, status, notes`) — no `registry_id/outcome/records_*` yet.
- `report_snapshot` 0017 columns (`rendered_report, content_hash, report_version, glossary_version, template_version`) → **ABSENT** (only `scoring_model_version` present).
- `organization` 0014 columns + `organization_intelligence_profile` `*_tier` columns → **ABSENT**.

## 3. What was authored (all additive)

| File | Purpose |
|---|---|
| `db/migrations/0020_schema_migrations.sql` | STEP A — `schema_migrations(filename PK, checksum, applied_at)`; RLS + REVOKE (internal). |
| `db/migrations/0021_ingestion_tables.sql` | STEP C — `source_registry`, `parser_version`, `security_event`, `organization_alias` (new) + additive columns on `ingestion_run`; FK indexes; `UNIQUE(alias_type,value)`; `UNIQUE(family)`; RLS + REVOKE on all five (service-role only). |
| `db/migrations/0017_*.sql`, `0014_*.sql` | STEP B — pre-existing authored-but-unapplied files, applied unchanged (both already `ADD COLUMN IF NOT EXISTS`). **0014 columns are created but NOT populated** — existing rows keep their live text `industry`. |
| `scripts/db/apply_and_record.py` | Runner: STEP A create + backfill historical, STEP B/C apply + record, in exact order. Idempotent. `--plan` prints checksums with no DB. |
| `scripts/db/seed_source_registry.py` | STEP D — idempotent upsert-on-`family` seed (7 families). |
| `.env.example` | Added `EDGAR_BULK_PATH` (dummy) + the 3 pre-existing ingest keys that were missing. |
| `tests/test_f02_ingestion_foundation.py` | 7 local + 9 live tests. |

**FK typing surprise (verified live):** `source_record.source_id` is **TEXT** (not UUID) and `organization.organization_id` is **UUID** — so `security_event`/`organization_alias` FKs are TEXT to source_record and UUID to organization. Getting this wrong would have failed the DDL.

**Sequence numbers:** used unique `0020`/`0021` per the new §5.2 rule; introduced no new duplicates.

## 4. Apply instructions (for a reachable host)

From an IPv6-capable host (or with a pooler URL / PAT in `.env`):
```
python scripts/db/apply_and_record.py     # applies 0020 → backfill → 0017 → 0014 → 0021, records each
PYTHONPATH=. python scripts/db/seed_source_registry.py   # seeds 7 families
./.venv/bin/pytest tests/test_f02_ingestion_foundation.py -v   # 16 pass, 0 skip
```
Or paste (Supabase SQL editor), in order: `0020`, `0017`, `0014`, `0021`; then run `apply_and_record.py` to write the ledger and `seed_source_registry.py` to seed.

**Idempotent:** every DDL is `IF NOT EXISTS`; every ledger row is `ON CONFLICT DO NOTHING`; the seed upserts on `family`. Re-running changes nothing.

## 5. Intended `schema_migrations` contents (24 rows)

20 historical (backfill, SQL already applied) + 4 applied-now. `0011_local_users.sql` and the three `APPLY_*.sql` bundles are **not** tracked.

```
<checksum[:16]>  how                     filename
e08f38295dd95dc5  backfill                0001_phase1_new_tables.sql
d0df1a6ac1964751  backfill                0002_phase1_alter_existing.sql
95693d8a7112264a  backfill                0003_phase1_seed_stubs.sql
40b89b69fe05967d  backfill                0004_phase2_profiles_rls.sql
9a8be3990fd73d86  backfill                0005_phase2_rls_fix.sql
7ccb2f58f42edb88  backfill                0006_phase2_rls_fix_recursion.sql
7fc7a7690209a804  backfill                0007_phase3_vector_indexes.sql
6a1b506c4059722c  backfill                0008_phase7_training_label.sql
4cd12759d9119bbc  backfill                0009_obligation_embedding.sql
91ab53f43c389204  backfill                0010_category_v2.sql
d90a6a4a126a17bf  backfill                0011_live_assessment_isolation.sql
cd6a65d26ac00ad4  backfill                0011_reference_corpus.sql
3a50757466f27756  backfill                0012_finding_content.sql
5c32993db48c0205  backfill                0012_versioning_metadata.sql
418402baf1e3d497  backfill                0013_clause_taxonomy_v2.sql
536259d05696f5d1  backfill                0013_enforcement_extra_cols.sql
b1a35bc89c30f589  backfill                0015_explainability_reference.sql
a5fa759fcc91f7c3  backfill                0016_legal_reference.sql
ae70ac6a54100f0a  backfill                0018_intake_columns.sql
284f858da40a4c1b  backfill                0019_versioning_columns.sql
583eacbc57d454a5  applied-now (STEP A)    0020_schema_migrations.sql
9e21cd6bc17b9a5e  applied-now (STEP B)    0017_snapshot_rendered_report.sql
11295587558f856c  applied-now (STEP B)    0014_org_profile_fields.sql
26f9adacc7669328  applied-now (STEP C)    0021_ingestion_tables.sql
```
(Full 64-char checksums live in `scripts/db/apply_and_record.py --plan`.)

## 6. `local_users` ambiguity — RESOLVED (never applied)

With direct catalog access via the pooler, this is now settled: **`to_regclass('public.local_users')` returns NULL — the table does not exist in the database.** Migration 0011_local_users was **never applied**; the earlier REST `404 PGRST205` was genuine absence, not API-revoked grants. Local JWT auth runs off `local_users.json` (as the audit suspected). It remains correctly **excluded from the `schema_migrations` backfill** and earns a row only if it is ever actually applied.

## 7. Tests (after live apply)

- **`tests/test_f02_ingestion_foundation.py`: 16 passed, 0 skipped, 0 failed.** All 9 live tests now execute for real.
- **Full suite: 624 passed, 25 failed, 0 skipped** (was 617 / 23 / 9 pre-apply). The delta reconciles exactly: **+9** (my live tests now pass instead of skip), **−2** (two profile-count tests flipped to failing, see below). **No hidden regressions** — every other test is byte-for-byte the same result.

### 7a. Did the 0014/0017 apply resolve any of the 23 pre-existing drift failures?

**Zero of 23 resolved.** 0014/0017 add *columns*, not *data* — none of the 23 was a missing-column failure. All 23 still fail, by cause:

| # | Cause family | Failing tests | Why 0014/0017 can't fix it |
|---|---|---|---|
| 6 | **Stale hardcoded row-counts** (audit-flagged) | `test_schema_p1::test_preexisting_row_counts[organization-30 / privacy_notice-26 / notice_section-767 / disclosure_clause-3655 / obligation-154 / enforcement_record-172]` | Corpus grew (live: 37 / 50 / 1564 / 6145 / 273 / 649). Fix = update the tests, not the schema. |
| 2 | **Stale stub-content assertions** | `test_schema_p1::test_finding_type_stubs`, `::test_recommendation_library_stubs` | `update_findings.py` replaced the STUB text with real content; tests still assert "STUB". |
| 1 | **Corpus completeness** (audit-flagged) | `test_embeddings::test_disclosure_clause_no_null_embeddings` | 2,490 clauses have NULL embedding (embedder is a stub). Needs a backfill, not a migration. |
| 14 | **App route / state behavior** (not schema) | `test_auth::test_admin_can_access_all_routes`; `test_explain` ×3; `test_export` ×6 (404s); `test_live_classify::test_classification_log_message_safe`; `test_exemplar_review::…section8…`; `test_report_assembly::…section8…`; `test_review_gate::…draft_banner…` | Live app/route/state failures unrelated to the ingestion schema. |

### 7b. Two NEW failures the apply *surfaced* (net 23 → 25)

`test_schema_p1::test_oip_populated` and `test_profile::test_profiles_exist_in_db` both hardcode `organization_intelligence_profile == 30`; it is now **31**. **This is the 0014 apply fixing a latent bug, not breaking one.** The profiling write path `_ensure_org_profile` ([app/services/live_scoring.py:329-353](../../app/services/live_scoring.py#L329-L353)) POSTs a profile including the 0014 columns (`industry_id`, `sub_industry`, `*_tier`) **with no error check**. Before 0014 those columns didn't exist, so PostgREST **400'd the insert and it was silently swallowed** — profiles never persisted (count frozen at 30). After 0014 the insert **succeeds**, so a live pipeline test (`test_live_pipeline`, running the real pipeline on the pre-existing "Anonymous Assessment" org) persisted the 31st profile at 22:17:42Z. Same stale-hardcoded-count family as the six row-count failures above.

**Net:** 0014/0017 resolved 0 of the 23 (they were never schema-shaped), and exposed 1 real latent bug (profile persistence was failing pre-0014) whose fix tripped 2 more hardcoded-count tests. Recommended follow-ups: (a) retire/parametrize the hardcoded live-count + stub-content assertions in `test_schema_p1` / `test_profile` (they will keep drifting); (b) add an error check to `_ensure_org_profile`'s POST so a failed profile write is never silent again; (c) the live-pipeline tests write to the shared DB — worth isolating.

## 8. Surprises

1. **First pass: live DB unreachable for DDL** — direct host is IPv6-only, no route here. Resolved in the second pass by the IPv4 session pooler.
2. **The pooler password broke URL parsing** — it contains URL-hostile characters *and* had stray `[ ]` brackets from the dashboard placeholder. Fix: parse the URL by hand → psycopg kwargs, and strip the brackets in `.env` (no secret printed).
3. **`source_record.source_id` is TEXT, not UUID** — drove the FK column types in `0021`.
4. **Applying 0014 exposed a silently-failing write path** — `_ensure_org_profile` POSTs the 0014 columns with no error check, so pre-0014 every profile insert 400'd and was swallowed (profiles weren't persisting). Post-0014 it works — a genuine bug fix that also tripped two hardcoded `==30` count tests (§7b).
5. **`local_users` never existed** — settled via direct catalog access; not an API-grant quirk.
6. **The full suite was already red** (23 live-drift failures) before this work, now 25 — all stale-count / stale-stub / app-state, none from the ingestion schema.

## Needs human
- **Confirm `.env` pooler URL** — I stripped the stray `[ ]` around the password so the apply could run; verify the stored value is correct (I never printed it).
- **Confirm the seed's operational config values** (`reliability_tier`, `cadence`, `base_url`s) — grounded in VICBNF §3.2 tiering + business-logic §7 cadences, but review-and-confirm.
- **Fix `_ensure_org_profile`** ([live_scoring.py:349-353](../../app/services/live_scoring.py#L349-L353)) to check the POST status — a failed profile write must not be silent (this is why profiles weren't persisting before 0014).
- **Retire/parametrize the stale live-count + stub assertions** in `test_schema_p1` / `test_profile` — they hardcode 2026-06 inventory (30 orgs, 26 notices, "STUB" content) and will keep drifting; the ingestion apply did not cause them and cannot fix them.
