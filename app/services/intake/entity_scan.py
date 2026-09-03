"""Deterministic detection of several self-identifying notices in one intake.

This module produces a data-quality flag only. It never calls an LLM, blocks an
assessment, changes a score, or guesses a confidence value.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.services.intake.decompose import DecomposedNotice


@dataclass(frozen=True)
class EntityScanResult:
    flagged: bool
    detected_entities: tuple[str, ...]
    evidence: tuple[dict, ...]
    confidence: None = None


_ENTITY = r"[A-Z][A-Za-z0-9&'’.-]*(?:[ \t]+[A-Z][A-Za-z0-9&'’.-]*){0,7}"
_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "entity_privacy_heading",
        re.compile(rf"^\s*#{{0,3}}\s*(?P<entity>{_ENTITY})[ \t]+Privacy[ \t]+(?:Policy|Notice)\s*$", re.MULTILINE),
    ),
    (
        "privacy_heading_for_entity",
        re.compile(rf"^\s*Privacy[ \t]+(?:Policy|Notice)[ \t]+(?:of|for)[ \t]+(?P<entity>{_ENTITY})\s*$", re.MULTILINE),
    ),
    (
        "defined_as_we",
        re.compile(
            rf"\b(?P<entity>{_ENTITY})\s*\(\s*[\"“']?(?:we|us|our)[\"”']?",
        ),
    ),
    (
        "notice_describes_entity",
        re.compile(
            rf"\b(?:[Tt]his|[Oo]ur)[ \t]+[Pp]rivacy[ \t]+(?:[Pp]olicy|[Nn]otice)[ \t]+"
            rf"(?:describes|explains)[ \t]+how[ \t]+(?P<entity>{_ENTITY})[ \t]+"
            r"(?:collects|uses|shares|processes|handles)\b",
        ),
    ),
    (
        "at_entity_we",
        re.compile(rf"\bAt[ \t]+(?P<entity>{_ENTITY}),?[ \t]+(?:we|our)\b"),
    ),
)

_TRAILING_LABELS = re.compile(r"\s+(?:Privacy|Policy|Notice)$", re.IGNORECASE)


def _clean_entity(raw: str) -> str:
    entity = " ".join(raw.strip(" \t.,:;()[]{}\"'“”").split())
    return _TRAILING_LABELS.sub("", entity).strip()


def scan_notice_entities(notice: DecomposedNotice) -> EntityScanResult:
    """Return a flag when at least two distinct self-identifying names exist."""
    names: dict[str, str] = {}
    evidence: list[dict] = []
    seen_evidence: set[tuple[str, int, str]] = set()

    for section in notice.sections:
        # Title + body captures Markdown headings as well as paragraph-based
        # decomposition. Evidence records structure, never the notice excerpt.
        searchable = f"{section.title}\n{section.text}"
        for signal, pattern in _PATTERNS:
            for match in pattern.finditer(searchable):
                entity = _clean_entity(match.group("entity"))
                if len(entity) < 2:
                    continue
                key = entity.casefold()
                names.setdefault(key, entity)
                marker = (key, section.sequence, signal)
                if marker not in seen_evidence:
                    evidence.append({
                        "entity": names[key],
                        "section_sequence": section.sequence,
                        "signal": signal,
                    })
                    seen_evidence.add(marker)

    ordered_names = tuple(names.values())
    flagged = len(ordered_names) >= 2
    if not flagged:
        # A non-flag does not persist or expose incidental single-name matches.
        return EntityScanResult(False, (), ())
    return EntityScanResult(True, ordered_names, tuple(evidence))
