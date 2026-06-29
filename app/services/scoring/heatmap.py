"""Regulator × domain exposure heatmap — deterministic, reproducible grid.

Builds a 9-regulator × 8-domain grid where each cell's intensity is:
    cell = RPW × clause_density × EFW × (1 + f004_boost)
    clamped 0–100.

RPW from regulator.priority_weights, EFW from enforcement_frequency_weight,
clause_density from notice clause category distribution, f004_boost from
F-004 lineage when available. No LLM calls.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

TAXONOMY_DOMAINS = [
    "ai_automated_decisions",
    "children_teens",
    "consumer_rights",
    "cross_border",
    "data_sharing",
    "retention",
    "sensitive_data",
    "tracking_cookies",
]


@dataclass
class HeatmapCell:
    domain: str
    intensity: float  # 0–100
    rpw: float
    efw: float
    clause_density: float  # 0–1: fraction of notice clauses in this domain
    f004_boost: float  # 0–1: enforcement correlation boost for this domain
    vci: float  # confidence for this cell


@dataclass
class HeatmapRow:
    regulator_id: str
    regulator_name: str
    jurisdiction: str
    cells: list[HeatmapCell] = field(default_factory=list)


def build_regulator_heatmap(
    regulators: list[dict],
    clause_categories: dict[str, int] | Counter,
    f004_domain_boosts: dict[str, float] | None = None,
    base_vci: float = 0.5,
) -> list[HeatmapRow]:
    """Build the 9×8 heatmap grid from regulator data + notice clause distribution.

    Args:
        regulators: [{regulator_id, name, jurisdiction, priority_weights, enforcement_frequency_weight}]
        clause_categories: {domain: count} from the notice's clauses
        f004_domain_boosts: {domain: 0–1 boost} from F-004 enforcement correlation lineage
        base_vci: default confidence level

    Returns:
        Sorted list of HeatmapRow, each with 8 sorted HeatmapCells.
        Deterministic ordering: regulators by regulator_id, domains alphabetical.
    """
    if f004_domain_boosts is None:
        f004_domain_boosts = {}

    total_clauses = sum(clause_categories.values()) if clause_categories else 1

    rows = []
    for reg in sorted(regulators, key=lambda r: r.get("regulator_id", "")):
        rpw_dict = reg.get("priority_weights", {}) or {}
        efw = reg.get("enforcement_frequency_weight", 0.5)
        reg_id = reg.get("regulator_id", "")
        reg_name = reg.get("name", reg_id)
        jurisdiction = reg.get("jurisdiction", "")

        cells = []
        for domain in TAXONOMY_DOMAINS:
            rpw = rpw_dict.get(domain, 0.0) if isinstance(rpw_dict, dict) else 0.0
            clause_count = clause_categories.get(domain, 0) if clause_categories else 0
            density = clause_count / max(total_clauses, 1)
            f004_boost = f004_domain_boosts.get(domain, 0.0)

            # Intensity: RPW × density × EFW × (1 + f004_boost) × 100
            # Density of 0 still gets a floor signal from RPW × EFW alone (×0.1)
            # so empty domains show baseline regulatory interest
            if density > 0:
                raw = rpw * density * efw * (1 + f004_boost) * 100
            else:
                raw = rpw * efw * 0.1 * 100  # floor: 10% of RPW×EFW

            intensity = round(min(max(raw, 0.0), 100.0), 1)

            # Cell VCI: reduce if clause density is 0 or f004 data missing
            cell_vci = base_vci
            if density == 0:
                cell_vci *= 0.5
            if not f004_domain_boosts:
                cell_vci *= 0.8

            cells.append(HeatmapCell(
                domain=domain,
                intensity=intensity,
                rpw=rpw,
                efw=efw,
                clause_density=round(density, 4),
                f004_boost=round(f004_boost, 4),
                vci=round(cell_vci, 4),
            ))

        rows.append(HeatmapRow(
            regulator_id=reg_id,
            regulator_name=reg_name,
            jurisdiction=jurisdiction,
            cells=cells,
        ))

    return rows


def heatmap_to_serializable(rows: list[HeatmapRow]) -> list[dict]:
    """Convert HeatmapRow list to JSON-serializable dicts for snapshot storage."""
    return [
        {
            "regulator_id": row.regulator_id,
            "regulator_name": row.regulator_name,
            "jurisdiction": row.jurisdiction,
            "cells": [
                {
                    "domain": c.domain,
                    "intensity": c.intensity,
                    "rpw": c.rpw,
                    "efw": c.efw,
                    "clause_density": c.clause_density,
                    "f004_boost": c.f004_boost,
                    "vci": c.vci,
                }
                for c in row.cells
            ],
        }
        for row in rows
    ]
