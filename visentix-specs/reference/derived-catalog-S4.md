# Derived Intelligence Catalog — Service 4 (Quarterly Report) rows

**Source:** Visentix Derived Intelligence Catalog v1.0, Service 4.
**Recorded verbatim** (owner-supplied, 2026-07-28) as the authoritative reference for F21. Do not paraphrase these formulas; F21 metrics cite these row IDs.

| ID | Name | Formula (verbatim) |
|---|---|---|
| **S4-001** | Organizations Analyzed | count distinct orgs in eligible quarterly benchmark snapshot after quality filters and anonymization thresholds. |
| **S4-002** | Privacy Clauses Analyzed | count ENT-CLAUSE records in quarterly snapshot with `extraction_confidence >= threshold`. |
| **S4-003** | Industries Benchmarked | count distinct benchmark industries where `sample_size >= minimum threshold`. |
| **S4-004** | Jurisdictions Covered | count jurisdiction records with active requirement/regulator mapping in quarter. |
| **S4-005** | Disclosure Maturity Index | average **F-005** across eligible orgs, weighted by source confidence and industry representation. |
| **S4-006** | AI Transparency Index | average **F-007** across AI-relevant notices, weighted by industry and source confidence. |
| **S4-007** | Consumer Rights Clarity Score | average rights clarity across rights clauses; penalize missing rights, fragmented mechanisms, vague process language. |
| **S4-018** | Top Enforcement Theme Share | `count(theme_records) / total_topic_classified_records × 100`. |

## F21 v1 scope decisions (owner-approved 2026-07-28)
- **In scope for the v1 BASELINE:** S4-001, S4-002, S4-003, S4-004, S4-005, S4-006, S4-018 + a **Top Disclosure Gaps** report aggregate (finding-frequency section; not a numbered Service-4 formula).
- **S4-007** — **DEFERRED in v1**: no live consumer-rights-clarity formula exists (verified — no `F-xxx` / `derived_data_item.object_type` for rights clarity; the described penalized average is unbuilt). Re-include when the formula ships.
- **S4-008…S4-017, S4-019…S4-022** — DEFERRED; missing inputs enumerated in F21-quarterly.md (prior-quarter snapshot for QoQ, per-industry n≥10, historical trend, compound grouping, approved exemplars, aggregate-VCI formula).
- **S4-018 deliberate deviation (Rule 3 tightening):** the catalog's `total_topic_classified_records` denominator is computed over **RESOLVED `enforcement_record` only** — F21 is **stricter** than the catalog (unresolved records, 623 rows, are pending signals not outcomes and never enter a public share). This narrowing is intentional and documented in the methodology block.
- **S4-002 threshold:** honor `extraction_confidence >= threshold` using an existing config value if one exists; otherwise count **non-noise clauses** as the v1 proxy and state that explicitly in the methodology block (no invented cutoff).
- **S4-005 / S4-006 weighting (acting-SME approved, PROVISIONAL 2026-07-28):** confidence-weighted mean per industry → equal-industry average over industries with `n>=10`. **Revisit trigger:** re-evaluate the industry weighting when industries at `n>=10` exceed 5, OR after F17 baselines exist — whichever comes first.
