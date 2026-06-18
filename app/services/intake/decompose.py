"""Decompose notice text into sections and clauses.

Matches the existing corpus schema: privacy_notice → notice_section → disclosure_clause.
Classification uses the 8 taxonomy domains + ambiguity/readability/nlp_confidence.
All new rows — never touches existing corpus data.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from uuid import uuid4

# Section heading patterns (matches common privacy notice structures)
SECTION_PATTERNS = [
    re.compile(r"^#{1,3}\s+(.+)$", re.MULTILINE),  # markdown headings
    re.compile(r"^([A-Z][A-Za-z\s]{5,60})\n", re.MULTILINE),  # Title Case lines
    re.compile(r"^\d+\.\s+(.+)$", re.MULTILINE),  # numbered sections
]

# Domain classification keywords
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
    category: str
    ambiguity_score: float
    readability_score: float
    nlp_confidence: float


@dataclass
class DecomposedNotice:
    sections: list[DecomposedSection] = field(default_factory=list)
    clauses: list[DecomposedClause] = field(default_factory=list)


def classify_clause(text: str) -> tuple[str, float]:
    """Classify a clause into one of the 8 taxonomy domains.

    Returns (domain, confidence). Uses keyword matching to mirror
    the existing corpus classification approach.
    """
    text_lower = text.lower()
    scores: dict[str, int] = {}

    for domain, keywords in DOMAIN_KEYWORDS.items():
        hits = sum(1 for kw in keywords if kw in text_lower)
        if hits > 0:
            scores[domain] = hits

    if not scores:
        return "other", 0.5

    best = max(scores, key=scores.get)
    confidence = min(0.5 + scores[best] * 0.1, 0.9)
    return best, round(confidence, 2)


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
    # Shorter sentences = more readable. 10 words → 1.0, 40 words → 0.25
    readability = max(0.0, min(1.0, 1.0 - (avg_length - 10) / 40))
    return round(readability, 4)


def decompose(text: str) -> DecomposedNotice:
    """Decompose notice text into sections and clauses.

    Mirrors the existing corpus pipeline: splits on headings into sections,
    then splits each section into paragraph-level clauses, classifying each.
    """
    result = DecomposedNotice()

    # Split into sections
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

        # Split section into clauses (paragraph-level)
        paragraphs = _split_clauses(section_text)

        for para in paragraphs:
            if len(para.strip()) < 20:
                continue

            normalized = para.lower().strip()
            category, confidence = classify_clause(para)
            ambiguity = compute_ambiguity(para)
            readability = compute_readability(para)

            result.clauses.append(DecomposedClause(
                clause_id=str(uuid4()),
                section_id=section_id,
                raw_text=para.strip(),
                normalized_text=normalized,
                category=category,
                ambiguity_score=ambiguity,
                readability_score=readability,
                nlp_confidence=confidence,
            ))

    return result


def _split_sections(text: str) -> list[tuple[str, str]]:
    """Split text into (title, body) sections."""
    # Try markdown headings first
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

    # Try double-newline separation
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

    # Fallback: single section
    return [("Full Notice", text.strip())]


def _split_clauses(section_text: str) -> list[str]:
    """Split section into clause-level paragraphs."""
    # Split on double newlines or bullet points
    parts = re.split(r'\n\s*\n|\n(?=[-•*]\s)', section_text)
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
