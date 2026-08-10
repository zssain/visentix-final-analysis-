"""ARCH-001A — the intake filter vocabularies, sourced from the SAME config the
scoring engine reads (`config/org_profile_weights.json`), so the dropdowns can
never drift from what scoring understands.

- Industry options   ← `industry_taxonomy` (name → {industry_id, …}); `compute_ic`
                       maps the chosen name to an industry_id that keys the
                       benchmark cohort (`build_population`).
- Jurisdiction options ← `rss_state_lookup` (code → weight); `compute_rss` reads
                       the org's `jurisdiction_presence` for state_exposure.

Honest absence: "unknown" is a first-class value (never a silently-defaulted real
industry); the `_default` RSS sentinel is NOT selectable.
"""

from __future__ import annotations

import json
from pathlib import Path

_CFG_PATH = Path(__file__).resolve().parents[2] / "config" / "org_profile_weights.json"
_CFG = json.loads(_CFG_PATH.read_text())

INDUSTRY_TAXONOMY: dict[str, dict] = _CFG["industry_taxonomy"]
RSS_STATE_LOOKUP: dict[str, float] = _CFG["rss_state_lookup"]

# Selectable jurisdictions = every RSS code except sentinels (e.g. `_default`).
JURISDICTION_CODES: list[str] = [k for k in RSS_STATE_LOOKUP if not k.startswith("_")]

# Plain-language labels (Rule 9). Codes not listed fall back to the raw code.
# Every state here has an ingested comprehensive privacy law in `legal_reference`
# / `obligation`; the label names the governing statute so the choice is legible.
_JURISDICTION_LABELS: dict[str, str] = {
    "US-CA": "California (CCPA / CPRA)",
    "US-TX": "Texas (TDPSA)",
    "US-CO": "Colorado (CPA)",
    "US-CT": "Connecticut (CTDPA)",
    "US-VA": "Virginia (VCDPA)",
    "US-WA": "Washington (My Health My Data)",
    "US-DE": "Delaware (DPDPA)",
    "US-IL": "Illinois (BIPA)",
    "US-NJ": "New Jersey (NJDPA)",
    "US-OR": "Oregon (OCPA)",
    "US-UT": "Utah (UCPA)",
    "US-IN": "Indiana (INCDPA)",
    "US-KY": "Kentucky (KCDPA)",
    "US-RI": "Rhode Island (RIDPA)",
    "US-MD": "Maryland (MODPA)",
    "US-MN": "Minnesota (MNCDPA)",
    "US-MT": "Montana (MCDPA)",
    "US-NE": "Nebraska (NEDPA)",
    "US-NH": "New Hampshire (NHDPA)",
    "US-IA": "Iowa (ICDPA)",
    "US-TN": "Tennessee (TIPA)",
    "US-FL": "Florida (FDBR)",
    "US-FED": "United States — Federal",
    "EU": "European Union (GDPR)",
}

# ── Industries offered in intake ─────────────────────────────
# Only industries with a real peer benchmark cohort built (`benchmark_cluster`)
# are offered, so a customer never picks a cohort that would silently fall back
# to the broad population with a disclosed confidence penalty. Keyed by
# industry_id → the one canonical taxonomy name to surface (aliases collapsed:
# e.g. fintech folds into financial_services under IND-05).
_COHORT_BACKED_INDUSTRIES: list[str] = ["retail", "healthcare", "financial_services"]

# The honest "no real industry" sentinel written when the user opts out.
UNKNOWN_INDUSTRY = "unknown"


def _industry_key(name: str) -> str:
    return (name or "").strip().lower().replace(" ", "_")


def is_valid_industry(name: str) -> bool:
    """True for a taxonomy key or the explicit unknown sentinel."""
    key = _industry_key(name)
    return key == UNKNOWN_INDUSTRY or key in INDUSTRY_TAXONOMY


def is_valid_jurisdiction(code: str) -> bool:
    """True for a real RSS jurisdiction code (never the `_default` sentinel)."""
    return code in RSS_STATE_LOOKUP and not code.startswith("_")


def industry_options() -> list[dict]:
    """[{value, label, industry_id}] for the intake dropdown.

    Restricted to cohort-backed industries (see `_COHORT_BACKED_INDUSTRIES`) so
    the dropdown never offers a peer benchmark that doesn't exist.
    """
    return [
        {"value": name, "label": name.replace("_", " ").title(),
         "industry_id": INDUSTRY_TAXONOMY[name].get("industry_id")}
        for name in _COHORT_BACKED_INDUSTRIES
        if name in INDUSTRY_TAXONOMY
    ]


def jurisdiction_options() -> list[dict]:
    """[{value, label}] for the state-privacy-laws multi-select."""
    return [
        {"value": code, "label": _JURISDICTION_LABELS.get(code, code)}
        for code in JURISDICTION_CODES
    ]


def intake_options() -> dict:
    """The full payload served by GET /config/intake-options."""
    return {
        "industries": industry_options(),
        "jurisdictions": jurisdiction_options(),
        "unknown_industry": UNKNOWN_INDUSTRY,
    }
