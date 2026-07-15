# Words We Use — The Visentix Glossary

Keep this open in a tab. When developers, the expert, and customers use the same word to mean the same thing, half our problems disappear. Terms are grouped by theme, not alphabetized, so related ideas sit together.

---

## The raw material

**Privacy notice** — the public page or PDF where a company explains what data it collects and what it does with it. The thing we analyze. (People also say "privacy policy" — same thing for our purposes.)

**Clause** — one individual statement inside a notice, e.g. "we may share your information with trusted partners." The smallest unit we work with. Every clause gets an ID like `C-118`.

**Domain** — one of the eight topic buckets a clause can belong to: Consumer Rights (CR), Data Collection (DC), Sharing (SH), Retention (RT), AI (AI), Security (SEC), Tracking (TRK), Cross-Border (XB).

**Source / source record** — anything we ingest: a notice, a regulator announcement, an enforcement action, a lawsuit. Every source is stamped with where it came from, when we captured it, and how reliable it is.

**Corpus** — our whole library of collected notices and sources. The bigger and cleaner the corpus, the smarter the benchmarks.

**Enforcement action** — a regulator formally going after a company (an FTC order, a state attorney general settlement, etc.). We study these to learn what regulators actually care about.

## Comparing companies

**Cohort / peer group / benchmark population** — three names for the same thing: the set of genuinely similar companies we compare a customer against. Built from industry plus several "how similar are they really" dimensions.

**Profile** — our multi-dimensional description of a company: industry, expected regulatory attention, data sensitivity, program maturity, organizational sophistication, enforcement history, AI maturity. The profile decides the cohort.

**Normalization** — the fairness adjustment. Within a cohort, more-similar peers count more and less-similar peers count less, so comparisons are never crude averages.

**Benchmark percentile** — where a company ranks inside its cohort. "42nd percentile" means 58% of true peers look stronger on that measure.

**Exemplar** — a real, anonymized clause from a strong peer, used in reports to show "here's what good looks like." Exemplars must pass de-identification and expert approval before use.

**Cohort size (n)** — how many peers are in the comparison group. We always show it honestly. Below a threshold we label the comparison "low confidence."

## Scores and findings

**Finding** — one specific weakness or observation, tied to specific clauses. E.g. "third-party sharing is disclosed vaguely."

**Finding code** — the ID for a finding type, like `TRK-007`. All codes live in the **Codex**, our governed dictionary — hover any code in the product and its definition pops up.

**Formula (F-001 … F-014)** — the fixed, versioned recipes that turn data into scores. Deterministic: same ingredients, same result, always.

**Exposure score** — how much attention/risk a weakness could attract. **Lower is better.** (This trips people up: on exposure charts, a falling line is good news, so we color it teal.)

**Maturity score** — how complete and well-developed a disclosure is. Higher is better.

**Compound risk** — when several weaknesses interact and amplify each other (e.g. vague AI language *plus* profiling *plus* weak opt-outs is worse than the three separately).

**VCI (Visentix Confidence Index)** — the 0–100 confidence rating attached to *every* score. Below 40 we suppress the score rather than show a shaky number.

**Interpretive variance** — an honest label for how settled the legal world is on a topic. "Missing consumer-rights language" is high-consensus; "is this AI disclosure adequate?" is genuinely ambiguous, and we say so.

## Trust machinery

**Lineage** — the receipt behind a number. Click any score and the lineage drawer shows: which clause, which regulator concern, which cohort, which formula, what confidence, which snapshot.

**Snapshot** — the frozen, immutable record of a delivered report (ID like `S-2041`). Guarantees the same report is byte-identical forever.

**Provenance ribbon** — the strip at the top of every report/dashboard showing the snapshot ID, formula version, freeze date, and whether it's a draft or approved.

**Draft vs. approved** — a report starts as a *draft* (gold watermark, "pending expert review"). After the expert clears the review queue, it becomes *approved* (teal "Reproducible" mark). Only approved reports go to paying clients.

**The Guardrail** — our absolute rule: no legal verdicts. Never "compliant," "violation," or "illegal." Always exposure, maturity, likelihood, benchmark position, confidence. A filter enforces this on every generated sentence, and the small "Intelligence, not legal advice" mark appears on findings and reports.

## People and process

**SME (subject-matter expert)** — our privacy/security expert. Reviews every finding before delivery; the human judgment in the product.

**Workbench** — the internal screen where the SME reviews findings: Confirm / Edit / Dismiss.

**Gate mode** — a platform switch. `expert_review`: reports are held until the SME approves (client mode). `instant_draft`: reports appear immediately as watermarked drafts (demo mode).

**Training label** — every SME confirm/edit/dismiss is saved. This is how the system learns to think more like our expert over time.

**De-identification (de-id)** — scrubbing names, emails, and URLs out of any language that will be reused. The system blocks approval until clean.

**Analyst view / Advisor view** — the two faces of every finding. Analyst = the machine's precise reading (grids, numbers). Advisor = the human-voiced note (warm prose, currently signed "The Visentix Privacy Desk"). One switch flips between them.

**Assessment** — one full run of the pipeline for one notice: intake through report.

**Monitoring / change feed / alert** — the ongoing watching. Changes worth knowing about appear in the feed; serious ones become alerts.

## Words we deliberately avoid

- **"Compliant / non-compliant / violation"** — legal verdicts. Banned everywhere.
- **"Audit"** — we're intelligence, not an audit; the word implies assurances we don't give.
- **"Score went up = good"** — depends on the score! Exposure down = good. Say "improved" or "worsened," never just "up/down," when talking to customers.
- Security jargon in customer-facing screens (e.g. naming attack types). The protection is real; the UI stays calm and plain.
