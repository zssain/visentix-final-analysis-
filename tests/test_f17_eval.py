"""F17 harness unit tests — gold set, classifier eval, precision, benchmark sanity,
golden notices. Pure/deterministic (synthetic fixtures); no tuning anywhere.
"""

import json

from scripts.eval import benchmark_sanity, classifier_eval, golden_notices, precision
from scripts.eval.common import GOLD_SET_PATH, band_of


# ── Gold set (component 1) ───────────────────────────────────

def test_band_of_cutoffs():
    assert band_of(0.95) == "very_high"
    assert band_of(0.80) == "high"
    assert band_of(0.65) == "moderate"
    assert band_of(0.50) == "low"
    assert band_of(0.20) == "very_low"
    assert band_of(None) == "very_low"


def test_frozen_gold_set_prefills_nothing_and_excludes_noise():
    m = json.loads(GOLD_SET_PATH.read_text())
    assert m["selected"] <= m["target"]
    # The harness pre-fills NO gold labels — the frozen manifest carries none.
    for c in m["clauses"]:
        assert "gold_domain" not in c and "verdict" not in c
    # Under-populated strata are reported, not back-filled.
    assert "empty_cells" in m


# ── Classifier eval (component 2) ────────────────────────────

def test_classifier_eval_awaiting_when_no_labels():
    assert classifier_eval.evaluate([])["status"] == classifier_eval.AWAITING


def test_classifier_eval_math_on_synthetic_labels():
    rows = [
        {"gold_domain": "data_sharing", "category_v2": "data_sharing",
         "nlp_confidence_v2": 0.9, "source_group": "fresh_2026"},
        {"gold_domain": "retention", "category_v2": "data_sharing",   # error
         "nlp_confidence_v2": 0.3, "source_group": "legacy"},
        {"gold_domain": "consumer_rights", "category_v2": "consumer_rights",
         "nlp_confidence_v2": 0.8, "source_group": "fresh_2026"},
    ]
    r = classifier_eval.evaluate(rows)
    assert r["labeled"] == 3
    assert r["accuracy"] == round(2 / 3, 4)
    assert r["confusion"]["retention"]["data_sharing"] == 1          # the miss
    # calibration: the error sits in the very_low band
    assert r["vci_calibration_error_rate"]["very_low"]["error_rate"] == 1.0
    assert r["vci_calibration_error_rate"]["very_high"]["error_rate"] == 0.0


def test_stability_is_labelled_not_accuracy_and_deterministic():
    r = classifier_eval.stability(["we share data with third parties"] * 5,
                                  classify_fn=lambda t: "data_sharing", runs=3)
    assert r["metric"] == "stability_not_accuracy"
    assert r["agreement_rate"] == 1.0


# ── Precision (component 6) ──────────────────────────────────

def test_precision_empty_state():
    assert precision.compute([])["status"] == "no SME review actions yet"


def test_precision_rates():
    rows = [
        {"finding_type": "SH-002", "action": "confirmed"},
        {"finding_type": "SH-002", "action": "dismissed"},
        {"finding_type": "SH-002", "action": "confirmed"},
        {"finding_type": "AI-004", "action": "edited"},
    ]
    r = precision.compute(rows)
    assert r["by_finding_type"]["SH-002"]["confirmed"] == 2
    assert r["by_finding_type"]["SH-002"]["confirmed_rate"] == round(2 / 3, 4)
    assert r["by_finding_type"]["AI-004"]["edited_rate"] == 1.0


# ── Benchmark sanity (component 5) ───────────────────────────

def test_benchmark_distribution_wellformed():
    r = benchmark_sanity.distribution_wellformed([40, 50, 60, 70, 80, 90])
    assert r["monotone_non_decreasing"] is True
    assert r["max_pct"] >= r["min_pct"]


def test_synthetic_strong_org_lands_upper_half_no_residue():
    r = benchmark_sanity.synthetic_strong_upper_half([30, 40, 50, 60, 70])
    assert r["upper_half"] is True
    assert "in-memory only" in r["note"]   # nothing persisted → nothing to remove


# ── Golden notices (component 4) ─────────────────────────────

def test_golden_files_have_no_drift_and_are_flagged_proposed():
    for slug, spec in golden_notices.FIXTURES.items():
        assert golden_notices.diff(slug, spec["text"]) == []   # frozen == current
        golden = json.loads((golden_notices.GOLDEN_DIR / f"{slug}.json").read_text())
        assert "PROPOSED" in golden["status"]                  # pending SME bless (OQ-1)


def test_golden_diff_detects_drift_and_names_formula_version():
    drift = golden_notices.diff("retail_strong", "# Privacy Policy\n\nWe collect nothing.")
    assert drift and any("formula_version" in d for d in drift)
