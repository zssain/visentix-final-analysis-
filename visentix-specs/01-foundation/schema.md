# Schema — Canonical Data Model

**Version:** 1.3.3 · 2026-07-27 · Authority: this file supersedes prose in the source docs; physical DDL lives in migrations, but no table/field may exist that isn't described here or in a feature spec that amends this file.
**Storage:** Postgres (Supabase-hosted). Embeddings via pgvector (`all-MiniLM-L6-v2`, 384-dim). Hybrid graph/vector semantics expressed relationally for MVP.

---

## 1. Design principles

1. **Lineage is non-negotiable.** Every derived value links back through explainability references to clauses → notices → sources.
2. **Nothing is silently overwritten.** Versioned: notices, formulas, benchmark populations, snapshots, scores.
3. **Snapshot immutability.** A `report_snapshot` freezes everything a report shows; regenerating a report reads the snapshot, never recomputes.
4. **Tenant isolation.** Every customer-scoped row carries `tenant_id`; RLS enforced (note: RLS recursion/NULL `auth.uid()` bugs were fixed in Phase 2 — regression tests must stay).
5. **Config over code.** Weights, state-law lookups, taxonomy, thresholds live in tables, not constants (single exception: UI constants like `LOW_CONFIDENCE_COHORT_N` mirror a DB setting).

## 2. Entity catalog

### 2.1 Identity & tenancy
| Table | Key fields | Notes |
|---|---|---|
| `tenant` | tenant_id, name, plan_tier, created_at | Customer account / partner workspace |
| `local_users` / `user_profile` | user_id, tenant_id, email, role (customer, sme, admin, partner), created_at | Custom JWT auth (ES256); roles drive routing |
| `platform_setting` | key, value, updated_by, updated_at | e.g. gate_mode, LOW_CONFIDENCE_COHORT_N |

### 2.2 Source & corpus layer
| Table | Key fields | Notes |
|---|---|---|
| `source_record` | source_id, source_type (notice, regulator, enforcement, litigation, ai_gov, market, **security**, **corporate_filing**, **dataset**), tier (1–3), url, publisher, jurisdiction, capture_date, content_hash, extraction_confidence, reliability_score, version_id | Tiering + minimum metadata per VICBNF §3.2. `source_type` extended in v1.3 for the ingestion architecture (F02 v2): `security` (breach reports), `corporate_filing` (SEC EDGAR etc.), `dataset` (bulk research corpora e.g. Princeton-Leuven) |
| `source_version` | version_id, source_id, hash, captured_at, diff_summary | Created when hash changes (change detection) |
| `corpus_quality` | source_id, extraction_conf, completeness, freshness, source_reliability, version_stability, cqs | CQS ≥ 75 required for active benchmark use |

### 2.3 Organization & profile layer
| Table | Key fields | Notes |
|---|---|---|
| `organization` | organization_id, tenant_id (nullable for public peers), name, domain, industry_id, sub_industry, size_metadata, revenue_metadata, public_company_flag, jurisdiction_presence | Customers AND benchmark peers. ⚠️ **Live reconciliation (v1.3):** the live table currently uses a text column **`industry`** (plus `entity_type`, `public_private`, `size`, `geography`, `sector_tags`, `slug`). The `industry_id` / `sub_industry` / `public_company_flag` / `size_metadata` / `revenue_metadata` / `jurisdiction_presence` columns above are **authored in migration 0014 but NOT applied to live** — see §5. Alias/identifier records live in `organization_alias` (§2.9). |
| `organization_profile` | profile_id, organization_id, ic, rss, pgms, osi, dsi, ehp_tier, ehp_score, aigms, profile_version, confidence_score, generated_at | The 7-dimension VICBNF profile; versioned. Live table name is **`organization_intelligence_profile`**. ⚠️ The tier-label columns (`rss_tier`, `pgms_tier`, `osi_tier`, `dsi_tier`, `ehp_tier`, `aigms_tier`, `industry_id`, `sub_industry`) are **authored in migration 0014 but NOT applied to live** — see §5. |
| `industry_taxonomy` | industry_id, name, sub_industries[], benchmark_notes | Controlled taxonomy (VICBNF §4.1) |
| `state_law_weight` | state, weight, effective_date, notes | Configurable RSS lookup (laws evolve) |

### 2.4 Notice & clause layer
| Table | Key fields | Notes |
|---|---|---|
| `privacy_notice` | notice_id, organization_id, source_url, capture_date, effective_date, source_hash, extraction_confidence, notice_version, intake_method (url/pdf/text), ssrf_protected | One row per version |
| `notice_section` | section_id, notice_id, title, section_type, sequence, extracted_text | Preserves original structure |
| `disclosure_clause` | clause_id, section_id, notice_id, domain_id, clause_type, raw_text, normalized_text, embedding (vector 384), ambiguity_score, transparency_score, nlp_confidence, is_exemplar, exemplar_status (candidate/deidentified/approved); **v2 reclassification (additive, write-only, never overwrites the base `category`):** category_v2, nlp_confidence_v2, classifier_version | Atomic unit of the platform |
| `clause_taxonomy` | domain_id (CR, DC, SH, RT, AI, SEC, TRK, XB + other), clause_type, definition, intelligence_outputs[] | The controlled ontology (VICBNF §6) |
| `obligation` | obligation_id, source_id, domain, requirement_type, applicability, jurisdiction, embedding | Regulatory expectations; matched to clauses |
| `clause_obligation_match` | clause_id, obligation_id, similarity, match_confidence | Part-B matcher output |

### 2.5 Regulator & enforcement layer
| Table | Key fields | Notes |
|---|---|---|
| `regulator` | regulator_id, name, jurisdiction, authority, priority_weights (jsonb), topic_weights (jsonb) | FTC, CPPA, state AGs, OCR… |
| `enforcement_record` | enforcement_id, regulator_id, target_org, issue_tags[], penalty, remedy, date, jurisdiction, embedding, priority_weight | Feeds F-004, EHP, heatmap |
| `litigation_event` | litigation_id, claim_type, issue_tags[], jurisdiction, industry, settlement_value, date | Tier-2 sources |

### 2.6 Benchmark layer
| Table | Key fields | Notes |
|---|---|---|
| `benchmark_population` | population_id, population_key (Industry+RSS+PGMS+OSI+DSI+AIGMS+EHP tiers), dimensions (jsonb), relaxation_notes, version, built_at | Dynamic cohorts; relaxation recorded for explainability. ⚠️ **Live reconciliation (v1.3):** the live database exposes a table named **`benchmark_cluster`** (8 cols) that plays this cohort-grouping role; `benchmark_population` as named here may not be the applied name. Canonical name going forward is an **OPEN QUESTION (OD-07, engineer)** — do not assume either until decided. `benchmark_membership` (below) is live and correct. |
| `benchmark_membership` | membership_id, population_id, organization_id, notice_id, normalization_score, benchmark_weight, inclusion_reason | Live cohort n = COUNT(*) here — never static |

### 2.7 Scoring & intelligence layer
| Table | Key fields | Notes |
|---|---|---|
| `formula_version` | formula_id (F-001…F-014 + profile formulas), version, expression_text, description (plain English — powers lineage drawer), weights (jsonb), effective_from, approved_by | Versioned formula registry |
| `risk_finding` | risk_id, organization_id, notice_id, related_clause_ids[], finding_code (e.g. TRK-007), domain, severity, scores (jsonb), compound_group_id, confidence_score, interpretive_variance, sme_status (pending/confirmed/edited/dismissed), snapshot_ids[] | Deterministic + reproducible. Live also carries flat per-finding scoring columns (`regulatory_exposure_score`, `benchmark_deviation_score`, `enforcement_correlation_score`, `finding_type_code`, `formula_version_id`, `scoring_model_version`, `source_corpus_version`). |
| `finding_clause` | finding_id, clause_id | ⚠️ **Documented in v1.3 (live truth):** M–M junction linking a `risk_finding` to the `disclosure_clause` rows it cites (normalizes `related_clause_ids[]`). Present live; was undocumented before v1.3. |
| `finding_enforcement` | finding_id, enforcement_id, similarity | ⚠️ **Documented in v1.3 (live truth):** M–M junction linking a `risk_finding` to correlated `enforcement_record` rows (feeds F-004 lineage). Present live; was undocumented before v1.3. |
| `finding_type` | finding_code, domain_id, canonical_definition, exposure_signal, example_pattern, related_codes[] | The Codex source of truth |
| `derived_data_item` | derived_data_item_id, object_type (percentile, exposure, maturity, transparency, ai_gov, compound, enforcement_corr, trend_delta, alert, vci…), score, vci, vci_components (jsonb), formula_version_id, source_snapshot_id, benchmark_population_id, generated_at | DIR-001…004 (see intelligence-logic.md §12); UI/PDF consume these, never recompute (DIR-008) |
| `explainability_reference` | explainability_id, intelligence_id, source_type, source_id, clause_id, regulator_id, benchmark_population_id, rationale | Lineage drawer contents |

### 2.8 Output & review layer
| Table | Key fields | Notes |
|---|---|---|
| `assessment` | assessment_id, tenant_id, organization_id, notice_id, status (processing/ready/error), gate_mode_at_run, created_at | One run of the pipeline |
| `report_snapshot` | snapshot_id (S-####), assessment_id, snapshot_frozen_at, formula_versions (jsonb), benchmark_versions (jsonb), payload (jsonb — all 12 sections incl. Analyst + Advisor layers), status (draft/approved), approved_by | Byte-identical re-pull guarantee |
| `training_label` | label_id, risk_id, sme_user_id, action (confirmed/edited/dismissed), before_text, after_text, created_at | Captured from SME corrections |
| `monitoring_event` | event_id, tenant_id, organization_id, trigger_type (notice_changed, score_moved, regulator_signal, cohort_rebenchmarked), prior_value, current_value, severity, snapshot_id, timestamp | Powers change feed |
| `alert` | alert_id, tenant_id, finding/risk refs, escalation_score (F-013), severity (high/medium), status | Powers alert center |

### 2.9 Ingestion, connector & external-signal layer (new in v1.3)

Additive tables that back the registry-driven ingestion architecture (F02 v2). All new, all nullable-friendly; none replaces or mutates an existing corpus table.

| Table | Key fields | Notes |
|---|---|---|
| `source_registry` | registry_id (pk), family (text: sec_edgar, hhs_ocr, ftc, cppa, state_ag, princeton_leuven, open_web), display_name, base_url, cadence (text: manual/daily/weekly/monthly), reliability_tier (int 1–3), parser_type, enabled (bool), config (jsonb), created_at | The living, configurable registry of source families a connector can crawl (F02 §Source registry). One row per source family. `cadence` mirrors the SLA cadences in business-logic §7. ⚠️ **Family-taxonomy reconciliation (OPEN QUESTION, engineer):** the `raw-artifacts` bucket already uses folders `{ag_actions, cfpb, cppa, frameworks, ftc, litigation, notices, state_laws}`; the `family` value must resolve to a storage folder. Map is not 1:1 (e.g. `state_ag`↔`ag_actions`; `cfpb`/`frameworks`/`litigation`/`notices` folders have no matching enum value yet). Reconcile before first connector run — see F02 v2. |
| `ingestion_run` | run_id (pk), registry_id (fk → source_registry), started_at, finished_at, outcome (text: ok/partial/failed), records_seen, records_new, records_changed, records_skipped, error_summary (text), parser_version_id (fk → parser_version) | One row per connector execution; the provenance/audit trail for every pull (F02 §Run logging). ⚠️ **Live reconciliation:** `ingestion_run` **already exists** (migration 0011c) with columns `{run_id, source_name, run_type, started_at, finished_at, rows_inserted, rows_updated, status, notes}`. The fields above are **additive** — `registry_id`, `outcome`, `records_seen/new/changed/skipped`, `error_summary`, `parser_version_id` are added alongside the existing columns (`rows_inserted`≈`records_new`, `status`≈`outcome`, `source_name` retained). **No existing column is dropped or renamed.** |
| `parser_version` | parser_version_id (pk), family, version (text), description, effective_from | Versioned parser registry so every `ingestion_run` records which parser produced it. A parser change writes a new row (never edits an old one) — lineage rule §4. |
| `security_event` | event_id (pk), source_record_id (fk → source_record), organization_id (fk, nullable), entity_name_raw, entity_type, state, breach_date, submission_date, individuals_affected (int), breach_type, information_location, description, source_url, capture_date, extraction_confidence (real), resolution_status (text: unresolved/resolved) | Breach-report and security-incident signals (e.g. HHS OCR breach portal, state AG breach notifications). ⚠️ **RATIONALE (critical):** breach reports are **security / organization-risk signals, NOT enforcement actions**. They must **never** populate `enforcement_record` or feed **F-004 (Enforcement Correlation)** without a separate, expert-approved formula change. This physical separation is a **proposed decision, OD-06** (expert sign-off required) — see §5 and open-decisions.md. |
| `organization_alias` | alias_id (pk), organization_id (fk → organization), alias_type (text: cik/ticker/domain/legal_name/dba), value, match_confidence (real), source_record_id (fk → source_record, nullable) , created_at | Identifier/alias resolution so external records (SEC CIK, ticker, DBA names, domains) can be matched to the right `organization` without overwriting its canonical name. Supports entity resolution during ingestion. |
| `schema_migrations` | filename (pk), checksum, applied_at | **Migration-tracking table (new rule, §5).** No migration is considered applied unless a row exists here. Currently absent — migrations are hand-pasted with no ledger, which is the direct cause of the 0014/0017 drift documented in §5. |
| `crawl_target` | target_id (pk), organization_id (fk → organization, nullable), domain (unique, normalized), sector, priority (int), status (text: pending/captured/unchanged/no_notice/blocked/consent_wall/error), status_reason, content_hash, notice_url, last_crawled_at, added_by, created_at | Work-list for the `open_web` crawler (F02 v2): company domains whose CURRENT privacy notice to find + capture. Seeded from EDGAR mapped-industry orgs and Princeton-resolved orgs. `status`/`status_reason` record the honest outcome of the last attempt (never fabricated, never silently skipped); `content_hash` powers change-detection for re-crawls (same mechanism later used for monitoring). Migration 0029. |
| `sic_industry_map` | map_id (pk, `sic:{low}-{high}`), sic_low, sic_high, industry_id (canonical IND-xx), industry_name, mapped_by (draft/**ai_reviewed**/approved), reviewed_by, reviewed_at, notes, created_at | Expert-gated crosswalk from SEC SIC ranges → the **canonical 10-industry taxonomy** (`config/org_profile_weights.json`, IND-00 unmapped … IND-10). Source of truth mirrored in `config/sic_industry_map.json`. Migrations 0025 (seed) + 0030 (review columns + `ai_reviewed` state). **Never auto-applied to `organization.industry_id`** — a human SME must promote `ai_reviewed` → `approved` before it feeds profiling (F03) or cohorting. |
| `ftc_topic_domain_map` | map_id (pk, slug of ftc_topic), ftc_topic (verbatim), domain (one of the 8 codes CR/DC/SH/RT/AI/SEC/TRK/XB, or NULL), mapped_by (unmapped/draft/**ai_reviewed**/approved), reviewed_by, reviewed_at, notes, created_at | Expert-gated crosswalk from FTC topic tags on `enforcement_record.issue_tags` → Visentix disclosure domains (intelligence-logic §4). Descriptive mappings only. Tags that are sector/program/statute/harm labels carry `domain = NULL` with a note (honest non-mapping). Migrations 0026 (scaffold) + 0030 (review columns + `ai_reviewed` state, domain-code CHECK). |
| `assessment_review` | assessment_id (pk), status (draft/in_review/approved), finding_reviews (jsonb: finding_id → {action, edited_fields, reviewer_id, reviewed_at}), approved_by, approved_at, created_at, updated_at | **Persistence hardening (F06, migration 0022).** Authoritative store for SME review state — was held in `review.py` module memory (lost on restart). |
| `review_queue_item` | id (pk), assessment_id, object_type, vci_score, score, is_definitive, needs_review, cleared, created_at, cleared_at; UNIQUE(assessment_id, object_type) | **F06 (0022).** VCI analyst-review queue — merges the former in-memory `_low_vci_objects` + `_analyst_cleared` via the `cleared` flag. |
| `platform_setting` | key (pk), value, updated_at | **F06 (0022).** Key/value platform settings; holds `gate_mode` (was `review.py._gate_mode` module memory). Enum values unchanged pending **OD-08**. |

**`report_snapshot.assessment_id` (F06, 0022):** additive column linking a snapshot to its assessment, so **`approve_and_freeze(assessment_id, approver, snapshot_id)`** (PL/pgSQL) can find the snapshot to freeze. That function sets approval state and writes `report_snapshot.rendered_report` + `content_hash` in ONE transaction — a missing snapshot RAISEs and rolls back the approval (never half-approved; Hard Rule 6). `training_label` (0008) already held the SME-label shape and is now written to instead of module memory. RLS server-side-only on all three new tables.

## 3. Core relationships

```
organization 1─M privacy_notice 1─M notice_section 1─M disclosure_clause
disclosure_clause M─M risk_finding · M─M obligation · M─M benchmark_population
risk_finding M─M enforcement_record · 1─M training_label
derived_data_item M─M explainability_reference
assessment 1─1..M report_snapshot (draft → approved)
monitoring_event M─M risk_finding
```

## 4. Versioning & lineage requirements (hard rules)

- Every score row stores: `scoring_model_version`, `benchmark_population_version`, `source_corpus_version`, `formula_version`, `generated_at`.
- LLM/NLP outputs store model version, prompt version, confidence, review status.
- Human overrides logged with reason + timestamp (`training_label` and audit columns).
- Anonymized/aggregate outputs (white-label, quarterly) live in separate tables from customer-scoped values (DIR-005); minimum-sample suppression before publication (DIR-006).

## 5. Live-schema reconciliation & migration governance (new in v1.3)

The build is mid-flight; the written schema had drifted from the applied database. This section records the reconciliation (source: `logs/audits/2026-07-data-layer-audit.md`, 2026-07-20) and sets the governance rule that prevents recurrence. **These are truth corrections, not proposals to change the data.**

**5.1 Migration-application status (authored but NOT applied to live).** Verified via PostgREST reflection on 2026-07-20:

| Migration | Table | Columns authored but absent from live | Severity |
|---|---|---|---|
| **0017** | `report_snapshot` | `rendered_report`, `content_hash`, `report_version`, `glossary_version`, `template_version` (only `scoring_model_version` landed) | **CRITICAL — Hard Rule 6 (immutable snapshots / byte-identical re-pull) is NOT physically backed until 0017 is applied. There is no column to freeze a rendered report into.** |
| **0014** | `organization` | `industry_id`, `sub_industry`, `public_company_flag`, `size_metadata`, `revenue_metadata`, `jurisdiction_presence` | High — profiling reads the live text column `industry` instead (see §2.3). |
| **0014** | `organization_intelligence_profile` | `industry_id`, `sub_industry`, `rss_tier`, `pgms_tier`, `osi_tier`, `dsi_tier`, `ehp_tier`, `aigms_tier` | High — 7-dimension tier labels have no column to persist into. |
| **0011_local_users** | `local_users` | entire table not visible via API | Ambiguous — local JWT auth appears to run off `local_users.json`; may be unapplied or API-revoked. Needs direct-DB confirmation. |

Applying migrations **0014 and 0017 to live is authorized as an explicit Phase-1 prerequisite** for the F02 v2 ingestion work (see F02 v2 → Prerequisites), pending the confirmation flagged in open-decisions.md.

**5.2 Migration governance rule (new).**
1. A `schema_migrations` table (§2.9: `filename`, `checksum`, `applied_at`) must exist and be written on every apply. **No migration is considered applied unless it has a row there.** This is the guard whose absence caused the 0014/0017 drift.
2. **Unique sequence numbers going forward.** The current tree has duplicated numbers — two `0011` (`_live_assessment_isolation`, `_local_users`, `_reference_corpus`), two `0012` (`_finding_content`, `_versioning_metadata`), two `0013` (`_clause_taxonomy_v2`, `_enforcement_extra_cols`). New migrations must use a unique, monotonically increasing sequence number.
3. Migrations remain **additive-only** (AGENTS.md §2): new tables, new nullable columns, new indexes. The single historical exception is `0011_live_assessment_isolation`'s `ALTER COLUMN organization_id DROP NOT NULL` (constraint-loosening, non-destructive).

**5.4 Monitoring read-layer reconciliation (2026-07-27, F07 M-06/07/08).** Verified via PostgREST reflection while building `app/routers/monitoring.py`. **Truth corrections, not data changes:**

| Declared (§2.8) | Live reality | Consequence for the read layer |
|---|---|---|
| `monitoring_event` has `organization_id`, `tenant_id`, `snapshot_id`, `timestamp`, `trigger_type` enum (notice_changed/score_moved/regulator_signal/cohort_rebenchmarked) | Live columns: `event_id`, `trigger_type` (value **`hash_change`**), `source_id`, `prior_value`, `current_value`, `material_change_indicator`, `severity`, `ts`. **No org/tenant/snapshot column.** | Events org-scoped **at query time** via `source_record.url` host ↔ `organization.domain` (+ the org's `privacy_notice` URLs). `trigger_type` normalized to the §2.8 vocabulary (`hash_change`→`notice_changed`). Adding a real `organization_id` column + backfill is a **future additive migration** (not done — backfill provenance would be fuzzy). |
| `alert` table (`alert_id`, `escalation_score` F-013, `severity`, status) | **Table absent from live.** | Alerts computed from stored F-013 `alert_escalation` (`derived_data_item`) joined to **resolved** `enforcement_record` only; the 623 unresolved never surface. No `alert` table is created (would need expert sign-off on the alert model). |
| F-013 severity banding | `formula_version.thresholds` for F-013 is **NULL** — no F-013-score→High/Medium/Severe mapping is defined anywhere. | Alert severity is surfaced **only** from a stored `monitoring_event.severity`; no numeric band thresholds are invented (Hard Rule: never invent thresholds). Defining them is an **OPEN QUESTION for the expert**. |

The `monitoring_event` and `formula_version` tables remain on the read-only-inputs list (AGENTS.md §2); this pass added no columns to them.

## 6. Changelog
- 1.3.3 (2026-07-27): **Monitoring read-layer reconciliation (§5.4, F07 closeout).** Recorded live truth for `monitoring_event` (no `organization_id`/`tenant_id`/`snapshot_id`; `trigger_type` value `hash_change`) and the **absent** `alert` table, and that F-013 severity band thresholds are undefined. Documents how `app/routers/monitoring.py` org-scopes events (source URL ↔ org domain) and computes alerts (stored F-013 + resolved enforcement only) without inventing thresholds. No table or column altered. Source: engineer (F07 M-06/07/08).
- 1.3.1 (2026-07-24): **Persistence hardening landed on the connector line (F06, migration 0022).** Brought the previously-unmerged `F06-persistence-hardening` wiring onto the running branch: `assessment_review` / `review_queue_item` / `platform_setting` become the **authoritative** stores for SME review state, the VCI analyst queue, and gate mode (all previously module memory in `review.py`, lost on restart); `training_label` (0008) is now written to instead of `training.py._labels`. Added `report_snapshot.assessment_id` + the `approve_and_freeze()` PL/pgSQL function (approval + snapshot freeze in one transaction; kill-test + restart-survival tests prove nothing is lost). Migration 0022 was already applied to live in the F06 session; this change adds the file + service wiring + tests to the connector line. No existing table/column altered or dropped.
- 1.3.2 (2026-07-27): **Config-crosswalk tables documented + review support.** Added `sic_industry_map` and `ftc_topic_domain_map` to §2.9 (migrations 0025/0026), which were live but undocumented here; recorded migration 0030's `ai_reviewed` `mapped_by` state, `reviewed_by`/`reviewed_at` columns, and the FTC `domain`-code CHECK. Documented that `sic_industry_map` uses the **canonical 10-industry taxonomy** (`config/org_profile_weights.json`) — Phase-1 review corrected the draft codes onto it. No existing column altered or dropped. Source: Phase-1 pilot-readiness pass (ai_reviewed); `logs/decision-log.md` 2026-07-27.
- 1.3.1 (2026-07-23): **Open-web crawler work-list.** Added `crawl_target` to §2.9 (migration 0029) — the additive work-list of company domains whose current privacy notice the `open_web` connector finds + captures, seeded from EDGAR mapped-industry and Princeton-resolved orgs. It records honest per-domain crawl outcomes (`status`/`status_reason`: pending/captured/unchanged/no_notice/blocked/consent_wall/error) and a `content_hash` for re-crawl change-detection (the mechanism that later powers monitoring). No existing table or column altered or dropped. Source: engineer (F02 open-web crawler).
- 1.3 (2026-07-20): **Ingestion-architecture amendment.** Added §2.9 ingestion/connector/external-signal layer (`source_registry`, `ingestion_run` evolved additively, `parser_version`, `security_event`, `organization_alias`, `schema_migrations`); extended `source_record.source_type` with `security`, `corporate_filing`, `dataset`; added §5 live-schema reconciliation (0014/0017 authored-not-applied; migration-tracking rule; unique-sequence rule) and documented live truth for `benchmark_cluster` (naming OD-07), `organization.industry` vs `industry_id`, and the `finding_clause` / `finding_enforcement` junctions. `security_event`'s separation from enforcement is proposed as **OD-06** (expert). Source: engineer + `logs/audits/2026-07-data-layer-audit.md`. No existing table or column altered or dropped.
- 1.2 (2026-07-16): Linked the `derived_data_item` DIR-001…004 / DIR-008 citations to their new canonical registry (intelligence-logic.md §12). No structural change — resolves previously dangling DIR references.
- 1.1 (2026-07-15): Documented the additive v2 corpus-reclassification columns on `disclosure_clause` (`category_v2`, `nlp_confidence_v2`, `classifier_version`) — write-only, never overwrite the base `category`. Absorbed from the archived DB_GROUND_TRUTH.md / RECLASSIFY_PLAN.md; verified against `scripts/reclassify_other.py`.
- 1.0 (2026-07-15): Initial canonical consolidation of SCHEMA.md, DB_GROUND_TRUTH.md, VICBNF §13, Data Model Framework §3, Derived Intelligence Catalog entities.
