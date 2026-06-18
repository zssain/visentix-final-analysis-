# Visentix Approved Language Guide

## Principle

Visentix provides privacy **intelligence** — exposure assessments, maturity
benchmarks, and likelihood estimates. It NEVER renders legal verdicts.

All customer-facing text must use **exposure/likelihood language**. The guardrail
(`app/services/guardrail.py`) hard-fails report generation if banned terms appear
in generated prose.

## Banned Terms (Never Use in Generated Prose)

| Banned Term | Why |
|---|---|
| violation | Legal conclusion |
| violates | Legal conclusion |
| illegal | Legal verdict |
| unlawful | Legal verdict |
| non-compliant / noncompliant | Compliance judgment |
| breach of law | Legal conclusion |
| guilty | Criminal verdict |
| liable | Legal liability finding |
| in violation of | Legal conclusion |
| found guilty | Criminal verdict |
| legally liable | Liability finding |

See `config/banned_terms.txt` for the full, extensible list.

## Approved Alternatives

| Instead of... | Use... |
|---|---|
| "violates CCPA" | "presents elevated exposure under CCPA requirements" |
| "non-compliant with GDPR" | "disclosure gaps relative to GDPR expectations" |
| "illegal data sharing" | "data sharing practices with heightened regulatory exposure" |
| "in violation of" | "inconsistent with the requirements of" |
| "liable for penalties" | "exposure to potential enforcement action" |
| "guilty of mishandling" | "practices presenting elevated risk indicators" |
| "breach of law" | "departure from regulatory expectations" |
| "unlawful processing" | "processing activities with elevated scrutiny indicators" |

## Pattern: Exposure Language

**Structure:** `[practice] + [presents/indicates/suggests] + [exposure level] + [relative to/under] + [standard/regulation]`

**Examples:**
- "The retention disclosure **presents elevated exposure** relative to CPPA expectations."
- "Data sharing practices **indicate heightened scrutiny risk** under FTC enforcement priorities."
- "The AI governance posture **suggests moderate maturity gaps** compared to peer benchmarks."
- "Cross-border transfer disclosures **show below-median completeness** within the cohort (n=30, as of 2026-06-18)."

## Source Excerpts

Verbatim quotes from enforcement records, regulatory guidance, or privacy notices
may contain banned terms. These are **allowed** when:
1. Enclosed in quotation marks (`"..."` or `'...'`)
2. Tagged with `[source: ...]`
3. Clearly attributed to the source

Example:
> The FTC stated that the company's practices constituted a "violation of Section 5"
> (source: FTC consent order, 2025).

The word "violation" is allowed here because it is a direct quote, not generated prose.

## Confidence Caveats

When VCI indicates reduced confidence, always include a caveat:
- VCI 40–59: "Based on available data (confidence: moderate)..."
- VCI < 40: Route to review — do not present as definitive.
- Small cohort: "Benchmarked against [n] peers as of [date] (small cohort; interpret with caution)."
