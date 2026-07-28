"""Shared helpers for the F17 evaluation harness (measurement only).

Pure reads via the IPv4 pooler (PostgREST count/scan times out on 684k rows).
Nothing here writes a score, weight, threshold, or a gold label.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GOLD_SET_PATH = ROOT / "logs" / "eval" / "gold_set_v1.json"
GOLD_SET_CSV = ROOT / "logs" / "eval" / "gold_set_v1.csv"
GOLD_SET_VERSION = "v1"

# category_v2 vocabulary (8 legacy domain slugs + other) — matches gold_domain.
DOMAINS = [
    "consumer_rights", "data_sharing", "tracking_cookies", "cross_border",
    "sensitive_data", "retention", "children_teens", "ai_automated_decisions", "other",
]

# Confidence bands — the §8 VCI band cutoffs applied to the CLAUSE-level
# confidence signal (nlp_confidence_v2 × 100). VCI itself is a notice-level
# composite; at clause granularity nlp_confidence_v2 is the confidence signal,
# and §8's cutoffs are reused so the calibration study is band-consistent.
VCI_BANDS = [
    ("very_high", 90, 100),
    ("high", 75, 89),
    ("moderate", 60, 74),
    ("low", 40, 59),
    ("very_low", 0, 39),
]

SOURCE_GROUPS = ["fresh_2026", "upload_rehearsal", "legacy"]


def band_of(confidence_0_1: float | None) -> str:
    """Map a 0–1 clause confidence to a §8 band label."""
    c = (confidence_0_1 or 0.0) * 100
    for label, lo, hi in VCI_BANDS:
        if lo <= c <= hi:
            return label
    return "very_low"


def conn():
    """psycopg connection via the migration runner's pooler resolver."""
    import psycopg

    import scripts.db.apply_and_record as _mig
    kw, _ = _mig._conn_kwargs()
    return psycopg.connect(**kw)
