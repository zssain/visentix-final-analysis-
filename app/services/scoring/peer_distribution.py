"""F-015 (PROPOSED — awaiting expert ratification): weighted peer-position density
and Clopper–Pearson confidence interval.

This module supports the report's peer-position surface. It does NOT replace
F-011 (Benchmark Percentile) — F-011 remains the authoritative stored position
(`formulas_advanced.compute_f011`). This module adds, around that same position,
the cohort's actual reliability-weighted density, the individual peer points
(the rug), and a confidence interval on the rank — so a reader sees the spread
and the uncertainty rather than a bare percentile printed to the unit.

Design constraints (all load-bearing):
  * Pure functions. No I/O, no DB, no LLM (Hard Rule 2). Fully deterministic so a
    frozen snapshot regenerates byte-identically (Hard Rule 6).
  * Effective sample size `n_eff`, never raw `cohort_size`, drives the bandwidth
    and the interval. A cohort of twenty where three members carry most of the
    weight has n_eff near six; using raw n would overstate how settled the curve
    is.
  * The density is reflected on [0,100] because scores are bounded; without
    reflection it is biased downward at exactly the edges where a customer sits
    when a finding matters.
  * The Beta quantile (Clopper–Pearson) is implemented in pure Python (regularized
    incomplete beta + bisection inverse) rather than pulling in scipy — the whole
    scoring layer is dependency-light pure math, and bisection is deterministic.

F-015 is PROPOSED. The z-score half of the same decision (which would RAISE a
claim) is deliberately NOT here — its gate thresholds are expert-owned; see the
open-decisions register.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

try:  # OD-05 (LOW_CONFIDENCE_COHORT_N) — the cohort floor below which no curve draws.
    from app.services.intake_options import LOW_CONFIDENCE_COHORT_N as _COHORT_FLOOR
except Exception:  # pragma: no cover - config always present in-app; keep the module importable
    _COHORT_FLOOR = 10

FORMULA_VERSION_ID = "F-015_v1"
OBJECT_TYPE = "peer_distribution"

# Fixed evaluation grid — integer 0..100 (101 points). Stored verbatim so the
# density is identical across runs and processes. Never adaptive (Hard Rule 6).
GRID: tuple[int, ...] = tuple(range(0, 101))

# Densities are rounded to this many places before storage. CPython `math` is
# deterministic, but rounding removes any last-bit ambiguity across platforms.
_ROUND = 12

_INV_SQRT_2PI = 1.0 / math.sqrt(2.0 * math.pi)


# ── low-level numeric helpers ────────────────────────────────────────────────


def _normal_pdf(z: float) -> float:
    """Standard normal pdf φ(z)."""
    return _INV_SQRT_2PI * math.exp(-0.5 * z * z)


def effective_n(weights: list[float]) -> float:
    """Kish effective sample size: (Σw)² / Σw².

    Equals len(weights) when all weights are equal; strictly smaller otherwise.
    """
    sw = math.fsum(weights)
    sw2 = math.fsum(w * w for w in weights)
    if sw2 <= 0.0:
        return 0.0
    return (sw * sw) / sw2


def weighted_mean(xs: list[float], ws: list[float]) -> float:
    sw = math.fsum(ws)
    if sw <= 0.0:
        return 0.0
    return math.fsum(w * x for x, w in zip(xs, ws)) / sw


def weighted_std(xs: list[float], ws: list[float], mean: float) -> float:
    """Reliability-weighted standard deviation.

    Denominator is the reliability-weight correction  Σw − Σw²/Σw , NOT the naive
    Σw. This is the unbiased estimator when weights express reliability rather
    than frequency.
    """
    sw = math.fsum(ws)
    sw2 = math.fsum(w * w for w in ws)
    denom = sw - (sw2 / sw) if sw > 0.0 else 0.0
    if denom <= 0.0:
        return 0.0
    num = math.fsum(w * (x - mean) * (x - mean) for x, w in zip(xs, ws))
    var = num / denom
    return math.sqrt(var) if var > 0.0 else 0.0


def weighted_quantile(sorted_xw: list[tuple[float, float]], total_w: float, q: float) -> float:
    """Weighted quantile via the Hazen (Type-5-like) cumulative-weight rule.

    `sorted_xw` must be sorted ascending by x. `q` in [0,1]. Positions are the
    mid-weight cumulative fractions c_i = (Σ_{j<i} w_j + w_i/2) / Σw, linearly
    interpolated. Deterministic; used for the weighted IQR only.
    """
    if not sorted_xw or total_w <= 0.0:
        return 0.0
    positions: list[float] = []
    running = 0.0
    for _, w in sorted_xw:
        positions.append((running + 0.5 * w) / total_w)
        running += w
    if q <= positions[0]:
        return sorted_xw[0][0]
    if q >= positions[-1]:
        return sorted_xw[-1][0]
    for i in range(1, len(positions)):
        if q <= positions[i]:
            x0, x1 = sorted_xw[i - 1][0], sorted_xw[i][0]
            p0, p1 = positions[i - 1], positions[i]
            if p1 == p0:
                return x1
            return x0 + (x1 - x0) * (q - p0) / (p1 - p0)
    return sorted_xw[-1][0]


def weighted_iqr(xs: list[float], ws: list[float]) -> float:
    sorted_xw = sorted(zip(xs, ws), key=lambda t: t[0])
    total_w = math.fsum(ws)
    q75 = weighted_quantile(sorted_xw, total_w, 0.75)
    q25 = weighted_quantile(sorted_xw, total_w, 0.25)
    return q75 - q25


# ── regularized incomplete beta + inverse (Clopper–Pearson) ──────────────────


def _betacf(a: float, b: float, x: float) -> float:
    """Continued fraction for the incomplete beta (Lentz's method, NR §6.4)."""
    MAXIT = 300
    EPS = 1e-14
    FPMIN = 1e-300
    qab = a + b
    qap = a + 1.0
    qam = a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < FPMIN:
        d = FPMIN
    d = 1.0 / d
    h = d
    for m in range(1, MAXIT + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < FPMIN:
            d = FPMIN
        c = 1.0 + aa / c
        if abs(c) < FPMIN:
            c = FPMIN
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < FPMIN:
            d = FPMIN
        c = 1.0 + aa / c
        if abs(c) < FPMIN:
            c = FPMIN
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < EPS:
            break
    return h


def regularized_incomplete_beta(a: float, b: float, x: float) -> float:
    """I_x(a,b) — the regularized incomplete beta function, in [0,1]."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    ln_bt = (
        math.lgamma(a + b)
        - math.lgamma(a)
        - math.lgamma(b)
        + a * math.log(x)
        + b * math.log(1.0 - x)
    )
    bt = math.exp(ln_bt)
    if x < (a + 1.0) / (a + b + 2.0):
        return bt * _betacf(a, b, x) / a
    return 1.0 - bt * _betacf(b, a, 1.0 - x) / b


def beta_ppf(q: float, a: float, b: float) -> float:
    """Inverse regularized incomplete beta B⁻¹(q; a, b) via bisection.

    Bisection (not Newton) for determinism: no dependence on a starting guess or
    derivative conditioning. Fixed iteration budget with a tight tolerance.
    """
    if q <= 0.0 or a <= 0.0:
        return 0.0
    if q >= 1.0 or b <= 0.0:
        return 1.0
    lo, hi = 0.0, 1.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if regularized_incomplete_beta(a, b, mid) < q:
            lo = mid
        else:
            hi = mid
        if hi - lo < 1e-14:
            break
    return 0.5 * (lo + hi)


# ── result container ─────────────────────────────────────────────────────────


@dataclass
class PeerDistributionResult:
    suppressed: bool
    suppression_reason: str | None
    n_eff: float
    n_eff_int: int
    cohort_size: int
    org_score: float
    percentile: float
    ci_lower: float | None
    ci_upper: float | None
    alpha: float
    ci_one_sided: bool
    ci_clamped: bool
    n_eff_rounded_down: bool
    bandwidth: float | None
    bandwidth_fallback: bool
    mean_w: float
    sigma_w: float
    iqr_w: float
    grid: list[int] = field(default_factory=list)
    density: list[float] = field(default_factory=list)
    peers: list[dict] = field(default_factory=list)

    def to_payload(self) -> dict:
        """The dict stored on the derived_data_item / snapshot. Presentation reads
        this verbatim and never recomputes (DIR-008)."""
        return {
            "formula_version_id": FORMULA_VERSION_ID,
            "object_type": OBJECT_TYPE,
            "proposed": True,  # F-015 caveat travels WITH the number (not just in the spec).
            "suppressed": self.suppressed,
            "suppression_reason": self.suppression_reason,
            "n_eff": round(self.n_eff, 6),
            "n_eff_int": self.n_eff_int,
            "n_eff_rounded_down": self.n_eff_rounded_down,
            "cohort_size": self.cohort_size,
            "org_score": round(self.org_score, 6),
            "percentile": round(self.percentile, 4),
            "ci_lower": None if self.ci_lower is None else round(self.ci_lower, 4),
            "ci_upper": None if self.ci_upper is None else round(self.ci_upper, 4),
            "alpha": self.alpha,
            "ci_one_sided": self.ci_one_sided,
            "ci_clamped": self.ci_clamped,
            "bandwidth": None if self.bandwidth is None else round(self.bandwidth, 8),
            "bandwidth_fallback": self.bandwidth_fallback,
            "mean_w": round(self.mean_w, 6),
            "sigma_w": round(self.sigma_w, 6),
            "iqr_w": round(self.iqr_w, 6),
            "grid": list(self.grid),
            "density": list(self.density),
            "peers": self.peers,
        }


# ── main entry ───────────────────────────────────────────────────────────────


def _weighted_percentile_rank(org_score: float, xs: list[float], ws: list[float], total_w: float) -> float:
    """The SAME weighted rank F-011 stores: (below + 0.5·equal) / total · 100.

    Recomputed here only to place the position marker; F-011's stored value is
    untouched and remains authoritative.
    """
    below = math.fsum(w for x, w in zip(xs, ws) if x < org_score)
    equal = math.fsum(w for x, w in zip(xs, ws) if x == org_score)
    pct = ((below + 0.5 * equal) / total_w) * 100.0
    return min(max(pct, 0.0), 100.0)


def compute_peer_distribution(
    org_score: float,
    peer_scores: list[dict],
    *,
    alpha: float = 0.05,
    cohort_floor: int | None = None,
) -> PeerDistributionResult:
    """Compute the reflected weighted density, the rug, and the CP interval.

    peer_scores: [{"score": float, "weight": float}] — the SAME shape F-011 reads
    (weights from benchmark_membership / normalization). Scores are the benchmark
    metric on the 0–100 scale.

    Returns a PeerDistributionResult. When the cohort is too thin or has no
    dispersion, `suppressed` is True with a stated reason and no curve — a smooth
    density over a handful of effective peers is a picture of nothing.
    """
    floor = _COHORT_FLOOR if cohort_floor is None else cohort_floor

    xs = [float(p["score"]) for p in peer_scores]
    ws = [float(p.get("weight", 1.0)) for p in peer_scores]
    cohort_size = len(xs)

    # No peers / no weight → nothing to draw.
    total_w = math.fsum(ws)
    if cohort_size == 0 or total_w <= 0.0:
        return PeerDistributionResult(
            suppressed=True, suppression_reason="no_peers",
            n_eff=0.0, n_eff_int=0, cohort_size=cohort_size,
            org_score=float(org_score), percentile=0.0,
            ci_lower=None, ci_upper=None, alpha=alpha,
            ci_one_sided=False, ci_clamped=False, n_eff_rounded_down=False,
            bandwidth=None, bandwidth_fallback=False,
            mean_w=0.0, sigma_w=0.0, iqr_w=0.0,
        )

    n_eff = effective_n(ws)
    n_eff_int = int(math.floor(n_eff))
    n_eff_rounded_down = (n_eff_int != n_eff)

    mu = weighted_mean(xs, ws)
    sigma = weighted_std(xs, ws, mu)
    iqr = weighted_iqr(xs, ws)
    percentile = _weighted_percentile_rank(org_score, xs, ws, total_w)

    # The rug: the individual peer points, always available even when the curve
    # is suppressed. Sorted for a stable order.
    peers = [
        {"x": round(x, 6), "weight": round(w, 8)}
        for x, w in sorted(zip(xs, ws), key=lambda t: (t[0], t[1]))
    ]

    # ── suppression: cohort floor on n_eff ───────────────────────────────────
    if n_eff < floor:
        return PeerDistributionResult(
            suppressed=True, suppression_reason=f"n_eff_below_cohort_floor_{floor}",
            n_eff=n_eff, n_eff_int=n_eff_int, cohort_size=cohort_size,
            org_score=float(org_score), percentile=percentile,
            ci_lower=None, ci_upper=None, alpha=alpha,
            ci_one_sided=False, ci_clamped=False, n_eff_rounded_down=n_eff_rounded_down,
            bandwidth=None, bandwidth_fallback=False,
            mean_w=mu, sigma_w=sigma, iqr_w=iqr, peers=peers,
        )

    # ── bandwidth (Silverman), with the IQR-zero fallback ────────────────────
    if sigma <= 0.0:
        # All peers identical → no dispersion. Do NOT floor h to a constant; that
        # would draw a fabricated spread.
        return PeerDistributionResult(
            suppressed=True, suppression_reason="zero_dispersion",
            n_eff=n_eff, n_eff_int=n_eff_int, cohort_size=cohort_size,
            org_score=float(org_score), percentile=percentile,
            ci_lower=None, ci_upper=None, alpha=alpha,
            ci_one_sided=False, ci_clamped=False, n_eff_rounded_down=n_eff_rounded_down,
            bandwidth=None, bandwidth_fallback=False,
            mean_w=mu, sigma_w=sigma, iqr_w=iqr, peers=peers,
        )

    iqr_term = iqr / 1.34 if iqr > 0.0 else 0.0
    bandwidth_fallback = False
    if iqr_term <= 0.0:
        # IQR collapsed but σ>0 — fall back to σ alone and record it.
        spread = sigma
        bandwidth_fallback = True
    else:
        spread = min(sigma, iqr_term)
    h = 0.9 * spread * (n_eff ** (-0.2))

    if h <= 0.0:  # defensive: spread degenerate after the fallback
        return PeerDistributionResult(
            suppressed=True, suppression_reason="zero_bandwidth",
            n_eff=n_eff, n_eff_int=n_eff_int, cohort_size=cohort_size,
            org_score=float(org_score), percentile=percentile,
            ci_lower=None, ci_upper=None, alpha=alpha,
            ci_one_sided=False, ci_clamped=False, n_eff_rounded_down=n_eff_rounded_down,
            bandwidth=None, bandwidth_fallback=bandwidth_fallback,
            mean_w=mu, sigma_w=sigma, iqr_w=iqr, peers=peers,
        )

    # ── reflected KDE on the fixed integer grid ──────────────────────────────
    # f*(x) = f̂(x) + f̂(−x) + f̂(200−x), reflection at the 0 and 100 bounds.
    density: list[float] = []
    inv_wsum_h = 1.0 / (total_w * h)
    for gx in GRID:
        acc = math.fsum(
            w * (
                _normal_pdf((gx - x) / h)
                + _normal_pdf((-gx - x) / h)
                + _normal_pdf((200.0 - gx - x) / h)
            )
            for x, w in zip(xs, ws)
        )
        density.append(round(acc * inv_wsum_h, _ROUND))

    # ── Clopper–Pearson interval on the rank ─────────────────────────────────
    ci_lower, ci_upper, ci_one_sided, ci_clamped = _clopper_pearson(
        percentile, n_eff_int, alpha
    )

    return PeerDistributionResult(
        suppressed=False, suppression_reason=None,
        n_eff=n_eff, n_eff_int=n_eff_int, cohort_size=cohort_size,
        org_score=float(org_score), percentile=percentile,
        ci_lower=ci_lower, ci_upper=ci_upper, alpha=alpha,
        ci_one_sided=ci_one_sided, ci_clamped=ci_clamped,
        n_eff_rounded_down=n_eff_rounded_down,
        bandwidth=h, bandwidth_fallback=bandwidth_fallback,
        mean_w=mu, sigma_w=sigma, iqr_w=iqr,
        grid=list(GRID), density=density, peers=peers,
    )


def _clopper_pearson(percentile: float, n_int: int, alpha: float) -> tuple[float | None, float | None, bool, bool]:
    """Clopper–Pearson interval in PERCENTILE units (0–100).

    k = ⌊ percentile/100 · n_int ⌋ successes in n_int trials.
      lower = 100 · B⁻¹(α/2;   k,   n−k+1)
      upper = 100 · B⁻¹(1−α/2; k+1, n−k)
    At k=0 the lower bound is 0 (one-sided below); at k=n the upper bound is 100
    (one-sided above). Both are recorded, never allowed to produce NaN.
    """
    if n_int < 2:
        return None, None, False, False  # no computable interval

    k = int(math.floor((percentile / 100.0) * n_int))
    k = min(max(k, 0), n_int)

    one_sided = False
    clamped = False

    # Lower bound
    if k <= 0:
        lower = 0.0
        one_sided = True
        clamped = True
    else:
        lower = 100.0 * beta_ppf(alpha / 2.0, k, n_int - k + 1)

    # Upper bound
    if k >= n_int:
        upper = 100.0
        one_sided = True
        clamped = True
    else:
        upper = 100.0 * beta_ppf(1.0 - alpha / 2.0, k + 1, n_int - k)

    lower = min(max(lower, 0.0), 100.0)
    upper = min(max(upper, 0.0), 100.0)
    return lower, upper, one_sided, clamped
