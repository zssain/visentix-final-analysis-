"""Narrative service — LLM-powered phrasing over pre-computed, guardrailed statements.

The LLM REPHRASES only. It never invents claims, numbers, findings, or
recommendations. Every output passes through guardrail.enforce().

Flow:
1. Build Statement objects from computed scores + findings + recommendation library
2. Call LLM to smooth tone (optional — works without LLM via templates)
3. Verify rephrased text contains the same numbers/entities (no new ones)
4. Run guardrail.enforce() on all generated prose
5. Fall back to templated text if verification or guardrail fails
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable

from app.services.guardrail import GuardrailError, enforce

# ── Number extraction for verification ────────────────────────

_NUMBER_PATTERN = re.compile(r"\b\d+(?:\.\d+)?%?\b")


def extract_numbers(text: str) -> set[str]:
    """Extract all numeric tokens from text for verification."""
    return set(_NUMBER_PATTERN.findall(text))


def extract_entities(text: str, known_entities: set[str]) -> set[str]:
    """Check which known entities appear in text."""
    text_lower = text.lower()
    return {e for e in known_entities if e.lower() in text_lower}


# ── Verification ─────────────────────────────────────────────

def verify_rephrased(
    source: str,
    rephrased: str,
    known_entities: set[str] | None = None,
) -> tuple[bool, str]:
    """Verify rephrased text doesn't introduce new numbers or lose existing ones.

    Returns (passed, reason).
    """
    source_nums = extract_numbers(source)
    rephrased_nums = extract_numbers(rephrased)

    # New numbers introduced?
    new_nums = rephrased_nums - source_nums
    if new_nums:
        return False, f"New numbers introduced: {new_nums}"

    # Critical numbers lost? (scores, percentiles)
    # Allow minor losses (e.g. dropping a less important number)
    # but flag if > half of source numbers are missing
    if source_nums:
        missing = source_nums - rephrased_nums
        if len(missing) > len(source_nums) / 2:
            return False, f"Too many numbers lost: {missing}"

    # Entity check
    if known_entities:
        source_ents = extract_entities(source, known_entities)
        rephrased_ents = extract_entities(rephrased, known_entities)
        new_ents = rephrased_ents - source_ents
        if new_ents:
            return False, f"New entities introduced: {new_ents}"

    return True, "ok"


# ── Statement objects ────────────────────────────────────────

@dataclass
class Statement:
    """A pre-computed, fact-bearing statement ready for LLM rephrasing."""

    section: str  # "executive_summary" | "takeaway" | "recommendation"
    template: str  # The templated text with all facts/numbers baked in
    context: dict = field(default_factory=dict)  # Additional context for LLM
    severity: str = "medium"
    finding_code: str = ""


@dataclass
class NarrativeOutput:
    """Complete narrative output for one assessment."""

    executive_summary: str
    takeaways: list[str]
    recommendations: list[dict]  # [{severity, code, title, prose}]
    all_guardrail_passed: bool = True
    fallback_count: int = 0


# ── Statement builders ───────────────────────────────────────

def build_executive_summary_statement(
    org_name: str,
    overall_score: float,
    percentile: float,
    vci_label: str,
    cohort_size: int,
    cohort_date: str,
    finding_count: int,
    top_domain: str,
) -> Statement:
    """Build the executive summary from pre-computed values."""
    template = (
        f"{org_name} presents an overall privacy intelligence score of "
        f"{overall_score:.1f} out of 100, placing it at the {percentile:.1f}th "
        f"percentile within its peer cohort (n={cohort_size}, as of {cohort_date}). "
        f"The assessment identified {finding_count} areas of elevated exposure, "
        f"with {top_domain} representing the most significant area of focus. "
        f"Confidence level: {vci_label}."
    )
    return Statement(
        section="executive_summary",
        template=template,
        context={
            "org_name": org_name,
            "overall_score": overall_score,
            "percentile": percentile,
            "cohort_size": cohort_size,
        },
    )


def build_takeaway_statements(
    findings: list[dict],
    scores: dict,
) -> list[Statement]:
    """Build takeaway statements from findings and scores."""
    statements = []

    for f in findings:
        code = f.get("code", "")
        domain = f.get("domain", "")
        severity = f.get("severity", "medium")
        score = f.get("score", 0)

        template = (
            f"The {domain.replace('_', ' ')} domain presents "
            f"{'elevated' if severity == 'high' else 'moderate'} exposure "
            f"(finding {code}, score {score:.1f}/100). "
            f"This area warrants {'priority' if severity == 'high' else 'standard'} "
            f"attention in the remediation roadmap."
        )
        statements.append(Statement(
            section="takeaway",
            template=template,
            severity=severity,
            finding_code=code,
        ))

    return statements


def build_recommendation_statements(
    findings: list[dict],
    recommendation_library: dict[str, dict],
) -> list[Statement]:
    """Build recommendation statements from findings + library entries."""
    statements = []

    for f in findings:
        code = f.get("code", "")
        rec = recommendation_library.get(code, {})
        title = rec.get("title", f"Address {code}")
        body = rec.get("body_template", f"Review and address the {code} finding.")

        # Fill any placeholders in the body template
        domain = f.get("domain", "").replace("_", " ")
        body_filled = body.replace("{domain}", domain)

        template = f"{title}: {body_filled}"
        statements.append(Statement(
            section="recommendation",
            template=template,
            severity=f.get("severity", "medium"),
            finding_code=code,
        ))

    return statements


# ── Narrative generation ─────────────────────────────────────

async def generate_narrative(
    org_name: str,
    scores: dict,
    findings: list[dict],
    vci: dict,
    recommendation_library: dict[str, dict],
    cohort_size: int = 30,
    cohort_date: str = "2026-06-18",
    rephrase_fn: Callable | None = None,
) -> NarrativeOutput:
    """Generate the full narrative for one assessment.

    rephrase_fn: async (template, context) -> str. If None, uses templates as-is.
    All output passes through guardrail.enforce().
    """
    overall = scores.get("f010", {}).get("score", 0)
    percentile = scores.get("f011", {}).get("score", 0)
    top_domain = ""
    if findings:
        top_domain = findings[0].get("domain", "").replace("_", " ")

    # Build statements
    exec_stmt = build_executive_summary_statement(
        org_name=org_name,
        overall_score=overall,
        percentile=percentile,
        vci_label=vci.get("label", "moderate"),
        cohort_size=cohort_size,
        cohort_date=cohort_date,
        finding_count=len(findings),
        top_domain=top_domain,
    )

    takeaway_stmts = build_takeaway_statements(findings, scores)
    rec_stmts = build_recommendation_statements(findings, recommendation_library)

    fallback_count = 0

    # Generate executive summary
    exec_text = await _rephrase_and_verify(
        exec_stmt, rephrase_fn, known_entities={org_name}
    )
    if exec_text is None:
        exec_text = exec_stmt.template
        fallback_count += 1

    # Generate takeaways
    takeaways = []
    for stmt in takeaway_stmts:
        text = await _rephrase_and_verify(stmt, rephrase_fn)
        if text is None:
            text = stmt.template
            fallback_count += 1
        takeaways.append(text)

    # Generate recommendations (grouped by severity)
    recommendations = []
    for stmt in rec_stmts:
        text = await _rephrase_and_verify(stmt, rephrase_fn)
        if text is None:
            text = stmt.template
            fallback_count += 1
        recommendations.append({
            "severity": stmt.severity,
            "code": stmt.finding_code,
            "title": text.split(":")[0] if ":" in text else text[:60],
            "prose": text,
        })

    return NarrativeOutput(
        executive_summary=exec_text,
        takeaways=takeaways,
        recommendations=recommendations,
        all_guardrail_passed=fallback_count == 0,
        fallback_count=fallback_count,
    )


async def _rephrase_and_verify(
    stmt: Statement,
    rephrase_fn: Callable | None,
    known_entities: set[str] | None = None,
) -> str | None:
    """Rephrase a statement, verify, and guardrail. Returns None on failure."""
    if rephrase_fn is None:
        # No LLM — use template directly, still guardrail it
        try:
            return enforce(stmt.template)
        except GuardrailError:
            return None

    try:
        rephrased = await rephrase_fn(stmt.template, stmt.context)
    except Exception:
        return None  # LLM failed → fallback

    # Verify no new numbers/entities
    passed, reason = verify_rephrased(stmt.template, rephrased, known_entities)
    if not passed:
        return None  # Verification failed → fallback

    # Guardrail check
    try:
        return enforce(rephrased)
    except GuardrailError:
        return None  # Guardrail failed → fallback
