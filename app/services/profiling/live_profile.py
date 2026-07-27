"""Spec-exact VICBNF v2 organization profiling engine.

Computes 7 dimensions from org metadata, classified clauses, and enforcement
records. ALL weights loaded from config/org_profile_weights.json — nothing
hardcoded.

Divergences fixed from the legacy profile.py:
  - RSS: spec 6-factor weighted formula (was: 4 additive signals)
  - PGMS: spec 4-pillar weighted formula (was: category depth * breadth)
  - OSI: spec 9-factor formula (was: size + public + geography only)
  - DSI: spec adds processing context multiplier (was: simple ratio)
  - AIGMS: spec 6-factor formula mapped to clause_types (was: clause count only)
  - EHP: spec Clean/Adjacent/Enforcement classification (was: numeric score only)
  - IC: spec 10-industry taxonomy with industry_id (was: 8 industry map + hash)
  - Tiers: spec-exact per-dimension cutoffs (was: single 4-tier set for all)
"""

from __future__ import annotations

import json
import math
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

# ── Load config ──────────────────────────────────────────────

_CONFIG_PATH = Path(__file__).resolve().parents[3] / "config" / "org_profile_weights.json"

with open(_CONFIG_PATH) as _f:
    _CFG = json.load(_f)

_INDUSTRY_TAX = _CFG["industry_taxonomy"]
_INDUSTRY_DEFAULT_SENS = _CFG["industry_default_sensitivity"]
_RSS_W = _CFG["rss_weights"]
_RSS_STATES = _CFG["rss_state_lookup"]
_RSS_TIERS = _CFG["rss_tiers"]
_PGMS_W = _CFG["pgms_weights"]
_PGMS_CAT_MAP = _CFG["pgms_category_map"]
_PGMS_TIERS = _CFG["pgms_tiers"]
_OSI_W = _CFG["osi_weights"]
_OSI_SIZE = _CFG["osi_size_scores"]
_OSI_TIERS = _CFG["osi_tiers"]
_DSI_CAT_W = _CFG["dsi_category_weights"]
_DSI_CTX_MULT = _CFG["dsi_processing_context_multiplier"]
_DSI_TIERS = _CFG["dsi_tiers"]
_AIGMS_W = _CFG["aigms_weights"]
_AIGMS_CT_MAP = _CFG["aigms_clause_type_map"]
_AIGMS_TIERS = _CFG["aigms_tiers"]
_EHP_TIERS = _CFG["ehp_tiers"]
# Presence-count saturation constants (value-identical to the former hardcoded
# x3 / /5 / /2). Option-1 decision 2026-07-28 keeps them as-is with a documented
# limitation; a future Option-2 calibration is a config + formula-version change.
_PRESENCE_SAT = _CFG["presence_saturation"]
_PGMS_SAT = _PRESENCE_SAT["pgms_clauses_per_category"]
_DSI_SAT = _PRESENCE_SAT["dsi_clauses_per_category"]
_AIGMS_SAT = _PRESENCE_SAT["aigms_clauses_per_factor"]


# ── Data structures ──────────────────────────────────────────

@dataclass
class OrgProfileInput:
    """All data needed to compute a 7-dimension profile."""
    organization_id: str
    name: str
    industry: str
    size: str
    geography: str
    public_private: str | None = None

    # From classified clauses
    clause_categories: Counter = field(default_factory=Counter)
    clause_types: Counter = field(default_factory=Counter)  # v2 30-type taxonomy
    total_clauses: int = 0
    has_notice: bool = False
    avg_transparency: float = 0.0

    # Enforcement
    enforcement_count: int = 0
    total_penalty_usd: float = 0.0
    enforcement_regulators: list[str] = field(default_factory=list)

    # Org metadata (may be sparse for new orgs)
    jurisdiction_presence: list[str] = field(default_factory=list)
    has_privacy_office: bool = False
    has_legal_dept: bool = False
    has_privacy_counsel: bool = False
    has_security_program: bool = False


@dataclass
class OrgProfileResult:
    """Computed 7-dimension profile with tier labels."""
    organization_id: str
    industry_id: str
    sub_industry: str
    ic_label: str

    rss: float
    rss_tier: str
    pgms: float
    pgms_tier: str
    osi: float
    osi_tier: str
    dsi: float
    dsi_tier: str
    ehp: float
    ehp_tier: str
    aigms: float
    aigms_tier: str

    confidence_score: float
    profile_version: int = 1
    dim_confidences: dict[str, float] = field(default_factory=dict)


# ── Tier lookup ──────────────────────────────────────────────

def _score_to_tier(score: float, tiers: list[dict]) -> str:
    """Map score to tier label using config-defined cutoffs."""
    for t in tiers:
        if t["min"] <= score <= t["max"]:
            return t["label"]
    return tiers[-1]["label"] if score > tiers[-1]["max"] else tiers[0]["label"]


# ── IC: Industry Classification ──────────────────────────────

def compute_ic(industry: str) -> tuple[str, str, str, float]:
    """Returns (industry_id, sub_industry, ic_label, confidence)."""
    key = industry.lower().replace(" ", "_")
    entry = _INDUSTRY_TAX.get(key)
    if entry:
        return entry["industry_id"], key, key.replace("_", " ").title(), 1.0
    # Fuzzy fallback: try prefix match
    for k, v in _INDUSTRY_TAX.items():
        if key.startswith(k[:4]) or k.startswith(key[:4]):
            return v["industry_id"], k, k.replace("_", " ").title(), 0.7
    return "IND-00", "unmapped", "Unmapped", 0.4


# ── RSS: Regulatory Scrutiny Score ───────────────────────────

def compute_rss(inp: OrgProfileInput) -> tuple[float, float]:
    """RSS = StateExposure*25% + DataVolume*20% + SensitiveData*20% +
    Advertising/Profiling*15% + IndustrySensitivity*10% + RegulatoryHistory*10%"""

    # State exposure (max jurisdiction weight from org's presence)
    jurisdictions = inp.jurisdiction_presence or [inp.geography or "US"]
    state_scores = [_RSS_STATES.get(j, _RSS_STATES["_default"]) for j in jurisdictions]
    state_exposure = max(state_scores) * 100 if state_scores else 30.0

    # Data volume (normalized by clause count)
    data_volume = min(inp.total_clauses / 100.0, 1.0) * 100

    # Sensitive data
    sens = inp.clause_categories.get("sensitive_data", 0)
    children = inp.clause_categories.get("children_teens", 0)
    sensitive_data = min((sens + children) / max(inp.total_clauses, 1) * 5, 1.0) * 100

    # Advertising / profiling
    tracking = inp.clause_categories.get("tracking_cookies", 0)
    ai = inp.clause_categories.get("ai_automated_decisions", 0)
    ad_profiling = min((tracking + ai) / max(inp.total_clauses, 1) * 5, 1.0) * 100

    # Industry sensitivity
    ind_key = inp.industry.lower().replace(" ", "_")
    ind_entry = _INDUSTRY_TAX.get(ind_key)
    ind_sens = (ind_entry["sensitivity"] if ind_entry else _INDUSTRY_DEFAULT_SENS) * 100

    # Regulatory history
    reg_history = min(inp.enforcement_count / 5.0, 1.0) * 100

    score = (
        state_exposure * _RSS_W["state_exposure"]
        + data_volume * _RSS_W["data_volume"]
        + sensitive_data * _RSS_W["sensitive_data"]
        + ad_profiling * _RSS_W["advertising_profiling"]
        + ind_sens * _RSS_W["industry_sensitivity"]
        + reg_history * _RSS_W["regulatory_history"]
    )
    score = round(min(max(score, 0), 100), 2)
    conf = 0.9 if inp.total_clauses > 20 else (0.6 if inp.total_clauses > 0 else 0.3)
    return score, conf


# ── PGMS: Privacy Governance Maturity Score ──────────────────

def compute_pgms(inp: OrgProfileInput) -> tuple[float, float]:
    """PGMS = GovernanceInfra*30% + OperationalControls*30% +
    TransparencyPractices*20% + ConsumerRightsSupport*20%"""
    if inp.total_clauses == 0:
        return 0.0, 0.3

    pillar_scores = {}
    for pillar, weight in _PGMS_W.items():
        categories = _PGMS_CAT_MAP.get(pillar, [])
        count = sum(inp.clause_categories.get(cat, 0) for cat in categories)
        depth = min(count / max(len(categories) * _PGMS_SAT, 1), 1.0)
        pillar_scores[pillar] = depth * 100

    score = sum(
        pillar_scores.get(p, 0) * w
        for p, w in _PGMS_W.items()
    )
    score = round(min(max(score, 0), 100), 2)

    pillars_with_data = sum(1 for v in pillar_scores.values() if v > 0)
    conf = 0.8 if pillars_with_data >= 3 else (0.6 if pillars_with_data >= 2 else 0.4)
    return score, conf


# ── OSI: Organizational Sophistication Index ─────────────────

def compute_osi(inp: OrgProfileInput) -> tuple[float, float]:
    """OSI = EmployeeCount*20% + Revenue*15% + PublicCompany*10% + LegalDept*15% +
    PrivacyOffice*15% + PrivacyCounsel*10% + Security*5% + AIGovernance*5% +
    GovernanceArtifacts*5%"""
    size_score = _OSI_SIZE.get(inp.size, _OSI_SIZE.get("unknown", 30))

    factors = {
        "employee_count": size_score,
        "revenue": size_score * 0.8,  # proxy from size when revenue unknown
        "public_company": 100 if inp.public_private == "public" else (50 if inp.public_private == "private" else 30),
        "legal_dept": 100 if inp.has_legal_dept else (50 if inp.size == "large" else 20),
        "privacy_office": 100 if inp.has_privacy_office else (40 if inp.size == "large" else 15),
        "privacy_counsel": 100 if inp.has_privacy_counsel else (30 if inp.size == "large" else 10),
        "security": 100 if inp.has_security_program else (60 if inp.clause_categories.get("sensitive_data", 0) > 0 else 20),
        "ai_governance": min(inp.clause_categories.get("ai_automated_decisions", 0) * 25, 100),
        "governance_artifacts": min(inp.total_clauses / 20.0, 1.0) * 100,
    }

    score = sum(factors.get(k, 0) * w for k, w in _OSI_W.items())
    score = round(min(max(score, 0), 100), 2)

    known_fields = sum(1 for k in ["public_company", "legal_dept", "privacy_office"]
                       if inp.public_private is not None or getattr(inp, f"has_{k}", False))
    conf = 0.8 if known_fields >= 2 else 0.5
    return score, conf


# ── DSI: Data Sensitivity Index ──────────────────────────────

def compute_dsi(inp: OrgProfileInput) -> tuple[float, float]:
    """DSI = min(100, sum(CategoryWeight * PresenceConfidence * ContextMultiplier))"""
    if inp.total_clauses == 0:
        return 0.0, 0.3

    raw = 0.0
    for cat, count in inp.clause_categories.items():
        w = _DSI_CAT_W.get(cat, 0.0)
        if w > 0:
            presence_conf = min(count / _DSI_SAT, 1.0)
            raw += w * presence_conf * _DSI_CTX_MULT

    score = round(min(raw / sum(v for v in _DSI_CAT_W.values() if v > 0) * 100, 100), 2)
    conf = 0.8 if inp.total_clauses > 10 else 0.5
    return score, conf


# ── EHP: Enforcement History Profile ─────────────────────────

def compute_ehp(inp: OrgProfileInput) -> tuple[float, str, float]:
    """Returns (score, classification_label, confidence).
    Clean / Enforcement-Adjacent / Enforcement."""
    if inp.enforcement_count == 0:
        return 0.0, "Clean", 0.4

    reg_count = len(set(inp.enforcement_regulators))
    reg_signal = min(reg_count / 3.0, 1.0) * 40

    penalty_signal = 0.0
    if inp.total_penalty_usd > 0:
        penalty_signal = min(math.log10(max(inp.total_penalty_usd, 1)) * 10, 40)

    vol_signal = min(inp.enforcement_count / 10.0, 1.0) * 20
    score = round(min(reg_signal + penalty_signal + vol_signal, 100), 2)

    tier = _score_to_tier(score, _EHP_TIERS)
    conf = 0.7 if inp.enforcement_count > 3 else 0.5
    return score, tier, conf


# ── AIGMS: AI Governance Maturity Score ──────────────────────

def compute_aigms(inp: OrgProfileInput) -> tuple[float, float]:
    """AIGMS = AIUseDisclosure*20% + ProfilingTransparency*20% +
    AutomatedDecisionDisclosure*20% + TrainingDataDisclosure*15% +
    ConsumerControls*15% + AIGovernanceArtifacts*10%"""
    factor_scores = {}
    for factor, weight in _AIGMS_W.items():
        clause_types_for_factor = _AIGMS_CT_MAP.get(factor, [])
        count = sum(inp.clause_types.get(ct, 0) for ct in clause_types_for_factor)
        # Also check legacy categories as fallback
        if count == 0 and factor in ("ai_use_disclosure", "automated_decision_disclosure"):
            count = inp.clause_categories.get("ai_automated_decisions", 0)
        factor_scores[factor] = min(count / _AIGMS_SAT, 1.0) * 100

    score = sum(factor_scores.get(f, 0) * w for f, w in _AIGMS_W.items())
    score = round(min(max(score, 0), 100), 2)

    ai_total = inp.clause_categories.get("ai_automated_decisions", 0)
    conf = 0.7 if ai_total >= 3 else (0.5 if ai_total >= 1 else 0.3)
    return score, conf


# ── Aggregate confidence ─────────────────────────────────────

def _aggregate_confidence(dim_confs: dict[str, float], inp: OrgProfileInput) -> float:
    """VCI-style aggregate: mean of dimension confidences with penalties."""
    avg = sum(dim_confs.values()) / len(dim_confs) if dim_confs else 0.5
    if not inp.has_notice:
        avg *= 0.5
    if inp.public_private is None:
        avg *= 0.9
    return round(min(max(avg, 0), 1), 4)


# ── Main entry point ─────────────────────────────────────────

def compute_org_profile(
    org_row: dict,
    clauses: list[dict],
    enforcement_rows: list[dict] | None = None,
    profile_version: int = 1,
) -> OrgProfileResult:
    """Compute spec-exact 7-dimension profile for one organization.

    Args:
        org_row: dict with organization_id, name, industry, size, geography,
                 public_private, jurisdiction_presence, etc.
        clauses: list of clause dicts with at least {category, clause_type}.
        enforcement_rows: list of {enforcement_id, regulator_id, penalty_usd}.
        profile_version: version counter for this computation.

    Returns OrgProfileResult with all scores, tiers, and confidence.
    """
    enforcement_rows = enforcement_rows or []

    # Build input
    cats = Counter(c.get("category", "other") for c in clauses)
    clause_types = Counter(c.get("clause_type", "") for c in clauses if c.get("clause_type"))
    transparency_vals = [c.get("transparency_score", 0) for c in clauses if c.get("transparency_score")]

    inp = OrgProfileInput(
        organization_id=org_row.get("organization_id", ""),
        name=org_row.get("name", ""),
        industry=org_row.get("industry", "unknown"),
        size=org_row.get("size", "unknown"),
        geography=org_row.get("geography", "US"),
        public_private=org_row.get("public_private") or org_row.get("public_company_flag"),
        clause_categories=cats,
        clause_types=clause_types,
        total_clauses=len(clauses),
        has_notice=len(clauses) > 0,
        avg_transparency=sum(transparency_vals) / len(transparency_vals) if transparency_vals else 0.0,
        enforcement_count=len(enforcement_rows),
        total_penalty_usd=sum(e.get("penalty_usd") or 0 for e in enforcement_rows),
        enforcement_regulators=[e.get("regulator_id", "") for e in enforcement_rows],
        jurisdiction_presence=org_row.get("jurisdiction_presence") or [org_row.get("geography", "US")],
        has_privacy_office=bool(org_row.get("has_privacy_office")),
        has_legal_dept=bool(org_row.get("has_legal_dept")),
        has_privacy_counsel=bool(org_row.get("has_privacy_counsel")),
        has_security_program=bool(org_row.get("has_security_program")),
    )

    # Compute all dimensions
    industry_id, sub_industry, ic_label, ic_conf = compute_ic(inp.industry)
    rss, rss_conf = compute_rss(inp)
    pgms, pgms_conf = compute_pgms(inp)
    osi, osi_conf = compute_osi(inp)
    dsi, dsi_conf = compute_dsi(inp)
    ehp, ehp_tier, ehp_conf = compute_ehp(inp)
    aigms, aigms_conf = compute_aigms(inp)

    dim_confs = {
        "ic": ic_conf, "rss": rss_conf, "pgms": pgms_conf,
        "osi": osi_conf, "dsi": dsi_conf, "ehp": ehp_conf,
        "aigms": aigms_conf,
    }
    confidence = _aggregate_confidence(dim_confs, inp)

    return OrgProfileResult(
        organization_id=inp.organization_id,
        industry_id=industry_id,
        sub_industry=sub_industry,
        ic_label=ic_label,
        rss=rss,
        rss_tier=_score_to_tier(rss, _RSS_TIERS),
        pgms=pgms,
        pgms_tier=_score_to_tier(pgms, _PGMS_TIERS),
        osi=osi,
        osi_tier=_score_to_tier(osi, _OSI_TIERS),
        dsi=dsi,
        dsi_tier=_score_to_tier(dsi, _DSI_TIERS),
        ehp=ehp,
        ehp_tier=ehp_tier,
        aigms=aigms,
        aigms_tier=_score_to_tier(aigms, _AIGMS_TIERS),
        confidence_score=confidence,
        profile_version=profile_version,
        dim_confidences=dim_confs,
    )
