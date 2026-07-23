"""Decompose notice text into sections and clauses.

Matches the existing corpus schema: privacy_notice -> notice_section -> disclosure_clause.
Classification uses the VICBNF v2 30-type taxonomy loaded from
config/clause_taxonomy.json, producing (domain_id, clause_type, legacy_slug).
The legacy `category` field is always set to `legacy_slug` so downstream scoring
code (F-002..F-007, findings.py, heatmap.py) keeps working unchanged.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

# ── Load taxonomy from single source of truth ────────────────

_TAXONOMY_PATH = Path(__file__).resolve().parents[3] / "config" / "clause_taxonomy.json"

with open(_TAXONOMY_PATH) as _f:
    CLAUSE_TAXONOMY: list[dict] = json.load(_f)

# Build lookup structures
_CLAUSE_TYPE_ENTRIES: list[dict] = CLAUSE_TAXONOMY  # alias for clarity

# Legacy domain keywords (kept as a FALLBACK when no clause_type matches)
DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "data_sharing": [
        "share", "third part", "disclose", "service provider", "partner",
        "affiliate", "vendor", "data broker",
    ],
    "tracking_cookies": [
        "cookie", "tracking", "pixel", "beacon", "analytics", "advertising",
        "fingerprint", "local storage",
    ],
    "consumer_rights": [
        "right to", "access", "delete", "correct", "opt out", "opt-out",
        "portability", "appeal", "request",
    ],
    "cross_border": [
        "transfer", "cross-border", "international", "outside", "adequacy",
        "standard contractual", "eu", "gdpr",
    ],
    "sensitive_data": [
        "sensitive", "biometric", "health", "genetic", "racial", "ethnic",
        "sexual orientation", "religious", "political",
    ],
    "retention": [
        "retain", "retention", "keep", "store", "delete after", "period",
        "how long",
    ],
    "children_teens": [
        "children", "child", "minor", "teen", "coppa", "age", "parental",
        "under 13", "under 16",
    ],
    "ai_automated_decisions": [
        "automat", "ai", "artificial intelligence", "algorithm", "profiling",
        "machine learning", "decision", "inference",
    ],
}

# Concrete-noun / specificity signals for transparency scoring
_SPECIFICITY_SIGNALS = [
    # Named parties / concrete nouns
    r"\b\d+\s*(days?|months?|years?|hours?)\b",  # concrete timeframes
    r"\b(google|facebook|meta|amazon|apple|microsoft|stripe|paypal)\b",  # named parties
    r"\b[A-Z][a-z]+(?:\s[A-Z][a-z]+)+\b",  # Proper Nouns (multi-word)
    r"\b\d+%\b",  # percentages
    r"\b(email|phone|address|name|ip address|device id|ssn|social security)\b",
    r"\b(encryption|aes|tls|ssl|https|two-factor|multi-factor|mfa)\b",
    r"\b(annual|quarterly|monthly|weekly|daily)\b",  # frequency
    r"\b(ccpa|gdpr|cpra|coppa|hipaa|glba|ferpa|vcdpa|ctdpa)\b",  # named laws
]
_SPECIFICITY_PATTERNS = [re.compile(p, re.IGNORECASE) for p in _SPECIFICITY_SIGNALS]

_VAGUE_SIGNALS = [
    "may", "might", "could", "possibly", "generally", "sometimes",
    "certain", "various", "appropriate", "reasonable", "as needed",
    "from time to time", "at our discretion", "as applicable",
]


# ── Data classes ─────────────────────────────────────────────

@dataclass
class DecomposedSection:
    section_id: str
    title: str
    section_type: str
    sequence: int
    text: str


@dataclass
class DecomposedClause:
    clause_id: str
    section_id: str
    raw_text: str
    normalized_text: str
    category: str           # legacy slug (one of 9) — scoring depends on this
    ambiguity_score: float
    readability_score: float
    nlp_confidence: float
    # VICBNF v2 taxonomy fields
    domain_id: str = ""     # CR/DC/SH/RT/AI/SEC/TRK/XB or ""
    clause_type: str = ""   # one of 30 types or ""
    transparency_score: float = 0.0
    # v2 category (never NULL once classified) — set by the intake LLM step, mirror of
    # the reclassifier. Defaults None so decompose()-only callers can fill it later.
    category_v2: str | None = None
    nlp_confidence_v2: float | None = None
    classifier_version: str | None = None


@dataclass
class DecomposedNotice:
    sections: list[DecomposedSection] = field(default_factory=list)
    clauses: list[DecomposedClause] = field(default_factory=list)


# ── Classification ───────────────────────────────────────────

def classify_clause(text: str) -> tuple[str, float]:
    """Classify a clause using the legacy 9-slug taxonomy.

    Returns (legacy_slug, confidence). This is the backward-compatible API
    that existing scoring code (F-002..F-007, findings.py) calls.
    """
    domain_id, clause_type, legacy_slug, confidence = classify_clause_v2(text)
    return legacy_slug, confidence


def classify_clause_v2(text: str) -> tuple[str, str, str, float]:
    """Classify a clause using the VICBNF v2 30-type taxonomy.

    Returns (domain_id, clause_type, legacy_slug, confidence).
    Strategy:
      1. Score each of the 30 clause_types by keyword hits.
      2. Best clause_type wins → returns its domain_id + legacy_slug.
      3. If no clause_type matches, fall back to legacy domain keywords.
      4. If nothing matches, return ("", "", "other", 0.5).
    """
    text_lower = text.lower()

    # Phase 1: try fine-grained clause_type matching
    best_entry = None
    best_hits = 0

    for entry in _CLAUSE_TYPE_ENTRIES:
        hits = sum(1 for kw in entry["keywords"] if kw in text_lower)
        if hits > best_hits:
            best_hits = hits
            best_entry = entry

    if best_entry and best_hits > 0:
        confidence = min(0.5 + best_hits * 0.1, 0.9)
        return (
            best_entry["domain_id"],
            best_entry["clause_type"],
            best_entry["legacy_slug"],
            round(confidence, 2),
        )

    # Phase 2: fall back to legacy domain-level keywords
    domain_scores: dict[str, int] = {}
    for domain, keywords in DOMAIN_KEYWORDS.items():
        hits = sum(1 for kw in keywords if kw in text_lower)
        if hits > 0:
            domain_scores[domain] = hits

    if domain_scores:
        best_domain = max(domain_scores, key=domain_scores.get)  # type: ignore[arg-type]
        confidence = min(0.5 + domain_scores[best_domain] * 0.1, 0.9)
        # Map legacy slug → a domain_id (best effort)
        domain_id = _legacy_to_domain_id(best_domain)
        return domain_id, "", best_domain, round(confidence, 2)

    return "", "", "other", 0.5


def _legacy_to_domain_id(slug: str) -> str:
    """Map a legacy 9-slug to its VICBNF domain_id (best effort)."""
    mapping = {
        "consumer_rights": "CR",
        "data_sharing": "SH",
        "tracking_cookies": "TRK",
        "retention": "RT",
        "ai_automated_decisions": "AI",
        "cross_border": "XB",
        "sensitive_data": "DC",
        "children_teens": "DC",
        "other": "",
    }
    return mapping.get(slug, "")


# ── Transparency score ───────────────────────────────────────

def compute_transparency(text: str) -> float:
    """Compute clause-level transparency score (0-1).

    Measures specificity: presence of concrete nouns, quantities, named parties,
    and specific timeframes raises the score. Vague-only language lowers it.
    Based on the VICBNF spec's "Transparent Clauses / Relevant Clauses" notion
    applied at the individual clause level.
    """
    if not text or len(text.strip()) < 10:
        return 0.0

    words = text.split()
    word_count = len(words)
    if word_count == 0:
        return 0.0

    # Count specificity signals
    specific_hits = sum(
        len(p.findall(text)) for p in _SPECIFICITY_PATTERNS
    )

    # Count vague signals
    text_lower = text.lower()
    vague_hits = sum(1 for v in _VAGUE_SIGNALS if v in text_lower)

    # Specificity ratio: specific signals per 10 words (normalized)
    specificity = min(specific_hits / max(word_count / 10, 1), 1.0)

    # Vagueness ratio
    vagueness = min(vague_hits / max(word_count / 10, 1), 1.0)

    # Transparency = specificity - vagueness, clamped to [0.1, 1.0]
    # Floor of 0.1 so even vague clauses get a non-zero score
    score = max(0.1, min(1.0, 0.5 + specificity * 0.4 - vagueness * 0.3))
    return round(score, 4)


# ── Ambiguity + readability (unchanged) ──────────────────────

def compute_ambiguity(text: str) -> float:
    """Estimate clause ambiguity (0 = clear, 1 = very ambiguous).

    Heuristic: vague words / total words.
    """
    vague_words = {"may", "might", "could", "possibly", "generally",
                   "sometimes", "certain", "various", "appropriate",
                   "reasonable", "as needed", "from time to time"}
    words = text.lower().split()
    if not words:
        return 0.0
    vague_count = sum(1 for w in words if w in vague_words)
    return round(min(vague_count / len(words), 0.2), 4)


def compute_readability(text: str) -> float:
    """Estimate readability (0 = hard to read, 1 = very readable).

    Simplified: shorter sentences + common words = more readable.
    """
    sentences = re.split(r'[.!?]+', text)
    sentences = [s.strip() for s in sentences if s.strip()]
    if not sentences:
        return 0.0

    avg_length = sum(len(s.split()) for s in sentences) / len(sentences)
    readability = max(0.0, min(1.0, 1.0 - (avg_length - 10) / 40))
    return round(readability, 4)


# ── Decomposition ────────────────────────────────────────────

def decompose(text: str) -> DecomposedNotice:
    """Decompose notice text into sections and clauses.

    Uses the VICBNF v2 30-type taxonomy for classification. The legacy
    `category` field is always set to the backward-compatible slug.
    """
    result = DecomposedNotice()
    sections = _split_sections(text)

    for seq, (title, section_text) in enumerate(sections):
        section_id = str(uuid4())
        stype = _infer_section_type(title)

        result.sections.append(DecomposedSection(
            section_id=section_id,
            title=title,
            section_type=stype,
            sequence=seq,
            text=section_text,
        ))

        paragraphs = _split_clauses(section_text)
        for para in paragraphs:
            if len(para.strip()) < 20:
                continue

            normalized = para.lower().strip()
            domain_id, clause_type, legacy_slug, confidence = classify_clause_v2(para)
            ambiguity = compute_ambiguity(para)
            readability = compute_readability(para)
            transparency = compute_transparency(para)

            result.clauses.append(DecomposedClause(
                clause_id=str(uuid4()),
                section_id=section_id,
                raw_text=para.strip(),
                normalized_text=normalized,
                category=legacy_slug,       # backward compat for scoring
                ambiguity_score=ambiguity,
                readability_score=readability,
                nlp_confidence=confidence,
                domain_id=domain_id,
                clause_type=clause_type,
                transparency_score=transparency,
            ))

    return result


# ── Section splitting (unchanged) ────────────────────────────

def _split_sections(text: str) -> list[tuple[str, str]]:
    """Split text into (title, body) sections."""
    parts = re.split(r'\n#{1,3}\s+', text)
    if len(parts) > 2:
        sections = []
        for i, part in enumerate(parts):
            if i == 0 and part.strip():
                sections.append(("Introduction", part.strip()))
            elif part.strip():
                lines = part.split("\n", 1)
                title = lines[0].strip()
                body = lines[1].strip() if len(lines) > 1 else ""
                sections.append((title, body))
        return sections

    blocks = re.split(r'\n\s*\n', text)
    if len(blocks) >= 3:
        sections = []
        for i, block in enumerate(blocks):
            if block.strip():
                lines = block.strip().split("\n", 1)
                title = lines[0][:80] if len(lines[0]) < 80 else f"Section {i+1}"
                body = block.strip()
                sections.append((title, body))
        return sections

    return [("Full Notice", text.strip())]


def _split_clauses(section_text: str) -> list[str]:
    """Split section into clause-level paragraphs."""
    parts = re.split(r'\n\s*\n|\n(?=[-\u2022*]\s)', section_text)
    return [p.strip() for p in parts if p.strip()]


def _infer_section_type(title: str) -> str:
    """Infer section type from title."""
    title_lower = title.lower()
    if any(w in title_lower for w in ["introduct", "overview", "about"]):
        return "general"
    if any(w in title_lower for w in ["collect", "gather", "data we"]):
        return "collection"
    if any(w in title_lower for w in ["share", "disclos", "third"]):
        return "sharing"
    if any(w in title_lower for w in ["right", "choice", "opt"]):
        return "rights"
    if any(w in title_lower for w in ["secur", "protect"]):
        return "security"
    if any(w in title_lower for w in ["retain", "keep", "delet"]):
        return "retention"
    if any(w in title_lower for w in ["contact", "question"]):
        return "contact"
    return "general"
