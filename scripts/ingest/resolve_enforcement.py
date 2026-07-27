"""Resolve unresolved enforcement_record rows to organizations (exact/normalized only).

Matches each enforcement action's `entity_name` (falling back to `target_company`)
against the corporate-name index built from organization_alias(legal_name) +
organization.name — the SAME deterministic, ambiguity-safe rules as the security_event
resolver (no fuzzy matching). On a single-org match it sets `organization_id` and
`resolution_status='resolved'`; no match / ambiguous → left unresolved (review queue).

Idempotent: only `resolution_status='unresolved'` rows are read, and a re-run re-derives
the same matches; resolved rows are never touched.

    PYTHONPATH=. python scripts/ingest/resolve_enforcement.py            # live
    PYTHONPATH=. python scripts/ingest/resolve_enforcement.py --dry-run  # preview only
"""
from __future__ import annotations

import argparse
import logging
import sys

import httpx

from app.config import settings
from app.db import get_service_headers
from app.services.ingestion.entity_resolution import build_name_index, resolve_records

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("ingestion.resolve_enforcement")

_PAGE = 1000


def _rest(path: str) -> str:
    return f"{settings.supabase_url}/rest/v1/{path}"


def _get_all(path: str) -> list[dict]:
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


def _mark_resolved(enforcement_id: str, org_id: str) -> None:
    r = httpx.patch(_rest(f"enforcement_record?enforcement_id=eq.{enforcement_id}"),
                    headers={**get_service_headers(), "Content-Type": "application/json",
                             "Prefer": "return=minimal"},
                    json={"organization_id": org_id, "resolution_status": "resolved"}, timeout=30)
    if r.status_code >= 300:
        raise RuntimeError(f"patch failed for {enforcement_id}: HTTP {r.status_code}")


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

    # 2. unresolved enforcement records
    records = _get_all(
        "enforcement_record?select=enforcement_id,entity_name,target_company,fine_amount_usd,"
        "penalty_usd,regulator_id&resolution_status=eq.unresolved")
    matches = resolve_records(records, index, id_field="enforcement_id",
                              name_field="entity_name", fallback_name_field="target_company")

    # 3. write (idempotent) unless dry-run
    if not dry_run:
        for m in matches:
            _mark_resolved(m.record_id, m.organization_id)

    _report(records, matches, org_name, dry_run)
    return 0


def _amount(r: dict) -> float:
    return float(r.get("fine_amount_usd") or r.get("penalty_usd") or 0)


def _report(records, matches, org_name, dry_run):
    matched_ids = {m.record_id for m in matches}
    print("\n" + "=" * 74)
    print(f"enforcement_record entity resolution {'(DRY RUN — no writes)' if dry_run else ''}")
    print(f"  unresolved read:   {len(records)}")
    print(f"  RESOLVED this run: {len(matches)}")
    print(f"  still unresolved:  {len(records) - len(matches)}")
    print("-" * 74)
    print("Sample matches (entity_name → organization):")
    for m in matches[:25]:
        print(f"  {(m.name or '')[:40]:<42} → {org_name.get(m.organization_id, '?')[:28]:<30}"
              f"  [{m.matched_norm}]")
    if not matches:
        print("  (none)")
    print("-" * 74)
    print("Top-20 STILL-UNRESOLVED by fine_amount_usd (review queue):")
    rem = sorted((r for r in records if r["enforcement_id"] not in matched_ids),
                 key=_amount, reverse=True)[:20]
    for r in rem:
        amt = _amount(r)
        name = r.get("entity_name") or r.get("target_company") or ""
        print(f"  ${amt:>16,.0f}  [{r.get('regulator_id') or '-':<7}] {name[:46]}")
    print("=" * 74 + "\n")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Resolve enforcement_record → organization (exact/normalized).")
    ap.add_argument("--dry-run", action="store_true", help="preview matches; write nothing")
    args = ap.parse_args(argv)
    try:
        return run(dry_run=args.dry_run)
    except Exception as e:  # noqa: BLE001
        log.error("resolution failed: %s: %s", type(e).__name__, e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
