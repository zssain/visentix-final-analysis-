# Archived documentation (`docs/old-docs/`)

These files predate the **spec-driven documentation system** that now lives at the
repo root (`visentix-specs/`, `visentix-onboarding/`, `AGENTS.md`, `AUTOMATION.md`).
They were moved here on **2026-07-15** during the docs restructure — nothing was
deleted, so history and any un-migrated detail are preserved. Git history for each
file continues across the move (`git log --follow`).

**Do not treat anything here as current.** The source of truth is `visentix-specs/`.
When the content below has been absorbed into the specs (via the `spec-update` skill,
with version bumps), the corresponding file here can be deleted.

## Still-live docs (kept in `docs/`, NOT archived)

| File | Why it stays live |
|---|---|
| `docs/SETUP.md` | Local dev setup (venv, Ollama, env vars) — no equivalent in the new bundle |
| `docs/DEMO_RUNBOOK.md` | Live demo script + expected outputs — referenced by the MVP plan's DoD |
| `docs/DB_GROUND_TRUTH.md` | Introspected live Supabase schema + row counts — current operational reference |

## Archive index

### Superseded — fully covered by a new spec (safe to delete once confirmed)

| Archived file | Replaced by |
|---|---|
| `visentix-design.md` | `visentix-specs/01-foundation/design-system.md` §4 (DDRs) |
| `visentix-logic.md` | `visentix-specs/01-foundation/intelligence-logic.md` + `business-logic.md` |
| `visentix-screens.md` | `visentix-specs/02-features/F01–F12` + `design-system.md` |
| `SCHEMA.md` | `visentix-specs/01-foundation/schema.md` (its changelog cites this file) |
| `PRODUCT_OVERVIEW.md` | `business-logic.md` + `intelligence-logic.md` (+ F01–F10) |
| `UI_SPEC.md` | `design-system.md` §0 + F01–F09 + `00-plan/mvp-completion-plan.md` |

### Partial — content absorbed into the specs on 2026-07-15 (✅ migrated)

| Archived file | Absorbed into | Status |
|---|---|---|
| `LANGUAGE.md` | `01-foundation/business-logic.md` §2 (approved-alternative table, exposure pattern, confidence caveats, source-excerpt exception) | ✅ business-logic v1.2 |
| `SECURITY_MATRIX.md` | `02-features/F10-auth-and-tenancy.md` (route access-control matrix + RLS summary) | ✅ F10 updated |
| `DATA_HANDLING.md` | `business-logic.md` §6 (hosted-endpoint zero-retention/no-training, `HOSTED_QWEN_*` env, log-that-not-what) | ✅ business-logic v1.2 |
| `SHADCN_TAILWIND_GUIDE.md` | — (one-time setup steps, already applied) | Kept as historical reference only |

These four can be deleted once someone confirms the absorbed copies read correctly.

### Historical / point-in-time snapshots (keep for the record; not migrated)

`AUDIT.md`, `F001_RECOMPUTE_REPORT.md`, `INVENTORY.md`, `MIGRATION_PLAN_P1.md`,
`PROGRESS.md`, `RECLASSIFY_PLAN.md`, `RELEASE_NOTES.md`, `VICBNF_ALIGNMENT.md`,
`VICBNF_VERIFICATION.md` — dated build logs, migration/reclassify plans, and
verification reports. Superseded by the current state of the repo and by
`logs/session-log-2026-07-15.md`.

## Facts reconciled on 2026-07-15 (verified against the codebase)

The coverage review flagged places where these old docs were more current than the
specs. Each was **checked against the actual code/DB** before editing — two of the
review's suggestions turned out to be wrong, which is why verification mattered:

1. ✅ **Reclassification columns → `schema.md` v1.1 + `intelligence-logic.md` v1.1 §4.**
   Added `category_v2`, `nlp_confidence_v2`, `classifier_version` on `disclosure_clause`
   (write-only). Verified in `scripts/reclassify_other.py` (`classifier_version=qwen3-8b-local-v1`).
2. ✅ **Test count → 633** across `README.md`, `mvp-completion-plan.md`, `further-ideas.md`
   (was 453; VICBNF_VERIFICATION said 604). `pytest --collect-only` = **633** now.
   *Caveat:* a DB-less local run showed 610 pass / 23 fail, where the 23 are
   live-Supabase-dependent (row-count + export tests) — not verified fully green here.
3. ✅ **Corpus reclassification shipped** → noted in `intelligence-logic.md` §4.
4. ⚠️ **JWT — the review was wrong.** It claimed "the app uses ES256, HS256 is stale."
   Code shows **both**: verification tries ES256 (Supabase JWKS) then falls back to
   HS256, and the local seed auth *issues* HS256. F10 now states this accurately —
   do **not** blanket-replace HS256 with ES256.
5. ⚠️ **Table naming — the review was wrong / unverified.** It claimed `legal_reference`
   / `finding_legal_reference` "resolve to `finding_enforcement`." The code
   (`app/routers/findings.py`, `explain.py`) queries `legal_reference` and
   `finding_legal_reference` as real tables — so schema table naming was **left unchanged**.
   If DB_GROUND_TRUTH's claim is real (a view/rename), confirm against live Supabase first.

Still open (not migrated — point-in-time provenance, low value): F-001 recompute
stats (303 sources, zero drift) could be cited in F04 / `intelligence-logic.md` §7.
