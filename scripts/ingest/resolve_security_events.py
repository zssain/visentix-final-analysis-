"""Resolve unresolved security_event rows to organizations (exact/normalized only).

Matches each `security_event.entity_name_raw` (resolution_status='unresolved')
against the corporate-name index built from organization_alias(legal_name) +
organization.name. On a single-org match it sets `organization_id` and flips
`resolution_status='resolved'`. No match → left unresolved (a review queue).

DETERMINISTIC normalization only, NO fuzzy matching (see entity_resolution.py).
Idempotent: only unresolved rows are read, and a re-run re-derives the same
matches; already-resolved rows are never touched.

    PYTHONPATH=. python scripts/ingest/resolve_security_events.py            # live
    PYTHONPATH=. python scripts/ingest/resolve_security_events.py --dry-run  # preview only
"""
from __future__ import annotations

import argparse
import logging
import sys

import httpx

from app.config import settings
from app.db import get_service_headers
from app.services.ingestion.entity_resolution import (
    build_name_index, normalize_name, resolve_events,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("ingestion.resolve")

_PAGE = 1000


def _rest(path: str) -> str:
    return f"{settings.supabase_url}/rest/v1/{path}"


def _get_all(path: str) -> list[dict]:
    """Fetch all rows for a select, paging past PostgREST's row cap."""
    rows, offset = [], 0
    while True:
        r = httpx.get(_rest(path), headers={**get_service_headers(),
                      "Range-Unit": "items", "Range": f"{offset}-{offset + _PAGE - 1}"}, timeout=60)
        if r.status_code >= 300:
            raise RuntimeError(f"fetch failed {path}: HTTP {r.status_code}")
        batch = r.json()
        rows.extend(batch)
        if len(batch) < _PAGE:
            return rows
        offset += _PAGE


def _mark_resolved(event_id: str, org_id: str) -> None:
    r = httpx.patch(_rest(f"security_event?event_id=eq.{event_id}"),
                    headers={**get_service_headers(), "Content-Type": "application/json",
                             "Prefer": "return=minimal"},
                    json={"organization_id": org_id, "resolution_status": "resolved"}, timeout=30)
    if r.status_code >= 300:
        raise RuntimeError(f"patch failed for {event_id}: HTTP {r.status_code}")


def run(dry_run: bool = False) -> int:
    # 1. corporate-name index: legal_name aliases + organization.name
    aliases = _get_all("organization_alias?select=value,organization_id&alias_type=eq.legal_name")
    orgs = _get_all("organization?select=organization_id,name")
    org_name = {o["organization_id"]: o["name"] for o in orgs}
    index = build_name_index(
        [(a["value"], a["organization_id"]) for a in aliases]
        + [(o["name"], o["organization_id"]) for o in orgs])
    log.info("name index: %d unique names, %d ambiguous (never matched)",
             len(index.by_norm), len(index.ambiguous))

    # 2. unresolved events
    events = _get_all(
        "security_event?select=event_id,entity_name_raw,individuals_affected"
        "&resolution_status=eq.unresolved")
    matches = resolve_events(events, index)

    # 3. write (idempotent) unless dry-run
    if not dry_run:
        for mt in matches:
            _mark_resolved(mt.event_id, mt.organization_id)

    _report(events, matches, org_name, dry_run)
    return 0


def _report(events, matches, org_name, dry_run):
    matched_ids = {m.event_id for m in matches}
    print("\n" + "=" * 72)
    print(f"security_event entity resolution {'(DRY RUN — no writes)' if dry_run else ''}")
    print(f"  unresolved read:   {len(events)}")
    print(f"  RESOLVED this run: {len(matches)}")
    print(f"  still unresolved:  {len(events) - len(matches)}")
    print("-" * 72)
    print("Sample matches (entity_name_raw → organization):")
    for m in matches[:25]:
        print(f"  {m.entity_name_raw[:40]:<42} → {org_name.get(m.organization_id, '?')[:28]:<30}"
              f"  [{m.matched_norm}]")
    if not matches:
        print("  (none)")
    print("-" * 72)
    print("Top-20 STILL-UNRESOLVED by individuals_affected (review queue):")
    rem = sorted((e for e in events if e["event_id"] not in matched_ids),
                 key=lambda e: e.get("individuals_affected") or 0, reverse=True)[:20]
    for e in rem:
        ia = e.get("individuals_affected")
        print(f"  {(ia if ia is not None else 0):>12,}  {(e['entity_name_raw'] or '')[:52]}")
    print("=" * 72 + "\n")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Resolve security_event → organization (exact/normalized).")
    ap.add_argument("--dry-run", action="store_true", help="preview matches; write nothing")
    args = ap.parse_args(argv)
    try:
        return run(dry_run=args.dry_run)
    except Exception as e:  # noqa: BLE001
        log.error("resolution failed: %s: %s", type(e).__name__, e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
