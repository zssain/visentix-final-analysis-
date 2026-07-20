# Change Report — F02 Ingestion Foundation (migrations, seed, tests)

**Branch:** `F02-ingestion-foundation` (off `feedback/ingestion-arch-schema-v1.3`) · **Date:** 2026-07-21 · **Author:** engineer (AI-assisted) · **Merge:** NOT merged (as instructed)

---

## TL;DR — what was applied to live, and when

**Nothing was applied to the live database, because the live database is not reachable for DDL from this environment.** Every migration file, the apply/record runner, the seed script, `.env.example`, and the test suite are written and verified locally; they are staged to apply in one shot the moment a working connection exists. See **§4 Apply instructions**.

This is not a permission problem (the apply is authorized) — it is a network-reachability problem. Details in §1.

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

## 6. `local_users` ambiguity (unresolved, as instructed)

`0011_local_users.sql` is deliberately **not** backfilled. Via REST it is `404 PGRST205` (not in the API schema) — which is consistent with *either* "never applied" *or* "applied then API-revoked" (a password table should be hidden from the API). Direct-DB confirmation is impossible from here (§1). Left for a follow-up; it earns a ledger row only if/when genuinely applied.

## 7. Tests

- **`tests/test_f02_ingestion_foundation.py`: 7 passed, 9 skipped, 0 failed.** The 7 local tests assert real invariants now (idempotent-by-construction; manifest partitions every file; checksum = raw file sha256; STEP order; seed-row shape incl. family↔folder mapping + hhs_ocr-only-enabled + EDGAR_BULK_PATH + cppa archive note). The 9 live tests (checksum-match, RLS-denies-anon ×5, 0017-writable, alias-uniqueness, seed-idempotent) **skip with an explicit "not applied to live yet" reason** and become hard assertions the instant the migrations land.
- **Full suite: 617 passed, 23 failed, 9 skipped.** The 23 failures are **pre-existing live-DB-drift**, not introduced here (0 failures come from any file in this change) — they are the exact set the audit documented: `test_schema_p1` stale inventory counts (`organization-30`→live 37, `disclosure_clause-3655`→live 6145, etc.), `test_embeddings` NULL-embedding (live has 2,490 NULL), `test_schema_p1` finding-type "STUB" markers (replaced by `update_findings.py`), and assorted live/state-dependent auth/explain/export/review-gate tests. "Full suite green" is not achievable in this environment independent of this work; my additions are green.

## 8. Surprises

1. **Live DB is genuinely unreachable for DDL** — only PostgREST (read/REST) works; the direct host is IPv6-only with no route here. This is the headline: STEP B/C/D "apply to live" could not execute.
2. **`source_record.source_id` is TEXT, not UUID** — drove the FK column types in `0021`.
3. **Existence checks are insufficient guards** — `ingestion_run` and `report_snapshot` pre-exist, so live tests key on the *new* artifact (`source_registry` presence for 0021; `report_snapshot.report_version` for 0017), not bare table existence.
4. **The full suite was already red** (23 live-drift failures) before this work — worth its own cleanup pass (retire/parametrize the hardcoded inventory counts).

## Needs human
- A reachable apply path: run `apply_and_record.py` + `seed_source_registry.py` from an IPv6-capable host (or add a pooler URL / PAT to `.env`), OR paste `0020/0017/0014/0021` into the Supabase SQL editor then run the runner to record. After that, `tests/test_f02_ingestion_foundation.py` should be 16/16 green.
- Confirm the seed's operational config values (`reliability_tier`, `cadence`, `base_url`s) — grounded in VICBNF §3.2 tiering + business-logic §7 cadences, but review-and-confirm.
- The `local_users` status still needs a direct-DB check (§6).
