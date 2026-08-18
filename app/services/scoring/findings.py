"""Deterministic finding selection from the fixed finding_type catalog.

Rules select findings by matching clause categories to finding_type domains.
Same inputs MUST yield the same findings (reproducible). The model never
creates or names a finding — catalog selection only.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

# Domain → finding_type code mapping (mirrors the catalog)
DOMAIN_TO_FINDING: dict[str, str] = {
    "ai_automated_decisions": "AI-004",
    "tracking_cookies": "TRK-007",
    "data_sharing": "SH-002",
    "retention": "RT-003",
    "consumer_rights": "CR-001",
    "sensitive_data": "SEC-002",
    "cross_border": "XB-001",
    "other": "DC-005",
    "security": "SEC-006",  # Phase 2 — security-practices disclosure (intelligence-logic §4)
}

# Severity from catalog (read at runtime, but defaults for pure-function tests)
DEFAULT_SEVERITY: dict[str, str] = {
    "AI-004": "high",
    "TRK-007": "medium",
    "SH-002": "high",
    "RT-003": "medium",
    "CR-001": "high",
    "DC-005": "medium",
    "SEC-002": "high",
    "XB-001": "medium",
    "SEC-006": "high",  # Phase 2 — security-practices disclosure gap
}

# Score thresholds for triggering a finding per domain
# A finding fires when: domain clauses exist AND (score < maturity threshold
# OR ambiguity > ambiguity threshold)
MATURITY_THRESHOLD = 70.0  # below this → finding triggered
AMBIGUITY_THRESHOLD = 0.05  # above this → finding triggered


@dataclass
class FindingInput:
    """All data needed to generate findings for one notice."""

    organization_id: str
    notice_id: str
    clause_categories: Counter  # {domain: count}
    clause_ids_by_domain: dict[str, list[str]]  # {domain: [clause_id, ...]}
    domain_scores: dict[str, float]  # computed scores per domain (F-005 breakdown)
    avg_ambiguity_by_domain: dict[str, float]
    enforcement_matches: list[dict]  # [{enforcement_id, domain, similarity}]
    vci_score: float = 50.0
    formula_version_id: str = "F-002_v1"

    # Finding type catalog (loaded from DB)
    finding_types: dict[str, dict] = field(default_factory=dict)
    recommendations: dict[str, str] = field(default_factory=dict)  # code → rec_id


@dataclass
class FindingResult:
    """One generated finding."""

    finding_type_code: str
    domain: str
    severity: str
    score: float
    confidence_score: float
    triggering_clause_ids: list[str]
    enforcement_ids: list[str]
    recommendation_id: str | None
    formula_version_id: str


def select_findings(inp: FindingInput) -> list[FindingResult]:
    """Deterministically select findings from the catalog.

    Rules (reproducible — same inputs → same findings):
    1. For each domain with clauses, check if a finding should trigger.
    2. A finding triggers when the domain has low maturity or high ambiguity.
    3. Finding type code comes from DOMAIN_TO_FINDING (fixed catalog).
    4. Score = 100 - domain_maturity (higher = worse exposure).
    """
    results = []
    seen_codes = set()

    # Sort domains for deterministic ordering
    for domain in sorted(inp.clause_categories.keys()):
        if domain == "other":
            continue  # DC-005 only triggers on specific conditions below

        code = DOMAIN_TO_FINDING.get(domain)
        if not code or code in seen_codes:
            continue

        clause_count = inp.clause_categories[domain]
        if clause_count == 0:
            continue

        # Check triggers
        maturity = inp.domain_scores.get(domain, 50.0)
        ambiguity = inp.avg_ambiguity_by_domain.get(domain, 0.0)

        triggered = maturity < MATURITY_THRESHOLD or ambiguity > AMBIGUITY_THRESHOLD

        if not triggered:
            continue

        severity = DEFAULT_SEVERITY.get(code, "medium")
        if code in inp.finding_types:
            severity = inp.finding_types[code].get("default_severity", severity)

        # Score: exposure = 100 - maturity (capped 0-100)
        finding_score = round(max(0.0, min(100.0, 100.0 - maturity)), 2)

        # Get triggering clauses (all in this domain)
        triggering = inp.clause_ids_by_domain.get(domain, [])

        # Get related enforcement matches
        enf_ids = [
            e["enforcement_id"] for e in inp.enforcement_matches
            if domain in (e.get("domain") or e.get("issue_tags") or [])
        ][:5]  # cap at 5

        # Get linked recommendation
        rec_id = inp.recommendations.get(code)

        results.append(FindingResult(
            finding_type_code=code,
            domain=domain,
            severity=severity,
            score=finding_score,
            confidence_score=inp.vci_score / 100,
            triggering_clause_ids=triggering[:20],  # cap for sanity
            enforcement_ids=enf_ids,
            recommendation_id=rec_id,
            formula_version_id=inp.formula_version_id,
        ))
        seen_codes.add(code)

    # DC-005: fires if total clause coverage is thin (< 4 domains)
    non_other = {d for d in inp.clause_categories if d != "other" and inp.clause_categories[d] > 0}
    if len(non_other) < 4 and "DC-005" not in seen_codes and inp.clause_categories.get("other", 0) > 0:
        results.append(FindingResult(
            finding_type_code="DC-005",
            domain="other",
            severity="medium",
            score=round(max(0, (4 - len(non_other)) * 25.0), 2),
            confidence_score=inp.vci_score / 100,
            triggering_clause_ids=inp.clause_ids_by_domain.get("other", [])[:10],
            enforcement_ids=[],
            recommendation_id=inp.recommendations.get("DC-005"),
            formula_version_id=inp.formula_version_id,
        ))

    return results
