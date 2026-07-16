# Full Application Roadmap — MVP → Four Commercial Products

**Version:** 1.0 · 2026-07-15
**Frame:** One canonical intelligence engine (VICBNF) feeding four products: (1) One-Time Assessment, (2) GRC / Continuous Monitoring Platform, (3) White-Label Intelligence, (4) Quarterly Global Privacy Intelligence Report. No product gets its own dataset; all consume shared derived intelligence objects (DIR-008).

---

## Release 1 — "Assessment" (MVP complete → first revenue)

*Scope:* the current build finished per `mvp-completion-plan.md`.
- Product 1 fully live: intake → decompose → classify → profile → normalize → score → SME review → 12-section reproducible report + PDF.
- Monitoring dashboard live for single-org customers (trend, change feed, alerts) — the "it's watching" proof.
- Corpus: seed benchmark corpus with priority-industry public notices (Retail, SaaS, Healthcare, Financial per ICP) so cohorts hit n≥20 in demo industries.
- Business: Tier 1 pricing ($500–$2,000/mo reports), design-partner program, first 3–5 pilots.

## Release 2 — "Corpus & Monitoring at scale" (GRC foundation)

The GRC platform's value depends on a living corpus and real recurring recalculation.

1. **Ingestion pipelines (F02 expansion):** scheduled crawlers for public peer notices (monthly), FTC/state AG/CPPA enforcement (weekly), state law tracker (monthly). Hash-diff change detection, source versioning, Source Reliability Score (F-001), Corpus Quality Score gating (CQS ≥ 75 for active benchmark use).
2. **Recalculation orchestration:** trigger matrix from the Derived Intelligence Catalog — notice change → diff + rescore affected domains; new enforcement → rerun F-004 correlations; benchmark refresh (monthly) → rebuild cohorts with version preservation.
3. **Monitoring productization:** per-customer monitored URL list, alert routing (email + in-app), alert severity from F-013, quiet-period and baseline states.
4. **Multi-tenancy hardening:** tenant isolation, role model beyond customer/SME/admin (portfolio owner, viewer), audit trail.
5. **Portfolio features (GRC V1):** multi-brand portfolio view, variance map across brand notices, remediation task objects linked to findings (finding → task → owner → status), executive monthly digest.

*Revenue unlock:* Tier 2 ($2K–$10K/mo dashboard + benchmarking).

## Release 3 — "White-Label & API"

1. **Partner portal:** client workspaces, branding controls (logo/colors on report templates), usage tracking, licensing limits.
2. **Intelligence APIs** (contracts in VICBNF §14): Organization Profile, Notice Classification, Benchmark Population, Derived Intelligence, Explainability, White-Label Feed. Every payload carries VCI + formula_version + lineage refs.
3. **Anonymized feeds:** benchmark data feed, regulator trend feed, risk signal feed, industry maturity feed — with minimum-sample suppression (DIR-006) and de-identification (reuse the SME de-id checker pipeline).
4. **Report template engine:** same intelligence rendered as executive report / legal memo / partner-branded report / board deck (Use Case Catalog requirement).

*Revenue unlock:* Tier 3 enterprise/white-label ($25K+/yr).

## Release 4 — "Quarterly Report & bulk intelligence"

1. **Quarterly publication engine:** quarter-close snapshot freeze, aggregation + anonymization checks, market-signal metrics (F-012 trend deltas across corpus, top disclosure gaps, compound risk patterns, AI governance trends), methodology auto-generation from dataset metadata, editorial reader page (Screen spec §6).
2. **Bulk analysis workflows (V2 use cases):** regulator sector scan, law-firm opportunity scan, audit-firm prospecting — company-list upload, risk-ranked queue, evidence packages, CSV/export.
3. **Framework Crosswalk** ships (post OD-01): descriptive mappings to NIST Privacy Framework / ISO 27701 / state law references.

*Business value:* top-of-funnel marketing engine + regulator/analyst credibility.

## Release 5 — "Scale & moats" (future-state)

- Predictive enforcement intelligence, regulator forecasting (Intelligence Engine §12).
- Knowledge graph productization (org ↔ clause ↔ regulator ↔ enforcement ↔ cohort as queryable graph).
- Reader registers with per-persona defaults; insurance underwriting API; M&A diligence mode.
- Model upgrades: replace/augment local Ollama with managed LLMs where data-handling policy allows; embedding model upgrade path with re-embedding migration plan.
- Patent package maintenance: keep architecture docs current for the seven patent families (dynamic benchmarking, RSS modeling, OSI normalization, normalization engine, compound risk, explainable lineage, knowledge graph).

## Cross-release engineering invariants

1. **Reproducibility:** every published number reproducible from stored snapshot + formula version + benchmark version (DIR-010).
2. **Confidence everywhere:** no score surfaces without VCI; <40 VCI suppressed or routed to review.
3. **Guardrail:** exposure/maturity/likelihood/benchmark/confidence language only — never compliance verdicts. Banned-term filter runs on every generated output including new products.
4. **Single intelligence source of truth:** presentation layers consume `derived_data_item` records; no product-side recalculation.
5. **Spec-first:** every release item gets a feature spec in `02-features/` before implementation.
