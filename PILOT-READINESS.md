# Pilot-Readiness Report — 2026-07-27

**Prepared by:** interim AI engineer/reviewer (all approvals attributed `ai_reviewed`; none impersonate the human SME).
**Scope:** data-readiness pass taking the database from the 2026-07-25 inventory toward pilot-ready — profiled orgs, honest benchmark cohorts, expert-gated config, formula descriptions, de-identified exemplars — all verified by tests and a fresh counts report.

> ⚠️ **Everything below marked `ai_reviewed` is pending the human owner/SME's confirmation.** No client report snapshot was approved or frozen (that gate stays human). Historical snapshots were not touched (Rule 4).

---

## 1. What changed, by phase

### Phase 0 — Live audit
- Reproduced the inventory via read-only `make census`; only drift was `report_snapshot` 106→107 (a generated snapshot, untouched).
- Corrected mock-tracker **M-13** (gate-mode backend is real at `GET/POST /review/gate-mode`, `platform_setting`-backed; only frontend wiring remains) and confirmed **M-14** `trigger-assessment` is still a `not_implemented` stub.
- Flagged two schema↔DB gaps (`formula_version.description`, `disclosure_clause.is_exemplar`) and the pilot-ICP data reality (demo industries were Princeton-2019, CQS-excluded).

### Phase 1 — Expert-gated config (`ai_reviewed`)
- **Migration 0030:** added an `ai_reviewed` state (distinct from human `approved`) + `reviewed_by`/`reviewed_at` to both crosswalk tables.
- **`sic_industry_map`:** the 13 draft rows used an obsolete 6-industry numbering that **collided** with the canonical 10-industry taxonomy (`config/org_profile_weights.json`). Corrected 11 rows to canonical codes + `ai_reviewed`; 2 "Entertainment & Media" rows have no canonical equivalent → left `draft`/`IND-00`, raised **OD-09**.
- **`ftc_topic_domain_map`:** populated from live FTC `issue_tags` — 25 rows, 11 mapped to a domain (CR/DC/SH/RT/AI/SEC/TRK), 14 sector/program/statute/harm tags with `domain=NULL` + note (honest non-mapping).
- **OD-01…OD-05 Decided (`ai_reviewed`)**, adopting each recommendation verbatim; propagated to F13/F05/F06, design-system (v1.4), intelligence-logic (v1.4 §5), schema.md (v1.3.2); AGENTS.md regenerated.

### Phase 2 — Profiling at scale + fresh ingestion
- **Fixed a blocking crawler bug:** `OpenWebWriter.load_targets` over-quoted the sector filter (`sector=eq."fintech"`), so every `--sector` crawl returned 0 targets. Fixed + regression test.
- **Fresh 2026 notices ingested** (open-web crawler, Playwright + local Qwen3-8B classification): fintech 13, retail 25, healthcare 31 captured. These refresh existing (Princeton) orgs' *current* notices → CQS-fresh.
- **Scalable profiler** (`scripts/compute_profiles_scaled.py`): server-side aggregation scoped to a bounded org set (replaces the old full-corpus OFFSET scan). Profiled **85 fresh orgs**; total profiles **31 → 116**. Never fabricates a dimension.

### Phase 3 — Cohort rebuild (F03)
- New benchmark population (version 2, refresh 2026-07-27) built from CQS-eligible (fresh-notice + profiled) orgs; v1 clusters left intact.
- Fixed a real correctness bug: `compute_normalization.py` fetched orgs unpaginated (capped at 1000 of 26k) → benchmark job silently ran on ~40 orgs. Now profile-driven + paginated; **all v2 members carry normalization weights**.

### Phase 4 — Entity resolution
- Re-ran the deterministic (exact/normalized) resolvers over a 32,029-name index: **0 safe additional matches** of the 623 enforcement + 696 security unresolved rows. The FTC/CPPA/AG targets and HHS breach reporters are not in our org corpus under matching names; per the rules, fuzzy matches are **left unresolved** (review queue), never forced.

### Phase 5 — Content & review pipeline
- **M-10:** migration 0031 + all 14 `formula_version.description` populated (plain-English, guardrail-safe, 0 NULL).
- **De-id gate hardened:** now blocks emails/URLs (not just known org names) + a `redact()` helper; +4 regression tests including *an exemplar containing an email cannot be approved*.
- **M-03:** migration 0032 (`is_exemplar`/`exemplar_status`); **16 exemplars approved across 8/8 demo domains** — only clauses that pass de-id with the org's own name blocked (no leak).
- **Part-B (clause↔obligation):** implemented but **deferred** — clause embeddings are only 2.8% populated (658k backlog); running it now would populate `clause_obligation` for <3% of clauses. Not improvised.

---

## 2. Final counts (live, 2026-07-27)

| Metric | 2026-07-25 | 2026-07-27 |
|---|---:|---:|
| organization_intelligence_profile | 31 | **116** |
| benchmark_cluster | 3 | **6** (3 v1 + 3 new demo cohorts) |
| benchmark_membership | 30 | **109** |
| privacy_notice (open_web / fresh) | ~14 | **~85 orgs** |
| formula_version.description NULL | 14 | **0** |
| disclosure_clause.is_exemplar = true | 0 (col absent) | **16** |
| sic_industry_map ai_reviewed | 0 | **11** (2 draft, OD-09) |
| ftc_topic_domain_map | 0 | **25** (11 domain-mapped) |
| clause_obligation | 0 | 0 (Part-B deferred) |
| enforcement / security unresolved | 623 / 696 | 623 / 696 (0 safe matches) |

Full table-by-table inventory: [`logs/audits/database-inventory-2026-07-27.csv`](logs/audits/database-inventory-2026-07-27.csv).

## 3. Demo cohorts (benchmark_version=2) — sizes + confidence

| Cohort | Live n (benchmark_membership) | Confidence | Weights |
|---|---:|---|---|
| `retail-2026Q3-v2` | **25** | Full (≥20) | 25/25 |
| `healthcare-2026Q3-v2` | **31** | Full (≥20) | 31/31 |
| `fintech-2026Q3-v2` | **23** | Full (≥20) | 23/23 |

All three clear the n≥20 full-confidence floor; `n` is live-queryable from `benchmark_membership` (M-12 — no static n). The low-confidence pathway (10 ≤ n < 20, OD-05 `LOW_CONFIDENCE_COHORT_N=10`) is codified in `build_cohorts.py` and intelligence-logic §5 but was not needed for these three. Logistics (5) and manufacturing (1) fresh orgs remain below the floor → no demo cohort built for them.

## 4. Verification
- Final full run **green**: pytest **746 passed / 15 skipped / 0 failed**, vitest **79/79**.
- Along the way, fixed stale-assumption tests my data changes exposed (hardcoded membership count `==30`→live invariant; migration manifest updated for 0030-0032; embedding tests now filter `embedding IS NOT NULL` + retry transient DB timeouts; category-reconciliation rewritten scan-free).
- Exit-gate grep for hardcoded `S-2041` / `n=30` / `142/31/12` in app/web code: **no matches**.
- New/updated regression tests: sector-filter over-quoting, canonical SIC codes, email/URL de-id block, category-reconciliation hardened to a scan-free invariant.

## 5. What remains **human-gated** (do not ship without these)
1. **Human SME re-review** of every `ai_reviewed` item before any client delivery: the sic/ftc crosswalk rows, OD-01…OD-05 closures (owner Teams confirmation), and the 16 exemplars.
2. **Client report snapshot approval / freeze** (`approve_and_freeze`) — never performed here.
3. **Frontend wiring** to close M-03 (BenchmarkLanguage → `is_exemplar`), M-10 (lineage drawer → `formula_version.description`), M-12 (live cohort n), M-13 (Console → `/review/gate-mode`).
4. **M-14** backend (`/admin/trigger-assessment`) still a stub.

## 6. Open questions I stopped on (did not guess)
- **OD-09** — no canonical 10-industry equivalent for "Entertainment & Media" (SIC 2700-2799, 7800-7999). Left unmapped; expert to add an industry or remap.
- **Part-B / clause embeddings** — 658k-clause embedding backfill is the prerequisite to populate `clause_obligation` meaningfully.
- **Entity-resolution backlog** — closing the 623/696 needs org-corpus enrichment (adding enforcement targets / breach reporters as orgs+aliases), a data-sourcing task, not deterministic resolution.
- **No SaaS in corpus** — the pilot ICP names SaaS, but `organization.industry` has no `saas` label; fresh SaaS ingestion needs new SaaS company domains (not derivable from existing orgs). Retail/healthcare/fintech(≈financial) cohorts stand in.
- **OD-07 / OD-08** (benchmark_cluster naming; gate-mode enum) remain open from the prior audit — out of this pass's scope.
