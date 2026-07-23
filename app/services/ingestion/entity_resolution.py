"""Exact/normalized entity resolution for security_event → organization.

Matches a breach report's `entity_name_raw` against known organization names
(the `organization_alias` legal_name values + `organization.name`) using
DETERMINISTIC normalization only — NO fuzzy matching (no edit distance, no token
overlap, no substring/subsidiary inference). A name resolves iff its normalized
form equals a known normalized name that maps to exactly ONE organization.

Safety properties:
- Ambiguous normalized names (mapping to >1 organization) are NEVER guessed —
  they are excluded from the index, so a collision leaves the event unresolved.
- A subsidiary ("Conduent Business Services LLC") does NOT match its public parent
  ("Conduent Incorporated") — different normalized forms, no fuzzy bridge.
- Non-matches are a review queue, not an error: most HHS covered entities are
  non-public healthcare orgs absent from the corporate corpus.

Pure and side-effect-free: the live driver (scripts/ingest/resolve_security_events.py)
does the DB I/O and idempotent writes.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable

# Trailing legal-entity designators stripped during normalization. Conservative:
# only true entity suffixes — NOT meaningful name parts like group/holdings/partners.
_LEGAL_SUFFIXES = {
    "inc", "incorporated", "corp", "corporation", "company", "co", "llc", "lp",
    "llp", "lllp", "plc", "pllc", "pc", "pa", "ltd", "limited", "sa", "nv", "ag",
}


def normalize_name(s: str | None) -> str:
    """Deterministic name key: lowercase, drop parentheticals & smart quotes, strip
    punctuation, collapse whitespace, remove trailing legal suffixes. Returns '' for
    empty/None (which never matches — '' is excluded from the index)."""
    if not s:
        return ""
    s = s.lower()
    s = re.sub(r"[‘’“”]", " ", s)      # smart quotes → space
    s = re.sub(r"\([^)]*\)", " ", s)                        # parentheticals (nicknames/DBAs)
    s = re.sub(r"[^a-z0-9]+", " ", s).strip()               # punctuation → space
    toks = s.split()
    while toks and toks[-1] in _LEGAL_SUFFIXES:             # trailing "inc"/"llc"/…
        toks.pop()
    return " ".join(toks)


@dataclass
class NameIndex:
    """normalized name → organization_id, for names resolving to exactly one org.
    `ambiguous` holds normalized names seen under >1 organization (never matched)."""
    by_norm: dict[str, str] = field(default_factory=dict)
    ambiguous: set[str] = field(default_factory=set)

    def lookup(self, raw_name: str | None) -> str | None:
        key = normalize_name(raw_name)
        if not key or key in self.ambiguous:
            return None
        return self.by_norm.get(key)


def build_name_index(pairs: Iterable[tuple[str, str]]) -> NameIndex:
    """Build a NameIndex from (name, organization_id) pairs (aliases + org names).
    A normalized name mapping to more than one DISTINCT org is marked ambiguous and
    removed from the resolvable index."""
    acc: dict[str, set[str]] = {}
    for name, org_id in pairs:
        key = normalize_name(name)
        if not key or org_id is None:
            continue
        acc.setdefault(key, set()).add(str(org_id))
    idx = NameIndex()
    for key, orgs in acc.items():
        if len(orgs) == 1:
            idx.by_norm[key] = next(iter(orgs))
        else:
            idx.ambiguous.add(key)
    return idx


@dataclass
class Match:
    event_id: str
    organization_id: str
    entity_name_raw: str
    matched_norm: str


@dataclass
class ResolvedMatch:
    """Generic resolution result for any record type (security_event, enforcement_record)."""
    record_id: str
    organization_id: str
    name: str
    matched_norm: str


def resolve_records(records: Iterable[dict], index: NameIndex, *,
                    id_field: str, name_field: str,
                    fallback_name_field: str | None = None) -> list[ResolvedMatch]:
    """Resolve records whose name resolves to a single org. Reads `name_field`,
    falling back to `fallback_name_field` when the primary is empty (e.g.
    enforcement_record.entity_name → target_company). Pure + idempotent: unmatched
    records are omitted; running twice over the same inputs yields the same matches."""
    out: list[ResolvedMatch] = []
    for r in records:
        name = r.get(name_field) or (r.get(fallback_name_field) if fallback_name_field else None)
        org_id = index.lookup(name)
        if org_id is not None:
            out.append(ResolvedMatch(record_id=r[id_field], organization_id=org_id,
                                     name=name, matched_norm=normalize_name(name)))
    return out


def resolve_events(events: Iterable[dict], index: NameIndex) -> list[Match]:
    """Return one Match per event whose entity_name_raw resolves to a single org.
    Thin wrapper over resolve_records for the security_event field names (kept for
    backward compatibility). Pure + idempotent."""
    return [Match(event_id=m.record_id, organization_id=m.organization_id,
                  entity_name_raw=m.name, matched_norm=m.matched_norm)
            for m in resolve_records(events, index, id_field="event_id",
                                     name_field="entity_name_raw")]
