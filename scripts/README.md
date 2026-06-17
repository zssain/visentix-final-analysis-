# Scripts

## embed_backfill.py — Embedding Backfill

Backfills NULL embeddings in `disclosure_clause` and `enforcement_record` using
`sentence-transformers/all-MiniLM-L6-v2` (384-dim vectors).

### Prerequisites

- `.env` with valid `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY`
- Python venv activated: `source .venv/bin/activate`

### Commands

```bash
# Dry-run: embed 10 rows per table, print dims, no writes
python scripts/embed_backfill.py --dry-run

# Full backfill (both tables)
python scripts/embed_backfill.py

# Single table
python scripts/embed_backfill.py --table disclosure_clause
python scripts/embed_backfill.py --table enforcement_record

# Custom batch size
python scripts/embed_backfill.py --batch-size 128
```

### Behavior

- **Resumable:** Only processes rows where `embedding IS NULL`. Safe to re-run
  after interruption — picks up where it left off.
- **Idempotent:** Re-running when all embeddings are populated results in 0 updates.
- **Safe:** Only updates the `embedding` column by primary key. No other columns
  are touched.
- **Retry:** Automatically retries on network timeouts (3 attempts with exponential
  backoff).

### Post-backfill

After the backfill completes, apply the vector index migration:

```sql
-- Run in Supabase Dashboard SQL Editor:
-- db/migrations/0007_phase3_vector_indexes.sql
```

This creates ivfflat cosine indexes on both embedding columns and runs ANALYZE.
