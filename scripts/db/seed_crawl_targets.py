"""Seed the crawl_target work-list for the open_web crawler (F02).

Targets are built from organizations that HAVE a crawlable domain:
  (a) EDGAR mapped-industry orgs (source_metadata.sic_industry_draft in the mapped set)
      that also carry a domain, and
  (b) orgs flagged origin='princeton_leuven' (domains from the Princeton sector CSVs
      that resolved to orgs).
Each becomes a crawl_target row (status='pending') keyed by normalized domain.

    PYTHONPATH=. python scripts/db/seed_crawl_targets.py --sector retail --limit 25
    PYTHONPATH=. python scripts/db/seed_crawl_targets.py --dry-run

NOTE: EDGAR orgs generally have NO domain (SEC website field is blank), so few/no
EDGAR-derived targets exist until domains are enriched — the seed reports what it found.
"""
from __future__ import annotations

import argparse
import hashlib
import sys

import httpx

from app.config import settings
from app.db import get_service_headers
from app.services.ingestion.connectors.edgar import normalize_domain

MAPPED_INDUSTRIES = {"IND-01", "IND-02", "IND-03", "IND-04", "IND-05", "IND-06"}
# sector label ← industry_id / free-text industry (best-effort, honest)
_IND_LABEL = {"IND-01": "retail", "IND-02": "software", "IND-03": "healthcare",
              "IND-04": "financial", "IND-05": "education", "IND-06": "entertainment"}


def _rest(p):
    return f"{settings.supabase_url}/rest/v1/{p}"


def _get_all(path):
    rows, off = [], 0
    while True:
        r = httpx.get(_rest(path), headers={**get_service_headers(), "Range": f"{off}-{off+999}"}, timeout=60)
        b = r.json() if r.status_code < 300 else []
        rows.extend(b)
        if len(b) < 1000:
            return rows
        off += 1000


def build_targets(sector: str | None):
    """Return crawl_target rows for orgs that have a domain, from EDGAR + Princeton."""
    orgs = _get_all("organization?select=organization_id,domain,industry,origin,size_metadata"
                    "&domain=not.is.null")
    out, seen = [], set()
    for o in orgs:
        domain = normalize_domain(o.get("domain"))
        if not domain or domain in seen:
            continue
        origin = o.get("origin")
        draft = (o.get("size_metadata") or {}).get("sic_industry_draft")
        # source (a) EDGAR mapped-industry, or (b) Princeton-resolved
        added_by = None
        sec = None
        if origin == "princeton_leuven":
            added_by, sec = "seed:princeton", o.get("industry")
        elif draft in MAPPED_INDUSTRIES:
            added_by, sec = "seed:edgar", _IND_LABEL.get(draft)
        else:
            # peers with domains but no EDGAR/Princeton provenance: include as general web
            added_by, sec = "seed:peer", o.get("industry")
        if sector and (sec or "").lower() != sector.lower():
            continue
        seen.add(domain)
        out.append({
            "target_id": f"ct:{domain}",
            "organization_id": o["organization_id"], "domain": domain, "sector": sec,
            "priority": 50 if origin == "princeton_leuven" else 100,
            "status": "pending", "added_by": added_by,
        })
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Seed crawl_target from EDGAR + Princeton orgs.")
    ap.add_argument("--sector", default=None, help="filter to one sector (e.g. retail)")
    ap.add_argument("--limit", type=int, default=None, help="cap targets seeded")
    ap.add_argument("--dry-run", action="store_true", help="print what would be seeded; no write")
    args = ap.parse_args(argv)

    rows = build_targets(args.sector)
    if args.limit:
        rows = rows[:args.limit]
    by_src: dict[str, int] = {}
    for r in rows:
        by_src[r["added_by"]] = by_src.get(r["added_by"], 0) + 1
    print(f"crawl targets built: {len(rows)}  by source: {by_src}  "
          f"(sector={args.sector or 'all'})")
    for r in rows[:10]:
        print(f"  {r['domain']:<28} sector={r['sector'] or '-':<12} src={r['added_by']}")
    if args.dry_run or not rows:
        return 0
    r = httpx.post(_rest("crawl_target?on_conflict=domain"),
                   headers={**get_service_headers(), "Content-Type": "application/json",
                            "Prefer": "resolution=ignore-duplicates,return=minimal"},
                   json=rows, timeout=60)
    print("seeded" if r.status_code < 300 else f"seed failed: HTTP {r.status_code} {r.text[:200]}")
    return 0 if r.status_code < 300 else 1


if __name__ == "__main__":
    sys.exit(main())
