"""Entity resolution for security_event → organization: exact/normalized matching,
ambiguity safety, no-fuzzy guarantee, idempotency. Pure functions, no DB."""
from app.services.ingestion.entity_resolution import (
    Match, build_name_index, normalize_name, resolve_events, resolve_records,
)

# (name, organization_id) pairs standing in for organization_alias + organization.name
ORG_NAMES = [
    ("DaVita Inc.", "org-davita"),
    ("Aflac Incorporated", "org-aflac"),
    ("Insulet Corporation", "org-insulet"),
    ("Option Care Health, Inc.", "org-optioncare"),
    ("Conduent Incorporated", "org-conduent"),        # the PUBLIC PARENT
    # two DISTINCT orgs share a normalized form → ambiguous, never matched
    ("Summit Health LLC", "org-summit-a"),
    ("Summit Health, Inc.", "org-summit-b"),
]


def test_normalize_name_cases():
    assert normalize_name("DaVita Inc.") == "davita"
    assert normalize_name("Aflac Incorporated (“Aflac”)") == "aflac"   # smart-quote parenthetical
    assert normalize_name("Option Care Health, Inc.") == "option care health"
    assert normalize_name("  ACME   HEALTH  SYSTEM , LLC ") == "acme health system"
    assert normalize_name("Insulet Corporation") == "insulet"
    assert normalize_name(None) == "" and normalize_name("") == ""
    assert normalize_name("LLC") == ""                # all-suffix → empty (never matches)


def test_exact_and_normalized_match():
    idx = build_name_index(ORG_NAMES)
    events = [
        {"event_id": "e1", "entity_name_raw": "DaVita Inc."},          # exact
        {"event_id": "e2", "entity_name_raw": "DAVITA, INC"},          # normalized variant
        {"event_id": "e3", "entity_name_raw": "Aflac Incorporated (“Aflac”)"},
        {"event_id": "e4", "entity_name_raw": "Insulet Corp"},         # suffix variant
    ]
    got = {m.event_id: m.organization_id for m in resolve_events(events, idx)}
    assert got == {"e1": "org-davita", "e2": "org-davita",
                   "e3": "org-aflac", "e4": "org-insulet"}


def test_ambiguous_names_never_matched():
    idx = build_name_index(ORG_NAMES)
    assert "summit health" in idx.ambiguous
    assert "summit health" not in idx.by_norm
    events = [{"event_id": "e", "entity_name_raw": "Summit Health, Inc."}]
    assert resolve_events(events, idx) == []           # collision → left unresolved


def test_no_fuzzy_subsidiary_does_not_match_parent():
    idx = build_name_index(ORG_NAMES)
    # a subsidiary name is NOT the parent's normalized form → no match, no guess
    events = [
        {"event_id": "e1", "entity_name_raw": "Conduent Business Services LLC"},
        {"event_id": "e2", "entity_name_raw": "DaVita Dialysis of Texas"},   # extra tokens
        {"event_id": "e3", "entity_name_raw": "HealthEquity, Inc."},          # absent from corpus
    ]
    assert resolve_events(events, idx) == []


def test_unmatched_are_omitted_not_errored():
    idx = build_name_index(ORG_NAMES)
    events = [
        {"event_id": "hit", "entity_name_raw": "DaVita Inc."},
        {"event_id": "miss", "entity_name_raw": "Nacogdoches Memorial Hospital"},
    ]
    matches = resolve_events(events, idx)
    assert [m.event_id for m in matches] == ["hit"]    # miss simply omitted


def test_idempotent_resolution():
    idx = build_name_index(ORG_NAMES)
    events = [{"event_id": "e1", "entity_name_raw": "DaVita Inc."},
              {"event_id": "e2", "entity_name_raw": "Aflac Incorporated"}]
    first = resolve_events(events, idx)
    second = resolve_events(events, idx)               # same inputs → same result
    assert [(m.event_id, m.organization_id) for m in first] \
        == [(m.event_id, m.organization_id) for m in second]
    # and re-running over only the STILL-unresolved (none here) yields nothing
    resolved_ids = {m.event_id for m in first}
    remaining = [e for e in events if e["event_id"] not in resolved_ids]
    assert resolve_events(remaining, idx) == []


def test_null_org_id_pairs_ignored():
    idx = build_name_index([("Ghost Corp", None), ("DaVita Inc.", "org-davita")])
    assert idx.lookup("Ghost Corp") is None
    assert idx.lookup("DaVita Inc.") == "org-davita"


# ── Generic resolve_records (enforcement_record) ─────────────────────

def test_resolve_records_enforcement_fields():
    idx = build_name_index(ORG_NAMES)
    records = [
        {"enforcement_id": "e1", "entity_name": "DaVita Inc.", "target_company": None},
        {"enforcement_id": "e2", "entity_name": "Insulet Corp", "target_company": "x"},
        {"enforcement_id": "e3", "entity_name": None, "target_company": "Aflac Incorporated"},  # fallback
        {"enforcement_id": "e4", "entity_name": "Unknown Retailer", "target_company": None},   # no match
        {"enforcement_id": "e5", "entity_name": "Summit Health, Inc.", "target_company": None}, # ambiguous
    ]
    got = {m.record_id: m.organization_id for m in resolve_records(
        records, idx, id_field="enforcement_id", name_field="entity_name",
        fallback_name_field="target_company")}
    assert got == {"e1": "org-davita", "e2": "org-insulet", "e3": "org-aflac"}
    assert "e4" not in got and "e5" not in got     # no match + ambiguous both omitted


def test_resolve_records_idempotent():
    idx = build_name_index(ORG_NAMES)
    recs = [{"enforcement_id": "e1", "entity_name": "DaVita Inc."}]
    first = resolve_records(recs, idx, id_field="enforcement_id", name_field="entity_name")
    second = resolve_records(recs, idx, id_field="enforcement_id", name_field="entity_name")
    assert [(m.record_id, m.organization_id) for m in first] \
        == [(m.record_id, m.organization_id) for m in second]
    # re-running over only the still-unresolved (none) yields nothing
    resolved = {m.record_id for m in first}
    assert resolve_records([r for r in recs if r["enforcement_id"] not in resolved], idx,
                           id_field="enforcement_id", name_field="entity_name") == []


def test_resolve_events_still_backward_compatible():
    idx = build_name_index(ORG_NAMES)
    ms = resolve_events([{"event_id": "s1", "entity_name_raw": "DaVita Inc."}], idx)
    assert len(ms) == 1 and isinstance(ms[0], Match)
    assert ms[0].event_id == "s1" and ms[0].organization_id == "org-davita"
