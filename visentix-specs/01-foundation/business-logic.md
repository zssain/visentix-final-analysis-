# Business Logic — Products, Guardrails, Operations

**Version:** 1.2 · 2026-07-15

## 1. What Visentix is (and is not)

Visentix is a **Privacy Intelligence Platform**: it transforms public privacy notices, regulatory materials, enforcement actions, and litigation records into **benchmark-driven, explainable, confidence-scored intelligence**. Positioning: "Bloomberg for Privacy Risk & Compliance."

It is **not** a compliance checker, legal advisor, GRC checklist tool, or document repository. The foundational question is never "is this notice compliant?" but "**how does this notice compare** to similar organizations, regulatory expectations, enforcement trends, and transparency leaders — and with what confidence?"

## 2. The Guardrail (absolute)

**No legal verdicts, ever.** Applies to all generated text, UI copy, API payloads, and marketing.

- **Banned:** "violation detected", "violates", "compliant", "non-compliant", "illegal", "unlawful", "breach of law", "guilty", "liable", "complies with" — any binary legal conclusion. The guardrail runs at draft time and hard-fails a report build containing a banned term.
- **Required vocabulary:** exposure, maturity, likelihood, benchmark position, regulator sensitivity, confidence, interpretation.
- **The model classifies and phrases — it never invents.** No claim, number, score, finding, or recommendation originates from an LLM: scores come from the formula engine, findings from the finding-type catalog, recommendations from the authored library. The LLM only smooths tone over pre-computed, guardrailed statements.
- **Enforcement:** the banned-term filter runs on every narrative output; LLM rephrasing is verified with deterministic fallback; the "Intelligence, not legal advice" mark appears per DDR-007 placement rules.
- **Framework crosswalks** (NIST/ISO/state law) stay descriptive ("relates to CCPA §1798.120"), never verdict.
- **Interpretive variance** is modeled, not hidden: findings carry a classification of High Consensus / Moderate Consensus / Emerging / Ambiguous Interpretation Area.

**Approved-alternative mapping** (rewrite banned phrasings, never soften the substance):

| Instead of… | Use… |
|---|---|
| "violates CCPA" | "presents elevated exposure under CCPA requirements" |
| "non-compliant with GDPR" | "disclosure gaps relative to GDPR expectations" |
| "illegal data sharing" | "data sharing practices with heightened regulatory exposure" |
| "in violation of" | "inconsistent with the requirements of" |
| "liable for penalties" | "exposure to potential enforcement action" |
| "guilty of mishandling" | "practices presenting elevated risk indicators" |
| "breach of law" | "departure from regulatory expectations" |
| "unlawful processing" | "processing activities with elevated scrutiny indicators" |

**Exposure-language pattern:** `[practice] + [presents / indicates / suggests] + [exposure level] + [relative to / under] + [standard / regulation]`. E.g. "The retention disclosure **presents elevated exposure** relative to CPPA expectations."

**Confidence caveats** (tie to VCI, §5): VCI 40–59 → "Based on available data (confidence: moderate)…"; VCI < 40 → route to review, never present as definitive; small cohort → "Benchmarked against [n] peers as of [date] (small cohort; interpret with caution)."

**Source-excerpt exception:** verbatim quotes from enforcement records / regulatory guidance / notices may contain banned terms **only** when quoted, tagged `[source: …]`, and attributed — the ban is on *generated* prose, not cited evidence. Full extensible list: `config/banned_terms.txt`; enforcement in `app/services/guardrail.py`.

## 3. The four products (one engine)

| # | Product | Delivery | Refresh | Tier / price |
|---|---|---|---|---|
| 1 | Privacy Notice Intelligence Assessment | 12-section reproducible report + PDF + portal | At assessment; snapshot frozen | T1: $500–$2,000/mo |
| 2 | GRC / Continuous Monitoring Platform | Dashboard, alerts, change feed, portfolio, tasks | Continuous/scheduled | T2: $2,000–$10,000/mo |
| 3 | White-Label Intelligence | Partner portal, APIs, anonymized feeds, branded reports | Monthly/quarterly per SLA | T3: $25K+/yr, custom |
| 4 | Quarterly Global Privacy Intelligence Report | Public editorial publication + data appendix | Quarterly frozen snapshot | Marketing engine / subscription |

All four consume the same `derived_data_item` objects (single intelligence source of truth). Presentation layers never recalculate.

## 4. Target customers & personas (US-first, Phase 1)

Primary: enterprise privacy/legal/compliance teams, consulting & advisory firms (white-label channel), SaaS, healthcare, financial services, retail. Secondary: law firms (bulk scans), audit firms, regulators/policy analysts, insurers, M&A diligence, trade associations.

Key persona → interface implications: CPO wants executive dashboard + board-ready PDF; GC wants clause-level evidence; GRC manager wants tasks/owners/audit trail; regulator wants sector scans; law firm wants bulk risk queues; partner wants branded workspaces. → The UI must support **Executive vs Analyst modes** (the Analyst/Advisor dual-voice model is the MVP expression of this).

## 5. SME review gate & gate modes

- **Gate modes** (platform setting): `instant_draft` (report available immediately with gold DRAFT watermark), `expert_review` (report held until SME approves; teal Reproducible mark on approval). Client-shippable deliverables use `expert_review`.
- SME actions per finding: **Confirm / Edit / Dismiss**. Dismissed findings drop from client reports. All actions captured as `training_label` rows (flywheel for model improvement).
- **De-identification gate:** exemplar clauses cannot be approved while names/emails/URLs/custom tokens remain; one-click REDACTED replacement; category shown per flag.
- **Confidence routing:** VCI < 40 → suppress or route to review; 40–59 → caution label; low-confidence + high-severity → mandatory review.

## 6. Data handling & trust commitments

- Customer notices are customer-scoped; benchmark/white-label/quarterly outputs use aggregated, anonymized data with minimum-sample suppression.
- **LLM endpoint policy.** MVP runs a **local LLM (Ollama, `OLLAMA_BASE_URL`)** — no notice text leaves the machine. Any move to a **hosted** endpoint (`HOSTED_QWEN_BASE_URL`) requires a provider contractually configured for **zero-retention / no-training** (e.g. Together AI, Fireworks AI, Azure AI under a DPA) and a policy review *first*. In all modes: send only the specific clause text needed (never whole notices, batches, or org metadata); **log that text was sent** (timestamp, char count, task type) but **never the content**; API keys never logged. `HOSTED_QWEN_API_KEY` is a secret (.env only). This is the standing data-handling policy (formerly the separate DATA_HANDLING.md; see also AGENTS.md §3).
- SSRF-protected URL intake (backend validates; UI shows "verified source", never names the attack class).
- Trust surface roadmap: Trust Center, Security, Methodology, FAQ pages; every public statistic must have documented source, formula, refresh cadence (data traceability matrix).

## 7. Operational cadences (SLA targets)

| Data family | Cadence | Freshness target |
|---|---|---|
| Customer assessments | On upload | Immediate |
| Monitored notices | Daily/weekly by plan | ≤24h of crawl |
| Peer notices | Monthly (weekly watchlists) | Monthly |
| FTC/CPPA/State AG enforcement | Weekly + event-driven | ≤5 business days |
| State law catalog | Monthly + effective-date tracking | ≤5 business days |
| AI governance sources | Monthly + events | ≤10 business days |
| Benchmark rebuild | Monthly; quarterly publication freeze | Monthly |
| Formula/model governance | Quarterly or on approval | Versioned, backward compatible |

## 8. Partnership & ownership context

TeclusionAI: technology, infrastructure, capital, security. Solrac Consulting: strategy, brand, GTM, partnerships, domain authority. Gross-revenue allocation model. 3-year plan: Y1 $250K–$1M ARR (5–15 customers, 2–3 partners) → Y2 $2M–$5M → Y3 $8M–$15M+ (acquisition-ready).

## 9. IP posture

The methodology is the asset. Seven patent-supportive families (dynamic benchmark modeling, RSS modeling, OSI normalization, normalization engine, compound risk, explainable lineage, knowledge graph). Engineering must maintain versioned architecture/formula/workflow documentation — this spec repo is part of that record.

## 10. Changelog
- 1.2 (2026-07-15): §2 absorbed the LANGUAGE.md guardrail assets (approved-alternative mapping, exposure-language pattern, confidence caveats, source-excerpt exception). §6 absorbed the DATA_HANDLING.md hosted-endpoint policy (zero-retention/no-training, `HOSTED_QWEN_*` env contract, log-that-not-what) — the standalone DATA_HANDLING.md is retired to docs/old-docs/, this section is now the source of truth.
- 1.1 (2026-07-15): Guardrail banned-term list extended (unlawful, breach of law, guilty, liable, violation of) and "classifies and phrases, never invents" rule absorbed from legacy AGENTS.md.
- 1.0: consolidated from Business Plan, Brand Guide, Use Case Catalog, VICBNF principles, Website Review.
