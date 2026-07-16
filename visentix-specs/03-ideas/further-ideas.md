# Further Ideas — Parked, Future-State & Patent-Adjacent

**Rule:** nothing here is committed. Promotion path: idea → feature spec in `02-features/` → foundation amendments → implementation.

## Near-term candidates (post-R2)

- ~~**Framework Crosswalk explorer**~~ — **graduated to [`02-features/F13-framework-crosswalk-explorer.md`](../02-features/F13-framework-crosswalk-explorer.md)** (2026-07-16). Shell UI shipped on mock citations; descriptive copy still pending OD-01 sign-off.
- **Reader registers** — Executive / Practitioner / Plain-language renderings of the same snapshot, both frozen (pending OD-02). Later: per-persona default registers (law firm vs CPO vs regulator).
- **Portfolio & remediation (GRC deepening)** — multi-brand variance maps, finding→task→owner workflow, control mapping, audit trail, monthly executive digest emails.
- ~~**Notice rewrite prompts**~~ — **graduated to [`02-features/F14-notice-rewrite-prompts.md`](../02-features/F14-notice-rewrite-prompts.md)** (2026-07-16). Trust Language Studio shell shipped on mock patterns; authored pattern library + SME sign-off still pending.
- ~~**Vendor due diligence mode**~~ — **graduated to [`02-features/F16-vendor-due-diligence.md`](../02-features/F16-vendor-due-diligence.md)** (2026-07-16). Intake→risk-approval→procurement-summary workflow shipped on mock vendors; vendor pipeline + persistence still pending.

## Medium-term (R4–R5)

- **Insurance underwriting API** — batch scoring, exposure tiers, underwriting memos (V3 use case).
- **M&A diligence mode** — fast target scan, red flags, confidential notes, data-room export.
- **Predictive enforcement intelligence** — regulator forecasting, enforcement-likelihood trajectories, disclosure trend forecasting (Intelligence Engine §12; requires multi-quarter corpus history).
- **Knowledge graph productization** — org/clause/regulator/enforcement/cohort as a queryable graph service; graph-native similarity exploration UI.
- **AI-assisted drafting guidance** — automated disclosure recommendations grounded in top-quartile exemplar patterns (heavy guardrail review before any build).
- **Cross-market benchmarking** — international expansion beyond US-first Phase 1 (EU/UK sources are already tagged future-state in the source model).
- **Industry maturity indexing** — published Visentix indices as citable market references (analyst/media strategy).

## Platform/engineering ideas

- **Managed-LLM tier** — optional hosted-model path for higher-quality narratives where a customer's data-handling agreement allows; local Ollama remains the default; requires DATA_HANDLING.md revision + per-tenant model policy.
- **Embedding upgrade path** — migration plan from MiniLM-L6 to a stronger model with full re-embedding + benchmark recalibration + version bump.
- **Eval harness for the intelligence layer** — golden-set notices with expected clause classifications and score ranges; run on every formula/model version change (extends the test-suite discipline to model quality).
- **Spec-agent CI** — a CI job where an AI agent checks each PR against its referenced feature spec's acceptance criteria and the foundation guardrails (banned-term scan on any string literals, hardcoded-value scan per DIR-008).
- ~~**Public Trust Center**~~ — **graduated to [`02-features/F15-public-trust-center.md`](../02-features/F15-public-trust-center.md)** (2026-07-16). Public `/trust` page shipped on mock trust-metrics; real metrics feed still pending.

## Patent-supportive documentation queue
Keep architecture records current for: dynamic benchmark population modeling · regulatory scrutiny modeling · organizational sophistication normalization · privacy notice normalization engine · compound privacy risk modeling · explainable intelligence lineage · privacy intelligence knowledge graph. Each formula/model version change should note whether it strengthens a claim direction.
