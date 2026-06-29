"""Exemplar review service — SME de-identification + approval.

An SME cleans raw candidate text (removes org names, de-identifies),
then approves to set sme_cleaned=true. No un-cleaned text reaches customers.
"""

from __future__ import annotations

import re


class DeIdentificationError(ValueError):
    """Raised when cleaned text still contains identifying tokens."""


# Org names + common identifiers that must be removed during de-identification
# In production, this would be loaded from the organization table dynamically.
KNOWN_ORG_NAMES = {
    "paypal", "stripe", "block", "chime", "robinhood", "sofi", "coinbase",
    "affirm", "plaid", "klarna", "fedex", "ups", "dhl", "xpo logistics",
    "xpo", "c.h. robinson", "j.b. hunt", "ryder", "uber freight", "penske",
    "flexport", "ge", "3m", "caterpillar", "john deere", "honeywell",
    "whirlpool", "rockwell automation", "rockwell", "emerson",
    "stanley black & decker", "stanley", "trane technologies", "trane",
}


def validate_deidentification(
    cleaned_text: str,
    extra_blocked_tokens: set[str] | None = None,
) -> list[str]:
    """Check that cleaned text doesn't contain identifying tokens.

    Returns list of found identifiers. Empty = pass.
    """
    blocked = KNOWN_ORG_NAMES.copy()
    if extra_blocked_tokens:
        blocked |= {t.lower() for t in extra_blocked_tokens}

    text_lower = cleaned_text.lower()
    found = []
    for token in blocked:
        if token and re.search(r'\b' + re.escape(token) + r'\b', text_lower):
            found.append(token)

    return sorted(found)


def validate_exemplar_for_approval(
    cleaned_text: str | None,
    maturity_note: str | None,
) -> str | None:
    """Validate an exemplar is ready for approval. Returns error message or None."""
    if not cleaned_text or len(cleaned_text.strip()) < 20:
        return "Cannot approve without a de-identified cleaned text (min 20 chars)."

    if not maturity_note or len(maturity_note.strip()) < 5:
        return "Cannot approve without a maturity note."

    identifiers = validate_deidentification(cleaned_text)
    if identifiers:
        return f"Cleaned text contains identifying tokens: {identifiers}. De-identify before approving."

    return None  # ok
