"""Deterministic Organization Intelligence Profiler.

Computes 7 dimensions per org from existing classified data + firmographics.
NO model calls — all scores are formula-driven from the data.

Dimensions:
    IC    — Industry Classification (mapped taxonomy)
    RSS   — Regulatory Scrutiny Score (0-100)
    PGMS  — Privacy Governance Maturity Score (0-100)
    OSI   — Organizational Sophistication Index (0-100)
    DSI   — Data Sensitivity Index (0-100)
    EHP   — Enforcement History Profile (0-100)
    AIGMS — AI Governance Maturity Score (0-100)
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

# ── Industry mapping (VICBNF taxonomy) ────────────────────────
# Maps raw organization.industry to canonical VICBNF categories.
# "logistics" has no direct VICBNF category — mapped to "supply_chain_services".
INDUSTRY_MAP: dict[str, str] = {
    "fintech": "financial_services",
    "manufacturing": "industrial_manufacturing",
    "logistics": "supply_chain_services",  # known gap — closest VICBNF category
    "healthcare": "healthcare",
    "technology": "technology",
    "retail": "retail_consumer",
    "telecom": "telecommunications",
    "education": "education",
}

# Industry sensitivity weights (higher = more regulatory scrutiny expected)
INDUSTRY_SENSITIVITY: dict[str, float] = {
    "financial_services": 0.85,
    "healthcare": 0.90,
    "technology": 0.70,
    "industrial_manufacturing": 0.45,
    "supply_chain_services": 0.40,
    "retail_consumer": 0.60,
    "telecommunications": 0.75,
    "education": 0.65,
}
DEFAULT_INDUSTRY_SENSITIVITY = 0.50

# Clause category weights for DSI
DSI_CATEGORY_WEIGHTS: dict[str, float] = {
    "sensitive_data": 1.0,
    "children_teens": 0.9,
    "ai_automated_decisions": 0.8,
    "cross_border": 0.6,
    "data_sharing": 0.5,
    "retention": 0.4,
    "tracking_cookies": 0.3,
    "consumer_rights": 0.2,
    "other": 0.0,
}

# Governance signal categories for PGMS
GOVERNANCE_SIGNALS = {
    "consumer_rights": 0.30,
    "retention": 0.20,
    "cross_border": 0.15,
    "data_sharing": 0.15,
    "tracking_cookies": 0.10,
    "sensitive_data": 0.10,
}

# Tier thresholds (from F-002_v1)
TIER_THRESHOLDS = {
    "low": (0, 24),
    "moderate": (25, 49),
    "elevated": (50, 74),
    "high": (75, 100),
}

# Size scoring for OSI
SIZE_SCORES = {
    "large": 70,
    "medium": 50,
    "small": 30,
}


def score_to_tier(score: float) -> str:
    """Convert a 0-100 score to a tier label."""
    for tier, (lo, hi) in TIER_THRESHOLDS.items():
        if lo <= score <= hi:
            return tier
    return "high" if score > 100 else "low"


@dataclass
class OrgData:
    """All data needed to compute a profile for one org."""

    organization_id: str
    name: str
    industry: str
    size: str
    geography: str
    public_private: str | None

    clause_categories: Counter = field(default_factory=Counter)
    total_clauses: int = 0
    has_notice: bool = False

    enforcement_count: int = 0
    total_penalty_usd: float = 0.0
    enforcement_regulators: list[str] = field(default_factory=list)

    regulator_weights: dict[str, float] = field(default_factory=dict)


@dataclass
class ProfileResult:
    """Computed profile for one org."""

    organization_id: str
    ic: str  # mapped industry classification
    ic_raw: str  # original industry value
    rss: float
    pgms: float
    osi: float
    dsi: float
    ehp: float
    aigms: float
    confidence_score: float
    tiers: dict[str, str] = field(default_factory=dict)

    @property
    def scores_dict(self) -> dict[str, float]:
        return {
            "ic": hash(self.ic) % 100,  # IC is categorical, store numeric proxy
            "rss": self.rss,
            "pgms": self.pgms,
            "osi": self.osi,
            "dsi": self.dsi,
            "ehp": self.ehp,
            "aigms": self.aigms,
        }


def compute_ic(data: OrgData) -> tuple[str, float]:
    """Industry Classification. Returns (mapped_industry, confidence)."""
    mapped = INDUSTRY_MAP.get(data.industry, "unmapped")
    conf = 1.0 if data.industry in INDUSTRY_MAP else 0.5
    return mapped, conf


def compute_rss(data: OrgData) -> tuple[float, float]:
    """Regulatory Scrutiny Score (0-100)."""
    ic_mapped, _ = compute_ic(data)
    ind_sens = INDUSTRY_SENSITIVITY.get(ic_mapped, DEFAULT_INDUSTRY_SENSITIVITY)

    # Data volume signal: more clauses → more data processing → more scrutiny
    volume_signal = min(data.total_clauses / 200.0, 1.0) * 30  # max 30 pts

    # Sensitive data signal
    sensitive_cats = data.clause_categories.get("sensitive_data", 0)
    children_cats = data.clause_categories.get("children_teens", 0)
    sens_signal = min((sensitive_cats + children_cats) / 10.0, 1.0) * 25  # max 25 pts

    # Industry sensitivity component
    ind_signal = ind_sens * 25  # max 25 pts (~21 for fintech, ~10 for logistics)

    # Enforcement history component (from EHP, fed back)
    enf_signal = min(data.enforcement_count / 5.0, 1.0) * 20  # max 20 pts

    score = min(volume_signal + sens_signal + ind_signal + enf_signal, 100.0)

    # Confidence: lower if few clauses
    conf = 0.9 if data.total_clauses > 20 else (0.6 if data.total_clauses > 0 else 0.3)
    return round(score, 2), conf


def compute_pgms(data: OrgData) -> tuple[float, float]:
    """Privacy Governance Maturity Score (0-100)."""
    if data.total_clauses == 0:
        return 0.0, 0.3  # no notice → no signal, low confidence

    # Check presence of governance-relevant categories
    score = 0.0
    categories_present = 0
    for cat, weight in GOVERNANCE_SIGNALS.items():
        count = data.clause_categories.get(cat, 0)
        if count > 0:
            categories_present += 1
            # Depth signal: more clauses in a category = more thorough
            depth = min(count / 10.0, 1.0)
            score += weight * depth * 100

    # Breadth bonus: covering more categories shows maturity
    breadth_pct = categories_present / len(GOVERNANCE_SIGNALS)
    score = score * 0.7 + breadth_pct * 100 * 0.3

    score = min(score, 100.0)
    conf = 0.8 if categories_present >= 4 else (0.6 if categories_present >= 2 else 0.4)
    return round(score, 2), conf


def compute_osi(data: OrgData) -> tuple[float, float]:
    """Organizational Sophistication Index (0-100).

    THIN computation from firmographics. Missing data → score conservatively
    and penalize confidence (AGENTS.md: never inflate when data is missing).
    """
    base = SIZE_SCORES.get(data.size, 30)

    # Public companies tend to have more sophisticated governance
    if data.public_private == "public":
        base = min(base + 15, 100)
    elif data.public_private is None:
        # Unknown → don't adjust, but lower confidence
        pass

    # Geography adjustment (US companies under CCPA/state law patchwork)
    if data.geography == "US":
        base = min(base + 5, 100)

    # Confidence: penalize for missing public_private (known data gap)
    conf = 0.5 if data.public_private is None else 0.8

    return round(float(base), 2), conf


def compute_dsi(data: OrgData) -> tuple[float, float]:
    """Data Sensitivity Index (0-100)."""
    if data.total_clauses == 0:
        return 0.0, 0.3

    weighted_sum = 0.0
    total_weight = 0.0
    for cat, count in data.clause_categories.items():
        w = DSI_CATEGORY_WEIGHTS.get(cat, 0.0)
        if w > 0:
            weighted_sum += w * min(count / 5.0, 1.0)
            total_weight += w

    if total_weight == 0:
        return 0.0, 0.3

    score = (weighted_sum / total_weight) * 100
    score = min(score, 100.0)

    conf = 0.8 if data.total_clauses > 10 else 0.5
    return round(score, 2), conf


def compute_ehp(data: OrgData) -> tuple[float, float]:
    """Enforcement History Profile (0-100).

    Computed from enforcement records linked to the org's regulators/jurisdiction.
    Since enforcement_record is not directly linked to orgs, we use
    jurisdiction + regulator overlap as a proxy.
    """
    if data.enforcement_count == 0:
        return 0.0, 0.4  # no enforcement history → low but uncertain

    # Regulator activity signal
    reg_count = len(set(data.enforcement_regulators))
    reg_signal = min(reg_count / 3.0, 1.0) * 40  # max 40 pts

    # Penalty signal
    penalty_signal = 0.0
    if data.total_penalty_usd > 0:
        # Log scale: $10K=10, $100K=20, $1M=30, $10M=40
        import math
        penalty_signal = min(math.log10(max(data.total_penalty_usd, 1)) * 10, 40)

    # Volume signal
    vol_signal = min(data.enforcement_count / 10.0, 1.0) * 20  # max 20 pts

    score = min(reg_signal + penalty_signal + vol_signal, 100.0)
    conf = 0.7 if data.enforcement_count > 3 else 0.5
    return round(score, 2), conf


def compute_aigms(data: OrgData) -> tuple[float, float]:
    """AI Governance Maturity Score (0-100)."""
    ai_clauses = data.clause_categories.get("ai_automated_decisions", 0)

    if ai_clauses == 0:
        # No AI disclosure at all → low maturity
        return 10.0, 0.5

    # More AI clauses = more thorough AI governance disclosure
    depth = min(ai_clauses / 5.0, 1.0)
    score = 20 + depth * 60  # range: 20-80 based on depth

    # Bonus: if they also address tracking/profiling (related AI signals)
    tracking = data.clause_categories.get("tracking_cookies", 0)
    if tracking > 0:
        score = min(score + 10, 100)

    conf = 0.7 if ai_clauses >= 3 else (0.5 if ai_clauses >= 1 else 0.3)
    return round(score, 2), conf


def compute_confidence(
    dim_confidences: dict[str, float],
    data: OrgData,
) -> float:
    """Aggregate confidence score for the full profile.

    Penalized for: missing firmographics, thin clause data, no enforcement data.
    """
    # Average of dimension confidences
    avg = sum(dim_confidences.values()) / len(dim_confidences) if dim_confidences else 0.5

    # Additional penalties
    if not data.has_notice:
        avg *= 0.5  # no notice → major confidence hit
    if data.public_private is None:
        avg *= 0.9  # missing firmographic

    return round(min(max(avg, 0.0), 1.0), 4)


def compute_profile(data: OrgData) -> ProfileResult:
    """Compute the full 7-dimension profile for one org."""
    ic_mapped, ic_conf = compute_ic(data)
    rss, rss_conf = compute_rss(data)
    pgms, pgms_conf = compute_pgms(data)
    osi, osi_conf = compute_osi(data)
    dsi, dsi_conf = compute_dsi(data)
    ehp, ehp_conf = compute_ehp(data)
    aigms, aigms_conf = compute_aigms(data)

    dim_confs = {
        "ic": ic_conf, "rss": rss_conf, "pgms": pgms_conf,
        "osi": osi_conf, "dsi": dsi_conf, "ehp": ehp_conf,
        "aigms": aigms_conf,
    }
    confidence = compute_confidence(dim_confs, data)

    tiers = {
        "rss": score_to_tier(rss),
        "pgms": score_to_tier(pgms),
        "osi": score_to_tier(osi),
        "dsi": score_to_tier(dsi),
        "ehp": score_to_tier(ehp),
        "aigms": score_to_tier(aigms),
    }

    return ProfileResult(
        organization_id=data.organization_id,
        ic=ic_mapped,
        ic_raw=data.industry,
        rss=rss, pgms=pgms, osi=osi, dsi=dsi, ehp=ehp, aigms=aigms,
        confidence_score=confidence,
        tiers=tiers,
    )
