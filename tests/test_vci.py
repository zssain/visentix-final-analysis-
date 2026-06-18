"""VCI tests — confidence scoring, labels, and suppression."""

import pytest

from app.services.scoring.vci import (
    SUPPRESSION_THRESHOLD,
    VCIResult,
    compute_vci,
)


def test_vci_all_high_confidence():
    r = compute_vci(nlp_confidence=0.9, benchmark_confidence=0.9,
                    regulatory_confidence=0.9, enforcement_confidence=0.9,
                    source_reliability=0.9)
    assert r.score == 90.0
    assert r.label == "very_high"
    assert r.suppress is False


def test_vci_all_low_confidence():
    r = compute_vci(nlp_confidence=0.1, benchmark_confidence=0.1,
                    regulatory_confidence=0.1, enforcement_confidence=0.1,
                    source_reliability=0.1)
    assert r.score == 10.0
    assert r.label == "very_low"
    assert r.suppress is True


def test_vci_moderate_mixed():
    r = compute_vci(nlp_confidence=0.5, benchmark_confidence=0.5,
                    regulatory_confidence=0.5, enforcement_confidence=0.5,
                    source_reliability=0.5)
    assert r.score == 50.0
    assert r.label == "moderate"
    assert r.suppress is False


def test_vci_suppression_threshold():
    """VCI < 40 must suppress."""
    r = compute_vci(nlp_confidence=0.3, benchmark_confidence=0.3,
                    regulatory_confidence=0.3, enforcement_confidence=0.3,
                    source_reliability=0.3)
    assert r.score == 30.0
    assert r.suppress is True
    assert r.label == "low"


def test_vci_just_above_threshold():
    r = compute_vci(nlp_confidence=0.4, benchmark_confidence=0.4,
                    regulatory_confidence=0.4, enforcement_confidence=0.4,
                    source_reliability=0.4)
    assert r.score == 40.0
    assert r.suppress is False


def test_vci_components_stored():
    r = compute_vci(nlp_confidence=0.8, benchmark_confidence=0.6,
                    regulatory_confidence=0.7, enforcement_confidence=0.5,
                    source_reliability=0.9)
    assert "nlp" in r.components
    assert "benchmark" in r.components
    assert r.components["nlp"] == 0.8
    assert r.components["source"] == 0.9


def test_vci_weights_sum_to_one():
    from app.services.scoring.vci import VCI_WEIGHTS
    assert abs(sum(VCI_WEIGHTS.values()) - 1.0) < 0.001


def test_vci_nlp_has_highest_weight():
    from app.services.scoring.vci import VCI_WEIGHTS
    assert VCI_WEIGHTS["nlp"] == max(VCI_WEIGHTS.values())
