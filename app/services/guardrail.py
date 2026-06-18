"""Guardrail service — enforces phrasing rules on all customer-facing text.

Hard safety filter: blocks legal-verdict language so all output uses only
exposure/likelihood phrasing. Runs at report-draft time.

Rules:
- Banned terms (case-insensitive, word-boundary) from config/banned_terms.txt.
- Source excerpts (inside quotation marks) are exempt — verbatim quotes from
  enforcement records may contain banned terms, but GENERATED prose may not.
- Extensible: add terms to config/banned_terms.txt without code changes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"

# ── Source excerpt markers ────────────────────────────────────
# Text inside these delimiters is treated as verbatim source material,
# NOT generated prose. Banned terms inside quotes are allowed.
QUOTE_PATTERN = re.compile(
    r'"[^"]*"|'        # double quotes
    r"'[^']*'|"        # single quotes
    r"\u201c[^\u201d]*\u201d|"  # smart quotes ""
    r"\[source:[^\]]*\]",       # [source: ...] tags
)


@dataclass
class BannedSpan:
    """A banned term found in text with its position."""

    term: str
    start: int
    end: int
    in_source_excerpt: bool


def load_banned_terms(path: Path | None = None) -> list[str]:
    """Load banned terms from config/banned_terms.txt."""
    p = path or (CONFIG_DIR / "banned_terms.txt")
    terms = []
    with open(p) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                terms.append(line.lower())
    return terms


def _build_pattern(terms: list[str]) -> re.Pattern:
    """Build a regex pattern matching any banned term at word boundaries."""
    # Sort by length descending so multi-word terms match before sub-terms
    sorted_terms = sorted(terms, key=len, reverse=True)
    escaped = [re.escape(t) for t in sorted_terms]
    return re.compile(r"\b(" + "|".join(escaped) + r")\b", re.IGNORECASE)


# Load at import time (extensible via config file)
BANNED_TERMS = load_banned_terms()
_BANNED_PATTERN = _build_pattern(BANNED_TERMS)


def _find_source_ranges(text: str) -> list[tuple[int, int]]:
    """Find character ranges that are inside source excerpts (quoted material)."""
    return [(m.start(), m.end()) for m in QUOTE_PATTERN.finditer(text)]


def _is_in_source(pos: int, source_ranges: list[tuple[int, int]]) -> bool:
    """Check if a character position falls inside a source excerpt."""
    return any(start <= pos < end for start, end in source_ranges)


def check_text(text: str) -> list[BannedSpan]:
    """Scan text for banned terms. Returns list of BannedSpan with positions.

    Source excerpts (quoted text) are flagged but marked in_source_excerpt=True.
    Only spans with in_source_excerpt=False represent violations in generated prose.
    """
    source_ranges = _find_source_ranges(text)
    spans = []

    for m in _BANNED_PATTERN.finditer(text):
        in_source = _is_in_source(m.start(), source_ranges)
        spans.append(BannedSpan(
            term=m.group().lower(),
            start=m.start(),
            end=m.end(),
            in_source_excerpt=in_source,
        ))

    return spans


def check_generated_prose(text: str) -> list[BannedSpan]:
    """Check ONLY generated prose (excludes source excerpts).

    Returns banned spans found in non-quoted text. Empty = pass.
    """
    return [s for s in check_text(text) if not s.in_source_excerpt]


def enforce(text: str) -> str:
    """Hard-fail if any banned term appears in generated prose.

    Source excerpts (quoted) are allowed. Generated prose is not.
    Raises GuardrailError with offending terms and positions.
    """
    violations = check_generated_prose(text)
    if violations:
        terms = sorted({v.term for v in violations})
        positions = [(v.term, v.start, v.end) for v in violations]
        raise GuardrailError(
            f"Guardrail HARD FAIL — banned terms in generated prose: {terms}. "
            f"Positions: {positions}. "
            "Rephrase using exposure/likelihood language. "
            "See docs/LANGUAGE.md for approved alternatives.",
            terms=terms,
            spans=violations,
        )
    return text


class GuardrailError(ValueError):
    """Raised when generated text contains banned legal-verdict language."""

    def __init__(self, message: str, terms: list[str] | None = None,
                 spans: list[BannedSpan] | None = None):
        super().__init__(message)
        self.terms = terms or []
        self.spans = spans or []


# ── Legacy compatibility (used by existing code) ─────────────

def check_guardrail(text: str) -> list[str]:
    """Return list of banned terms found in prose. Empty = pass."""
    return sorted({s.term for s in check_generated_prose(text)})


def enforce_guardrail(text: str) -> str:
    """Legacy wrapper for enforce()."""
    return enforce(text)
