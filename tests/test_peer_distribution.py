"""F-015 peer-distribution unit tests.

Pure-function tests — no DB, no network, always run (not in _LIVE_DB_MODULES).
Covers AC-1, AC-2, AC-4, AC-5, AC-6, the AC-8 payload shape, AC-3 (F-011 stays
authoritative), and the documented edge cases. The rendering ACs (AC-7 no
comparative/SD language over HTML, AC-9 spec marking, AC-10 tenancy) are verified
in the report/spec/isolation suites, not here.
"""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from app.services.scoring import peer_distribution as pd


# ── Beta quantile against known closed-form values ───────────────────────────
# These are the three-plus known values the prompt requires when implementing the
# incomplete-beta inverse directly instead of trusting scipy.

@pytest.mark.parametrize(
    "q,a,b,expected",
    [
        (0.5, 1.0, 1.0, 0.5),        # uniform: B⁻¹(0.5;1,1)=0.5
        (0.975, 1.0, 1.0, 0.975),    # uniform CDF is identity
        (0.5, 2.0, 2.0, 0.5),        # symmetric Beta(2,2)
        (0.05, 5.0, 1.0, 0.05 ** (1.0 / 5.0)),   # CDF Beta(5,1)=x^5 → x=0.05^{1/5}
        (0.95, 1.0, 5.0, 1.0 - 0.05 ** (1.0 / 5.0)),  # CDF Beta(1,5)=1-(1-x)^5
    ],
)
def test_beta_ppf_known_values(q, a, b, expected):
    assert pd.beta_ppf(q, a, b) == pytest.approx(expected, abs=1e-4)


def test_regularized_incomplete_beta_roundtrips():
    # I_x(a,b) and its inverse should round-trip.
    for a, b, x in [(2.0, 5.0, 0.3), (5.0, 2.0, 0.7), (1.0, 1.0, 0.42)]:
        p = pd.regularized_incomplete_beta(a, b, x)
        assert pd.beta_ppf(p, a, b) == pytest.approx(x, abs=1e-4)


# ── AC-1: effective n ────────────────────────────────────────────────────────

def test_effective_n_equals_count_when_weights_equal():
    ws = [1.0] * 25
    assert pd.effective_n(ws) == pytest.approx(25.0, abs=1e-9)
    # scale invariance: equal weights of any magnitude
    assert pd.effective_n([3.3] * 25) == pytest.approx(25.0, abs=1e-9)


def test_effective_n_strictly_less_when_weights_unequal():
    ws = [10.0, 10.0, 10.0, 1.0, 1.0]
    assert pd.effective_n(ws) < len(ws)
    # the concentrated cohort from the docstring: three heavy of twenty → ~near six
    heavy = [10.0, 10.0, 10.0] + [0.3] * 17
    assert pd.effective_n(heavy) < 20
    assert pd.effective_n(heavy) > 2


# ── helpers to build cohorts ─────────────────────────────────────────────────

def _equal_weight_cohort(scores):
    return [{"score": float(s), "weight": 1.0} for s in scores]


def _spread(n, lo=20, hi=80):
    return [lo + (hi - lo) * i / (n - 1) for i in range(n)]


# ── AC-6: suppression below the cohort floor ─────────────────────────────────

def test_suppressed_below_cohort_floor():
    peers = _equal_weight_cohort([30, 40, 50, 60, 70])  # n_eff=5 < floor 10
    res = pd.compute_peer_distribution(55.0, peers)
    assert res.suppressed is True
    assert res.suppression_reason is not None
    assert "cohort_floor" in res.suppression_reason
    assert res.density == []          # no curve
    assert res.peers                  # rug still available
    assert res.to_payload()["suppressed"] is True


def test_not_suppressed_above_floor():
    peers = _equal_weight_cohort(_spread(30))  # n_eff=30
    res = pd.compute_peer_distribution(50.0, peers)
    assert res.suppressed is False
    assert len(res.density) == 101
    assert len(res.grid) == 101


# ── AC-4: reflected density integrates to ~1 ─────────────────────────────────

def _trapezoid_unit_grid(density):
    # grid spacing is exactly 1 (integer 0..100)
    return sum(density) - 0.5 * (density[0] + density[-1])


def test_density_integrates_to_one():
    peers = _equal_weight_cohort(_spread(40, 20, 80))
    res = pd.compute_peer_distribution(50.0, peers)
    assert res.suppressed is False
    integral = _trapezoid_unit_grid(res.density)
    assert integral == pytest.approx(1.0, abs=1e-3)


def test_reflection_holds_mass_at_edges():
    # data pushed against the lower boundary — reflection must keep the mass in.
    peers = _equal_weight_cohort(_spread(40, 2, 30))
    res = pd.compute_peer_distribution(10.0, peers)
    assert res.suppressed is False
    integral = _trapezoid_unit_grid(res.density)
    assert integral == pytest.approx(1.0, abs=1e-3)


# ── AC-2: determinism ────────────────────────────────────────────────────────

def test_deterministic_same_process():
    peers = _equal_weight_cohort(_spread(37, 15, 85))
    a = pd.compute_peer_distribution(48.0, peers).to_payload()
    b = pd.compute_peer_distribution(48.0, peers).to_payload()
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_deterministic_across_processes():
    # Byte-identical grid+density from a fresh interpreter (Hard Rule 6).
    peers = _equal_weight_cohort(_spread(37, 15, 85))
    local = json.dumps(pd.compute_peer_distribution(48.0, peers).to_payload(), sort_keys=True)
    code = (
        "import json;"
        "from app.services.scoring import peer_distribution as pd;"
        "peers=[{'score':15+(85-15)*i/36,'weight':1.0} for i in range(37)];"
        "print(json.dumps(pd.compute_peer_distribution(48.0,peers).to_payload(),sort_keys=True))"
    )
    out = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, cwd=".",
    )
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == local


# ── AC-5: CI contains the estimate and widens as n_eff falls ─────────────────

def test_ci_contains_point_and_widens_as_neff_falls():
    small = _equal_weight_cohort(_spread(12, 10, 90))    # n_eff = 12
    large = _equal_weight_cohort(_spread(120, 10, 90))   # n_eff = 120

    r_small = pd.compute_peer_distribution(50.0, small)
    r_large = pd.compute_peer_distribution(50.0, large)

    for r in (r_small, r_large):
        assert r.suppressed is False
        assert r.ci_lower is not None and r.ci_upper is not None
        assert r.ci_lower <= r.percentile <= r.ci_upper

    width_small = r_small.ci_upper - r_small.ci_lower
    width_large = r_large.ci_upper - r_large.ci_lower
    assert width_small > width_large


# ── AC-8 (payload shape) + F-015 caveat travels with the number ──────────────

def test_payload_carries_version_and_proposed_flag():
    peers = _equal_weight_cohort(_spread(30))
    payload = pd.compute_peer_distribution(50.0, peers).to_payload()
    assert payload["formula_version_id"] == "F-015_v1"
    assert payload["object_type"] == "peer_distribution"
    assert payload["proposed"] is True          # AC-9 companion: caveat in the DATA, not only the spec
    assert payload["grid"] == list(range(0, 101))


# ── AC-3: F-011 remains authoritative and unchanged ──────────────────────────

def test_f011_value_unchanged():
    from app.services.scoring.formulas_advanced import compute_f011

    peers = [{"score": s, "weight": 1.0} for s in (50, 60, 70, 80, 90)]
    res = compute_f011(70.0, peers, cohort_size=5)
    # below={50,60}=2, equal={70}=1, total=5 → (2 + 0.5)/5*100 = 50.0
    assert res.formula_version_id == "F-011_v1"
    assert res.object_type == "benchmark_percentile"
    assert res.score == 50.0


# ── edge cases ───────────────────────────────────────────────────────────────

def test_all_peers_identical_suppressed_not_floored():
    peers = _equal_weight_cohort([50] * 30)      # σ=0
    res = pd.compute_peer_distribution(50.0, peers)
    assert res.suppressed is True
    assert res.suppression_reason == "zero_dispersion"
    assert res.bandwidth is None                 # no fabricated spread
    assert res.density == []


def test_iqr_zero_but_sigma_positive_falls_back():
    # 30 peers at 50 (mass), plus extremes → weighted IQR(25-75)=0 but σ>0.
    scores = [50] * 30 + [0, 100]
    res = pd.compute_peer_distribution(50.0, _equal_weight_cohort(scores))
    assert res.suppressed is False
    assert res.iqr_w == pytest.approx(0.0, abs=1e-9)
    assert res.sigma_w > 0.0
    assert res.bandwidth_fallback is True


def test_percentile_at_boundary_zero_is_one_sided():
    peers = _equal_weight_cohort(_spread(30, 40, 90))
    res = pd.compute_peer_distribution(10.0, peers)   # below everything → pct 0
    assert res.percentile == pytest.approx(0.0, abs=1e-9)
    assert res.ci_lower == 0.0
    assert res.ci_one_sided is True
    assert res.ci_clamped is True


def test_percentile_at_boundary_hundred_is_one_sided():
    peers = _equal_weight_cohort(_spread(30, 10, 60))
    res = pd.compute_peer_distribution(99.0, peers)   # above everything → pct 100
    assert res.percentile == pytest.approx(100.0, abs=1e-9)
    assert res.ci_upper == 100.0
    assert res.ci_one_sided is True


def test_no_peers_suppressed():
    res = pd.compute_peer_distribution(50.0, [])
    assert res.suppressed is True
    assert res.suppression_reason == "no_peers"


def test_neff_rounded_down_recorded():
    # unequal weights → non-integer n_eff → rounded-down flag set
    peers = [{"score": s, "weight": w} for s, w in
             zip(_spread(20, 10, 90), [2.0, 1.0] * 10)]
    res = pd.compute_peer_distribution(50.0, peers)
    assert res.n_eff_int <= res.n_eff
    if res.n_eff_int != res.n_eff:
        assert res.n_eff_rounded_down is True
