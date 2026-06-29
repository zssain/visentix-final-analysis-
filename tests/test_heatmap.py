"""Heatmap tests — 9×8 grid, hot/cold cells, deterministic ordering, reproducibility."""

from collections import Counter

import pytest

from app.services.scoring.heatmap import (
    HeatmapCell,
    HeatmapRow,
    build_regulator_heatmap,
    heatmap_to_serializable,
)


# ── Fixtures ─────────────────────────────────────────────────

SAMPLE_REGULATORS = [
    {"regulator_id": "FTC", "name": "Federal Trade Commission", "jurisdiction": "US-FED",
     "enforcement_frequency_weight": 0.9,
     "priority_weights": {"data_sharing": 0.9, "tracking_cookies": 0.9, "sensitive_data": 0.9,
                          "consumer_rights": 0.6, "children_teens": 0.9, "retention": 0.6,
                          "cross_border": 0.4, "ai_automated_decisions": 0.8}},
    {"regulator_id": "CPPA", "name": "CA Privacy Protection Agency", "jurisdiction": "US-CA",
     "enforcement_frequency_weight": 0.7,
     "priority_weights": {"data_sharing": 0.9, "tracking_cookies": 0.9, "sensitive_data": 0.8,
                          "consumer_rights": 0.9, "children_teens": 0.7, "retention": 0.7,
                          "cross_border": 0.5, "ai_automated_decisions": 0.9}},
    {"regulator_id": "TX-AG", "name": "Texas Attorney General", "jurisdiction": "US-TX",
     "enforcement_frequency_weight": 0.8,
     "priority_weights": {"data_sharing": 0.8, "sensitive_data": 0.8, "consumer_rights": 0.7,
                          "tracking_cookies": 0.7, "ai_automated_decisions": 0.6}},
]

SAMPLE_CLAUSES = Counter({
    "data_sharing": 20,
    "tracking_cookies": 10,
    "retention": 3,
    "sensitive_data": 5,
    "consumer_rights": 8,
    "other": 30,
})


# ── Grid dimensions ──────────────────────────────────────────

def test_grid_dimensions():
    """Each regulator gets exactly 8 domain cells."""
    rows = build_regulator_heatmap(SAMPLE_REGULATORS, SAMPLE_CLAUSES)
    assert len(rows) == 3  # 3 sample regulators
    for row in rows:
        assert len(row.cells) == 8


def test_grid_with_9_regulators():
    """With 9 regulators, grid is 9×8."""
    regs = [{"regulator_id": f"REG-{i}", "name": f"Reg {i}", "jurisdiction": "US",
             "enforcement_frequency_weight": 0.5,
             "priority_weights": {"data_sharing": 0.5}} for i in range(9)]
    rows = build_regulator_heatmap(regs, SAMPLE_CLAUSES)
    assert len(rows) == 9
    for row in rows:
        assert len(row.cells) == 8


# ── Hot vs cold cells ────────────────────────────────────────

def test_high_rpw_high_exposure_is_hot():
    """Regulator with high RPW in an exposed domain → hotter cell."""
    rows = build_regulator_heatmap(SAMPLE_REGULATORS, SAMPLE_CLAUSES)
    ftc = next(r for r in rows if r.regulator_id == "FTC")

    # data_sharing: RPW=0.9, high clause density → hot
    ds_cell = next(c for c in ftc.cells if c.domain == "data_sharing")
    # cross_border: RPW=0.4, zero clauses → cold
    xb_cell = next(c for c in ftc.cells if c.domain == "cross_border")

    assert ds_cell.intensity > xb_cell.intensity


def test_zero_clauses_gets_floor_signal():
    """Domain with 0 clauses still gets a small floor from RPW×EFW."""
    rows = build_regulator_heatmap(SAMPLE_REGULATORS, SAMPLE_CLAUSES)
    ftc = next(r for r in rows if r.regulator_id == "FTC")
    # children_teens has 0 clauses but FTC has RPW=0.9
    ct_cell = next(c for c in ftc.cells if c.domain == "children_teens")
    assert ct_cell.intensity > 0  # floor signal, not zero


def test_low_rpw_low_exposure_is_cold():
    """Low RPW + low clause density → low intensity."""
    rows = build_regulator_heatmap(SAMPLE_REGULATORS, SAMPLE_CLAUSES)
    tx = next(r for r in rows if r.regulator_id == "TX-AG")
    # TX-AG has no RPW for cross_border, retention etc
    xb_cell = next(c for c in tx.cells if c.domain == "cross_border")
    assert xb_cell.intensity < 5  # very cold


# ── Clamping ─────────────────────────────────────────────────

def test_intensity_clamped_0_100():
    rows = build_regulator_heatmap(SAMPLE_REGULATORS, SAMPLE_CLAUSES)
    for row in rows:
        for cell in row.cells:
            assert 0 <= cell.intensity <= 100


# ── F-004 boost ──────────────────────────────────────────────

def test_f004_boost_increases_intensity():
    """F-004 enforcement correlation boost makes cells hotter."""
    rows_no_boost = build_regulator_heatmap(SAMPLE_REGULATORS, SAMPLE_CLAUSES)
    rows_with_boost = build_regulator_heatmap(
        SAMPLE_REGULATORS, SAMPLE_CLAUSES,
        f004_domain_boosts={"data_sharing": 0.5, "tracking_cookies": 0.3},
    )

    ftc_no = next(r for r in rows_no_boost if r.regulator_id == "FTC")
    ftc_yes = next(r for r in rows_with_boost if r.regulator_id == "FTC")

    ds_no = next(c for c in ftc_no.cells if c.domain == "data_sharing")
    ds_yes = next(c for c in ftc_yes.cells if c.domain == "data_sharing")

    assert ds_yes.intensity > ds_no.intensity


# ── Deterministic ordering ───────────────────────────────────

def test_regulators_sorted_by_id():
    rows = build_regulator_heatmap(SAMPLE_REGULATORS, SAMPLE_CLAUSES)
    ids = [r.regulator_id for r in rows]
    assert ids == sorted(ids)


def test_domains_sorted_alphabetically():
    rows = build_regulator_heatmap(SAMPLE_REGULATORS, SAMPLE_CLAUSES)
    for row in rows:
        domains = [c.domain for c in row.cells]
        assert domains == sorted(domains)


# ── Reproducibility ──────────────────────────────────────────

def test_reproducible():
    r1 = build_regulator_heatmap(SAMPLE_REGULATORS, SAMPLE_CLAUSES)
    r2 = build_regulator_heatmap(SAMPLE_REGULATORS, SAMPLE_CLAUSES)

    s1 = heatmap_to_serializable(r1)
    s2 = heatmap_to_serializable(r2)

    assert s1 == s2


# ── Serialization ────────────────────────────────────────────

def test_serializable_structure():
    rows = build_regulator_heatmap(SAMPLE_REGULATORS, SAMPLE_CLAUSES)
    data = heatmap_to_serializable(rows)
    assert isinstance(data, list)
    assert len(data) == 3

    for item in data:
        assert "regulator_id" in item
        assert "regulator_name" in item
        assert "cells" in item
        assert len(item["cells"]) == 8
        for cell in item["cells"]:
            assert "domain" in cell
            assert "intensity" in cell
            assert "rpw" in cell
            assert "vci" in cell


# ── VCI reduced for missing data ─────────────────────────────

def test_vci_reduced_for_zero_density():
    """Cells with 0 clause density get reduced VCI."""
    rows = build_regulator_heatmap(SAMPLE_REGULATORS, SAMPLE_CLAUSES, base_vci=0.6)
    ftc = next(r for r in rows if r.regulator_id == "FTC")

    ds_cell = next(c for c in ftc.cells if c.domain == "data_sharing")  # has clauses
    ct_cell = next(c for c in ftc.cells if c.domain == "children_teens")  # no clauses

    assert ds_cell.vci > ct_cell.vci
