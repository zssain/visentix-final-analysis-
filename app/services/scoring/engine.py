"""Formula Engine — loads versioned weights/thresholds, dispatches scoring.

All weights come from formula_version (DB) or config files (JW, element_checklist).
NEVER hardcode a weight that exists in those sources.
"""

from __future__ import annotations

import csv
import os
from pathlib import Path

import yaml

CONFIG_DIR = Path(__file__).resolve().parents[3] / "config"


# ── Config loaders ────────────────────────────────────────────

def load_jurisdiction_weights(path: Path | None = None) -> dict[str, float]:
    """Load JW from config/targets.yaml."""
    p = path or (CONFIG_DIR / "targets.yaml")
    with open(p) as f:
        data = yaml.safe_load(f)
    jw = {k: float(v) for k, v in data["jurisdictions"].items()}
    jw["_default"] = float(data.get("default_jw", 0.3))
    return jw


def load_element_checklist(path: Path | None = None) -> list[dict]:
    """Load expected disclosure elements from config/element_checklist.csv."""
    p = path or (CONFIG_DIR / "element_checklist.csv")
    with open(p) as f:
        return list(csv.DictReader(f))


def get_expected_elements(checklist: list[dict], domain: str | None = None,
                          ai_only: bool = False) -> list[dict]:
    """Filter checklist by domain and/or AI-specific flag."""
    rows = checklist
    if domain:
        rows = [r for r in rows if r["domain"] == domain]
    if ai_only:
        rows = [r for r in rows if r["ai_specific"].lower() == "true"]
    return [r for r in rows if r["expected"].lower() == "true"]


TAXONOMY_DOMAINS = [
    "data_sharing", "tracking_cookies", "consumer_rights", "cross_border",
    "sensitive_data", "retention", "children_teens", "ai_automated_decisions",
]


def build_regulator_heatmap(
    regulators: list[dict],
    jurisdiction_weights: dict[str, float],
    org_clause_categories: dict[str, int] | None = None,
) -> list[dict]:
    """Build a regulators × domains heatmap grid.

    Each cell = JW × RPW × EFW × (DS if org data available, else 1.0).
    Returns a list of {regulator, jurisdiction, domain, score, tier} rows.
    """
    rows = []
    for reg in regulators:
        jw = jurisdiction_weights.get(
            reg.get("jurisdiction", ""),
            jurisdiction_weights.get("_default", 0.3),
        )
        efw = reg.get("efw", reg.get("enforcement_frequency_weight", 0.5))
        rpw = reg.get("rpw", reg.get("priority_weights", {}))

        for domain in TAXONOMY_DOMAINS:
            rpw_val = rpw.get(domain, 0.0) if isinstance(rpw, dict) else 0.0
            base = jw * rpw_val * efw

            # Company-conditioned: weight by org's clause distribution
            if org_clause_categories:
                total = sum(org_clause_categories.values()) or 1
                ds = org_clause_categories.get(domain, 0) / total
                cell_score = base * (0.5 + ds)  # floor of 0.5 so empty domains still show
            else:
                cell_score = base

            cell_score = round(min(cell_score * 100, 100.0), 1)

            if cell_score >= 60:
                tier = "high"
            elif cell_score >= 40:
                tier = "elevated"
            elif cell_score >= 20:
                tier = "moderate"
            else:
                tier = "low"

            rows.append({
                "regulator": reg.get("id", reg.get("regulator_id", "")),
                "jurisdiction": reg.get("jurisdiction", ""),
                "domain": domain,
                "score": cell_score,
                "tier": tier,
            })

    return rows


class FormulaVersion:
    """Loaded formula definition with weights/thresholds."""

    def __init__(self, fv_id: str, name: str, definition: str,
                 weights: dict | None, thresholds: dict | None):
        self.id = fv_id
        self.name = name
        self.definition = definition
        self.weights = weights or {}
        self.thresholds = thresholds or {}

    def get_threshold_tier(self, score: float) -> str:
        """Map a 0-100 score to a tier using stored thresholds."""
        for tier, bounds in self.thresholds.items():
            lo, hi = bounds[0], bounds[1]
            if lo <= score <= hi:
                return tier
        return "high" if score > 100 else "low"
