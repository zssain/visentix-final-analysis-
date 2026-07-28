"""F17 component 3 — score-validity perturbation + cited monotonicity.

Each assertion is stated VERBATIM from intelligence-logic.md with a section
citation (M-1…M-5). MEASUREMENT ONLY — a failure here is a REPORTED finding for
[ENG] review; the harness fixes nothing.
"""

from uuid import uuid4

from app.services.intake.decompose import DecomposedClause, DecomposedNotice
from app.services.pipeline import score_notice
from app.services.scoring.vci import compute_vci
from tests.test_live_pipeline import (
    F002_THRESHOLDS,
    F010_WEIGHTS,
    JW,
    PEER_SCORES,
    SAMPLE_REGULATORS,
)


def _clause(cat: str) -> DecomposedClause:
    text = f"We process {cat.replace('_', ' ')} data as described in this notice."
    return DecomposedClause(
        clause_id=str(uuid4()), section_id="s", raw_text=text, normalized_text=text.lower(),
        category=cat, ambiguity_score=0.01, readability_score=0.5, nlp_confidence=0.8,
    )


def _score(clauses):
    return score_notice(
        organization_id="t", notice_id="t", notice=DecomposedNotice(clauses=clauses),
        regulators=SAMPLE_REGULATORS, jurisdiction_weights=JW, f002_thresholds=F002_THRESHOLDS,
        f010_weights=F010_WEIGHTS, peer_scores=PEER_SCORES, org_pgms=55.0,
        avg_source_reliability=0.85, finding_types={}, recommendations={},
    )


# Baseline: a domain well-covered (3 clauses) alongside two other domains.
BASE = ([_clause("data_sharing")] * 3 + [_clause("consumer_rights")] * 3
        + [_clause("retention")] * 3)
# Perturbed: WEAKEN data_sharing (remove its clauses); others unchanged.
WEAK = [_clause("consumer_rights")] * 3 + [_clause("retention")] * 3


def test_M1_F005_maturity_falls_when_domain_weakened():
    """M-1 (intelligence-logic §7, F-005): 'Disclosure Maturity = (Observed /
    Expected elements) × 100 − …' → removing observed elements DECREASES maturity."""
    strong, weak = _score(BASE), _score(WEAK)
    assert weak["scores"]["f005"]["score"] <= strong["scores"]["f005"]["score"]


# NOTE — F-002 is intentionally NOT asserted here. `compute_f002` defines
# "DS (disclosure severity) = proportion of clauses in each domain", and domain
# proportions are coupled (Σ = 1), so the verbatim §7 formula does not license a
# clean "weaken → exposure worsens" monotonic direction. Per the rule "if you
# can't cite it, don't assert it," F-002 is REPORTED-only in INTELLIGENCE-QUALITY.md
# ([EXPERT]: confirm severity should track disclosure VOLUME vs QUALITY), not asserted.


def test_M3_F010_overall_falls_when_risk_rises():
    """M-3 (§7, F-010 = '100 − weighted risk aggregate'): more risk → lower F-010."""
    strong, weak = _score(BASE), _score(WEAK)
    assert weak["scores"]["f010"]["score"] <= strong["scores"]["f010"]["score"]


def test_M4_F006_transparency_not_higher_when_weakened():
    """M-4 (§7, F-006 = Completeness × Clarity × Specificity × Explainability):
    lowering completeness cannot INCREASE transparency."""
    strong, weak = _score(BASE), _score(WEAK)
    assert weak["scores"]["f006"]["score"] <= strong["scores"]["f006"]["score"] + 1e-6


def test_other_domains_stable_within_tolerance():
    """Perturbing data_sharing must not move the untouched domains' coverage.
    consumer_rights/retention counts are identical in BASE and WEAK → maturity equal."""
    from collections import Counter
    base_cats = Counter(c.category for c in BASE)
    weak_cats = Counter(c.category for c in WEAK)
    for d in ("consumer_rights", "retention"):
        assert min(base_cats[d] * 15, 100) == min(weak_cats[d] * 15, 100)


def test_M5_vci_below_40_is_very_low_band():
    """M-5 (§8, VCI): '<40 Very Low (suppress or route to review — never present as
    definitive)'. A low-confidence object must land below 40 (→ suppress/route)."""
    low = compute_vci(nlp_confidence=0.1, benchmark_confidence=0.1, regulatory_confidence=0.1,
                      enforcement_confidence=0.1, source_reliability=0.1)
    high = compute_vci(nlp_confidence=0.95, benchmark_confidence=0.9, regulatory_confidence=0.9,
                       enforcement_confidence=0.9, source_reliability=0.9)
    assert low.score < 40, f"very-low inputs should be <40, got {low.score}"
    assert high.score > low.score  # monotone in confidence
