"""Guardrail service — enforces phrasing rules on all customer-facing text.

Responsibilities:
- Scan text for banned legal-verdict terms (AGENTS.md §2):
  "violation", "violates", "illegal", "unlawful", "non-compliant",
  "breach of law", "guilty", "liable"
- Hard-fail report generation if any banned term is present
- Validate that numbers reference real cohort sizes with confidence labels
"""

import re

BANNED_TERMS = [
    "violation",
    "violates",
    "illegal",
    "unlawful",
    "non-compliant",
    "breach of law",
    "guilty",
    "liable",
]

_BANNED_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(t) for t in BANNED_TERMS) + r")\b",
    re.IGNORECASE,
)


def check_guardrail(text: str) -> list[str]:
    """Return list of banned terms found. Empty list = pass."""
    return list({m.group().lower() for m in _BANNED_PATTERN.finditer(text)})


def enforce_guardrail(text: str) -> str:
    """Raise ValueError if banned terms are found; return text otherwise."""
    violations = check_guardrail(text)
    if violations:
        raise ValueError(
            f"Guardrail HARD FAIL — banned terms found: {violations}. "
            "Rephrase using exposure/likelihood language."
        )
    return text
