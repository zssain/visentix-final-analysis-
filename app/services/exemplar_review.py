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

# Structural PII patterns that must never survive into an approved exemplar.
# Emails and URLs identify a source even after org names are stripped, so they
# block approval exactly like a known org name (F06 de-id gate; Phase 5.4).
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
URL_RE = re.compile(r"(?:https?://|www\.)[^\s)\]}<>\"']+", re.IGNORECASE)
REDACTION = "[REDACTED]"


def validate_deidentification(
    cleaned_text: str,
    extra_blocked_tokens: set[str] | None = None,
) -> list[str]:
    """Check that cleaned text doesn't contain identifying tokens.

    Scans for known org names, any caller-supplied blocked tokens, and structural
    PII (email addresses, URLs). Returns the list of found identifiers — empty = pass.
    """
    blocked = KNOWN_ORG_NAMES.copy()
    if extra_blocked_tokens:
        blocked |= {t.lower() for t in extra_blocked_tokens}

    text_lower = cleaned_text.lower()
    found = []
    for token in blocked:
        if token and re.search(r'\b' + re.escape(token) + r'\b', text_lower):
            found.append(token)

    # Structural PII — reported with a label so the reason is clear in the error.
    found += [f"email:{m.group(0)}" for m in EMAIL_RE.finditer(cleaned_text)]
    found += [f"url:{m.group(0)}" for m in URL_RE.finditer(cleaned_text)]

    return sorted(found)


def redact(text: str, extra_blocked_tokens: set[str] | None = None) -> str:
    """Replace identifying tokens (org names, emails, URLs, caller tokens) with
    [REDACTED]. Best-effort cleaner used to prepare candidate exemplar text; the
    result must still pass validate_deidentification before approval."""
    out = URL_RE.sub(REDACTION, text)
    out = EMAIL_RE.sub(REDACTION, out)
    tokens = {t.lower() for t in (extra_blocked_tokens or set())} | KNOWN_ORG_NAMES
    for token in sorted(tokens, key=len, reverse=True):
        if token:
            out = re.sub(r'\b' + re.escape(token) + r'\b', REDACTION, out, flags=re.IGNORECASE)
    return out


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
