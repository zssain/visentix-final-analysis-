# Reclassify Plan — Corpus "other" Clauses (Part B)

**Status: AWAITING APPROVAL — do not run until explicitly approved.**

## Problem

2,391 of 3,655 corpus clauses (65.4%) have `category='other'` from the initial
keyword-based classification pass. These should be reclassified via Qwen3 8B
to improve the intelligence layer's domain coverage.

## Approach (AGENTS.md compliant)

AGENTS.md forbids re-running classification over the existing 3,655 clauses
IN PLACE. Therefore this plan is **additive only**:

### Additive Migration

```sql
-- Migration 0010: Additive columns for v2 classification (never overwrites original)
ALTER TABLE disclosure_clause ADD COLUMN IF NOT EXISTS category_v2 TEXT;
ALTER TABLE disclosure_clause ADD COLUMN IF NOT EXISTS nlp_confidence_v2 FLOAT8;
ALTER TABLE disclosure_clause ADD COLUMN IF NOT EXISTS classifier_version TEXT;
```

- `category_v2`: The LLM-assigned category (NULL = not yet reclassified)
- `nlp_confidence_v2`: LLM confidence for the v2 classification
- `classifier_version`: e.g. "qwen3-8b-local-v1" for traceability

### Script: scripts/reclassify_other.py

- Processes ONLY rows where `category = 'other'` AND `category_v2 IS NULL`
- Uses LOCAL Ollama Qwen3 8B (batch, not hosted)
- Writes ONLY to the three new columns — never touches `category` or `nlp_confidence`
- Idempotent + resumable (only NULL category_v2 rows)
- --dry-run mode (classifies 10 rows, prints results, no writes)
- Logs progress (clause count, not text)

### What does NOT change

- `disclosure_clause.category` (original) — untouched for all 3,655 rows
- `disclosure_clause.nlp_confidence` (original) — untouched
- `disclosure_clause.embedding` — untouched
- All other tables — untouched

### How downstream consumers use it

After reclassification, scoring/findings can optionally prefer `category_v2`
over `category` for clauses where `category='other'` and `category_v2` is
non-null. This is a separate code change and can be wired incrementally.

## Estimated Impact

- ~2,391 clauses to reclassify
- Local Qwen3 8B at ~0.5s/clause = ~20 minutes batch time
- Expected: most "other" clauses will map to one of the 8 taxonomy domains
- Some will legitimately remain "other" (boilerplate, contact info, etc.)

## Approval Required

Please reply "approved" to proceed with:
1. Applying the additive migration
2. Running scripts/reclassify_other.py --dry-run (10 rows)
3. Running the full batch (2,391 rows)
