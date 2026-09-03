# Self-hosted Supabase for Visentix (on the Azure VM)

Move off Supabase Cloud (free-tier DB cap = 0.5 GB; your DB is ~1.3 GB) onto the
Azure VM you already run. No size cap, no Supabase bill, keep all your data.

**What runs:** Postgres (pgvector) · Kong · GoTrue (Auth) · PostgREST · Storage.
**Topology:** internal-only. The app container reaches the gateway at
`http://kong:8000` over a shared `visentix` Docker network. Nothing is exposed to
the public internet — the browser never calls Supabase directly (`web/src` uses no
supabase-js; login is server-side), so there's no public HTTPS/CORS to configure.

**Why this is compatible:** the app talks to its DB only through PostgREST
(`{SUPABASE_URL}/rest/v1/*`) and logs in through GoTrue (`/auth/v1/token`), and its
JWT verifier already falls back to **HS256 with the shared `SUPABASE_JWT_SECRET`**
(`app/auth.py`) — exactly how self-hosted Supabase signs tokens.

> ⚠️ These image tags mirror the official `supabase/docker` as of 2026-09. If any
> image fails to pull, copy the current tag from
> <https://github.com/supabase/supabase/blob/master/docker/docker-compose.yml> into
> `.env` — the wiring is the same.

---

## Gotchas hit in a real run (2026-09-04) — read these

1. **Match the Postgres major version to Cloud.** Cloud was PG17.6; a PG15 self-host
   made `pg_dump` refuse ("server version mismatch") and PG17→PG15 restore is unsafe.
   `.env` `POSTGRES_IMAGE` is pinned to `supabase/postgres:17.6.1.168`. Check yours
   with `SELECT version();` on Cloud and match the major version.
2. **Export via the POOLER, not the direct host.** `db.<ref>.supabase.co` is
   **IPv6-only**; a Docker container can't reach it ("Network is unreachable"). Use
   the **session pooler** (`aws-<region>.pooler.supabase.com:5432`, user
   `postgres.<ref>`) — it's IPv4 and supports `pg_dump` (the 6543 transaction pooler
   does not).
3. **Set the internal role passwords after the first boot.** `supabase/postgres`
   creates `authenticator` / `supabase_auth_admin` / `supabase_storage_admin` but
   does **not** set their passwords to `POSTGRES_PASSWORD`, so rest/auth/storage
   crash-loop with "password authentication failed". Fix once per fresh db volume
   with `scripts/fix-role-passwords.sh` (must run as `supabase_admin`, the true
   superuser — `postgres` is not).
4. **Restore from a file inside the container, not a pipe.** Custom-format archives
   don't restore reliably from a non-seekable pipe — `docker cp` the dump into the
   db container and `pg_restore` the file.
5. **Disk.** The stack images (~5 GB) + the DB volume + pgvector indexes on hundreds
   of thousands of embeddings are large. On a 29 GB VM this runs at ~90% — plan to
   resize the disk as the corpus grows.

## Prerequisites

- SSH access to the VM (`visentix-api.westeurope.cloudapp.azure.com`).
- Docker + Docker Compose v2 on the VM (the app already uses it).
- `postgresql-client` v15+ on the VM and on whatever machine runs the export
  (`pg_dump`, `pg_restore`, `psql`).
- ~4 GB free disk on the VM (1.3 GB data + dump + working room).

---

## Step 1 — Export your data from Cloud (read-only, safe while restricted)

Get the **direct** connection string: Supabase dashboard → Project → Settings →
Database → Connection string → **URI** (port **5432**, not the 6543 pooler).

```bash
cd deploy/selfhost-supabase/scripts
export CLOUD_DB_URL='postgresql://postgres:PASSWORD@db.jhzkyfitrdxmzyyvqfak.supabase.co:5432/postgres'
./export-from-cloud.sh            # -> visentix_public.dump  (a few hundred MB, compressed)
```

`pg_dump` is read-only, so this works even though the project returns 402 to writes.
Copy `visentix_public.dump` to the VM (`scp`, or run the export on the VM directly).

## Step 2 — Configure the stack (on the VM)

```bash
cd deploy/selfhost-supabase

# Shared network so the app container can reach kong:8000
docker network create visentix   # ignore "already exists"

# Generate secrets + keys, then paste the four values into .env
python3 scripts/gen-keys.py
cp .env.example .env
# edit .env: set POSTGRES_PASSWORD, JWT_SECRET, ANON_KEY, SERVICE_ROLE_KEY
```

Keep the `gen-keys.py` output — you'll paste the **same** ANON/SERVICE/JWT values
into the app's `.env` in Step 6.

## Step 3 — Bring up the stack

```bash
docker compose --env-file .env up -d
docker compose ps                 # wait until db is healthy, all Up
docker compose logs -f auth       # GoTrue should log "migrations applied" then serve
```

GoTrue and Storage auto-create their own `auth.*` / `storage.*` schemas on first
boot. `supabase/postgres` already provides the roles (`anon`, `authenticated`,
`service_role`, `authenticator`, …) and makes pgvector available.

## Step 4 — Import your data

```bash
cd scripts
export POSTGRES_PASSWORD='<same POSTGRES_PASSWORD as .env>'
./import-to-selfhost.sh visentix_public.dump
```

It restores the `public` schema, ensures pgvector, and prints row counts — check
they match Cloud. Grant-to-missing-role warnings in `restore.log` are harmless.

## Step 5 — Re-provision the login users

Auth users live in the `auth` schema, which GoTrue owns. Rather than migrate that
schema, recreate the users through GoTrue's admin API — their roles/orgs already
came across in the `profiles` table (public). Use the existing script, pointed at
the self-host:

```bash
cd /path/to/visentix          # repo root on the VM
export SUPABASE_URL=http://127.0.0.1:8000
export SUPABASE_SERVICE_ROLE_KEY='<SERVICE_ROLE_KEY from gen-keys>'
./.venv/bin/python scripts/db/provision_demo_users.py --email admin@visentix.com
./.venv/bin/python scripts/db/provision_demo_users.py --email sme@visentix.com
./.venv/bin/python scripts/db/provision_demo_users.py --email customer@visentix.com
# …one per approved email. Enter the shared password at the prompt.
```

> If a re-provisioned user's new auth id doesn't match its `profiles.user_id`,
> update the profile row's `user_id` to the new auth id (the script prints it), or
> re-link by email. `profiles.role`/`organization_id` are unchanged.

## Step 6 — Point the app at the self-host and redeploy

Edit the app's `.env` **on the VM** (`deploy/azure/.env`) — replace the Cloud
Supabase values with the self-host ones (from `gen-keys.py`):

```
SUPABASE_URL=http://kong:8000
SUPABASE_ANON_KEY=<ANON_KEY>
SUPABASE_SERVICE_ROLE_KEY=<SERVICE_ROLE_KEY>
SUPABASE_JWT_SECRET=<JWT_SECRET>
```

Put the app on the same network. In `deploy/azure/docker-compose.yml`, add to the
`api` service:

```yaml
    networks: [default, visentix]
# and at the file's top level:
networks:
  visentix:
    external: true
```

Apply the outstanding migrations against the now-writable DB, then redeploy:

```bash
./.venv/bin/python scripts/db/apply_and_record.py     # applies 0053 etc.
./deploy/azure/deploy.sh v1.0.6-pilot
```

Frontend needs **no change** — it only talks to the app API. (`web/.env.production`
already points at `https://visentix-api.westeurope.cloudapp.azure.com`.)

## Step 7 — (Optional, phase 2) Migrate the raw-artifacts files (~1 GB)

The Storage bucket holds captured source files, referenced by path for lineage.
Core scoring/reports work without them. To bring them over later, download from
Cloud Storage (dashboard → Storage, or the `s3`-compatible endpoint / `rclone`) and
drop them under the `storage-data` volume, or re-upload via the Storage API. Not
required to go live.

## Step 8 — Verify end-to-end

```bash
# Gateway up:
curl -s -H "apikey: $ANON_KEY" http://127.0.0.1:8000/rest/v1/organization?select=name\&limit=1
# App healthy against self-host:
curl -s https://visentix-api.westeurope.cloudapp.azure.com/health
# Login works (server-side via GoTrue), then open the Worker frontend and load a report.
```

Then re-run the live gate from the repo (DB is writable now):
```bash
./.venv/bin/pytest -q    # the 402 failures should clear; print the skip count
```

---

## Operations

- **Backups:** `docker exec <db> pg_dump -U postgres postgres | gzip > backup_$(date +%F).sql.gz`
  on a cron (you already have `deploy/azure/backup.sh` — point it at the container).
- **Disk:** watch the `db-data` and `storage-data` volumes; the corpus grows as you crawl.
- **Upgrades:** bump the image tags in `.env` together, `docker compose up -d`.

## Troubleshooting

- **`type "vector" does not exist` during import** → `psql … -c 'CREATE EXTENSION vector;'`
  (or `SCHEMA extensions`) and re-run `import-to-selfhost.sh` (idempotent).
- **PostgREST "permission denied for table"** → the dump's GRANTs didn't restore; run
  `GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA public TO anon, authenticated, service_role;`
- **App gets 401 from `/rest/v1`** → `SUPABASE_SERVICE_ROLE_KEY` in the app `.env`
  doesn't match this stack's `SERVICE_ROLE_KEY`. They must be the same JWT.
- **Login 500 / token invalid** → `SUPABASE_JWT_SECRET` (app) must equal `JWT_SECRET`
  (stack). GoTrue signs HS256 with it; the app verifies HS256 with it.
- **An image tag won't pull** → copy the current tag from the official
  `supabase/docker` compose into `.env`.
