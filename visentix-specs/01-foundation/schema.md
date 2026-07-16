# Schema — Canonical Data Model

**Version:** 1.2 · 2026-07-16 · Authority: this file supersedes prose in the source docs; physical DDL lives in migrations, but no table/field may exist that isn't described here or in a feature spec that amends this file.
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
| `source_record` | source_id, source_type (notice, regulator, enforcement, litigation, ai_gov, market), tier (1–3), url, publisher, jurisdiction, capture_date, content_hash, extraction_confidence, reliability_score, version_id | Tiering + minimum metadata per VICBNF §3.2 |
| `source_version` | version_id, source_id, hash, captured_at, diff_summary | Created when hash changes (change detection) |
| `corpus_quality` | source_id, extraction_conf, completeness, freshness, source_reliability, version_stability, cqs | CQS ≥ 75 required for active benchmark use |

### 2.3 Organization & profile layer
| Table | Key fields | Notes |
|---|---|---|
| `organization` | organization_id, tenant_id (nullable for public peers), name, domain, industry_id, sub_industry, size_metadata, revenue_metadata, public_company_flag, jurisdiction_presence | Customers AND benchmark peers |
| `organization_profile` | profile_id, organization_id, ic, rss, pgms, osi, dsi, ehp_tier, ehp_score, aigms, profile_version, confidence_score, generated_at | The 7-dimension VICBNF profile; versioned |
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
| `benchmark_population` | population_id, population_key (Industry+RSS+PGMS+OSI+DSI+AIGMS+EHP tiers), dimensions (jsonb), relaxation_notes, version, built_at | Dynamic cohorts; relaxation recorded for explainability |
| `benchmark_membership` | membership_id, population_id, organization_id, notice_id, normalization_score, benchmark_weight, inclusion_reason | Live cohort n = COUNT(*) here — never static |

### 2.7 Scoring & intelligence layer
| Table | Key fields | Notes |
|---|---|---|
| `formula_version` | formula_id (F-001…F-014 + profile formulas), version, expression_text, description (plain English — powers lineage drawer), weights (jsonb), effective_from, approved_by | Versioned formula registry |
| `risk_finding` | risk_id, organization_id, notice_id, related_clause_ids[], finding_code (e.g. TRK-007), domain, severity, scores (jsonb), compound_group_id, confidence_score, interpretive_variance, sme_status (pending/confirmed/edited/dismissed), snapshot_ids[] | Deterministic + reproducible |
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

## 5. Changelog
- 1.2 (2026-07-16): Linked the `derived_data_item` DIR-001…004 / DIR-008 citations to their new canonical registry (intelligence-logic.md §12). No structural change — resolves previously dangling DIR references.
- 1.1 (2026-07-15): Documented the additive v2 corpus-reclassification columns on `disclosure_clause` (`category_v2`, `nlp_confidence_v2`, `classifier_version`) — write-only, never overwrite the base `category`. Absorbed from the archived DB_GROUND_TRUTH.md / RECLASSIFY_PLAN.md; verified against `scripts/reclassify_other.py`.
- 1.0 (2026-07-15): Initial canonical consolidation of SCHEMA.md, DB_GROUND_TRUTH.md, VICBNF §13, Data Model Framework §3, Derived Intelligence Catalog entities.
