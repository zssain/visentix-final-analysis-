"""Benchmark sanity (F17 component 5) — measurement only.

Asserts a cohort's percentile distribution is well-formed and that a synthetic
strong org lands in the upper half. The synthetic org is a pure in-memory score
(never persisted) — so there is nothing to remove from any benchmark table.
Uses the real F-011 percentile formula. Changes nothing.
"""

from __future__ import annotations

from app.services.scoring.formulas_advanced import compute_f011


def distribution_wellformed(peer_scores: list[float]) -> dict:
    """A cohort's percentile ranks should span a sensible range and be monotone
    in the underlying score. Reports facts; asserts nothing here."""
    if not peer_scores:
        return {"status": "empty cohort", "n": 0}
    ordered = sorted(peer_scores)
    pranks = [compute_f011(s, [{"score": p, "weight": 1.0} for p in peer_scores],
                           len(peer_scores)).score for s in ordered]
    monotone = all(pranks[i] <= pranks[i + 1] + 1e-6 for i in range(len(pranks) - 1))
    return {
        "status": "ok", "n": len(peer_scores),
        "min_pct": round(min(pranks), 2), "max_pct": round(max(pranks), 2),
        "monotone_non_decreasing": monotone,
        "spread": round(max(pranks) - min(pranks), 2),
    }


def synthetic_strong_upper_half(peer_scores: list[float], strong: float | None = None) -> dict:
    """Inject a synthetic strong org (score above the cohort median) and confirm it
    ranks in the upper half. In-memory only — no benchmark-table residue."""
    if not peer_scores:
        return {"status": "empty cohort"}
    med = sorted(peer_scores)[len(peer_scores) // 2]
    strong = strong if strong is not None else min(med + 20, 100)
    pr = compute_f011(strong, [{"score": p, "weight": 1.0} for p in peer_scores],
                      len(peer_scores) + 1).score
    return {"synthetic_score": strong, "percentile": round(pr, 2), "upper_half": pr >= 50.0,
            "note": "synthetic org is in-memory only; nothing persisted to remove"}
