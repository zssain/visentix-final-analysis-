"""Shared v2 clause classifier — the SINGLE source of truth for the
`category_v2 / nlp_confidence_v2 / classifier_version` columns.

Used by BOTH the intake path (so newly-ingested clauses are never left with a NULL
category_v2 — a mirror of the embedding fix) and the batch reclassifier
(`scripts/reclassify_other.py`), so the two paths label clauses identically via the
same local model (Qwen3-8B on Ollama).

Never overwrites the legacy `category` / `nlp_confidence` — writes only the v2 fields.
"""
from __future__ import annotations

# The 8 domains + 'other' (same taxonomy the intake LLM step and the reclassifier use).
TAXONOMY_V2 = [
    "data_sharing", "tracking_cookies", "consumer_rights", "cross_border",
    "sensitive_data", "retention", "children_teens", "ai_automated_decisions", "other",
]

# classifier_version written when the local LLM produced the label…
CLASSIFIER_VERSION = "qwen3-8b-local-v1"
# …and when the LLM was unavailable and we fall back to the deterministic keyword
# label (so category_v2 is still non-NULL, honestly attributed).
KEYWORD_FALLBACK_VERSION = "decompose-keyword-v1"

MAX_CONFIDENCE = 0.95           # cap: never claim more certainty than the reclassifier does


async def classify_one(llm, text: str) -> tuple[str, float]:
    """Classify one clause via the local LLM into (category_v2, confidence).
    Falls back to ('other', low-confidence) on any LLM error — never raises."""
    try:
        result = await llm.classify(text, TAXONOMY_V2)
        cat = result.get("category", "other")
        conf = result.get("confidence", 0.5)
        if cat not in TAXONOMY_V2:
            cat = "other"
        return cat, min(conf, MAX_CONFIDENCE)
    except Exception:  # noqa: BLE001 — batch/live resilience; caller decides fallback labelling
        return "other", 0.3
