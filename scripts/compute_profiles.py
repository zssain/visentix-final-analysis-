"""Compute Organization Intelligence Profiles for all 30 orgs.

Reads existing classified data from Supabase, computes 7 dimensions
deterministically, and inserts NEW versioned rows into
organization_intelligence_profile. Never overwrites existing profiles.

Usage:
    python scripts/compute_profiles.py
    python scripts/compute_profiles.py --dry-run
"""

import argparse
import json
import logging
from collections import Counter, defaultdict

import httpx
from dotenv import dotenv_values

from app.services.profiling.profile import (
    OrgData,
    compute_profile,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("compute_profiles")

CONFIG = dotenv_values(".env")
URL = CONFIG["SUPABASE_URL"]
KEY = CONFIG["SUPABASE_SERVICE_ROLE_KEY"]
H = {"apikey": KEY, "Authorization": f"Bearer {KEY}"}


def fetch_all(table: str, select: str, limit: int = 1000) -> list[dict]:
    """Paginated fetch of all rows."""
    rows = []
    offset = 0
    while True:
        r = httpx.get(
            f"{URL}/rest/v1/{table}?select={select}&offset={offset}&limit={limit}",
            headers=H, timeout=30,
        )
        r.raise_for_status()
        batch = r.json()
        rows.extend(batch)
        if len(batch) < limit:
            break
        offset += limit
    return rows


def load_org_data() -> list[OrgData]:
    """Load all data needed for profiling from Supabase."""
    log.info("Loading organizations...")
    orgs = fetch_all("organization", "organization_id,name,industry,size,geography,public_private")

    log.info("Loading notices...")
    notices = fetch_all("privacy_notice", "notice_id,organization_id")
    notice_org = {n["notice_id"]: n["organization_id"] for n in notices}
    orgs_with_notice = set(notice_org.values())

    log.info("Loading sections...")
    sections = fetch_all("notice_section", "section_id,notice_id")
    section_org = {s["section_id"]: notice_org.get(s["notice_id"]) for s in sections}

    log.info("Loading clauses...")
    clauses = fetch_all("disclosure_clause", "clause_id,section_id,category")

    # Build org → clause categories
    org_cats: dict[str, Counter] = defaultdict(Counter)
    org_clause_count: dict[str, int] = defaultdict(int)
    for c in clauses:
        org_id = section_org.get(c["section_id"])
        if org_id:
            org_cats[org_id][c["category"]] += 1
            org_clause_count[org_id] += 1

    log.info("Loading enforcement records...")
    enforcements = fetch_all(
        "enforcement_record",
        "enforcement_id,regulator_id,jurisdiction,penalty_usd"
    )

    # Enforcement is regulator-level, not org-specific. Distribute by jurisdiction.
    # All orgs are US-based, so US enforcement records apply broadly.
    total_enf = len(enforcements)
    total_penalty = sum(e.get("penalty_usd") or 0 for e in enforcements)
    all_regulators = [e["regulator_id"] for e in enforcements]

    log.info("Loading regulator weights...")
    regulators = fetch_all("regulator", "regulator_id,enforcement_frequency_weight")
    reg_weights = {r["regulator_id"]: r["enforcement_frequency_weight"] for r in regulators}

    result = []
    for org in orgs:
        oid = org["organization_id"]
        data = OrgData(
            organization_id=oid,
            name=org["name"],
            industry=org["industry"],
            size=org["size"] or "large",
            geography=org["geography"] or "US",
            public_private=org["public_private"],
            clause_categories=org_cats.get(oid, Counter()),
            total_clauses=org_clause_count.get(oid, 0),
            has_notice=oid in orgs_with_notice,
            # Enforcement is jurisdiction-level proxy (all orgs share the US landscape)
            enforcement_count=total_enf,
            total_penalty_usd=total_penalty,
            enforcement_regulators=all_regulators,
            regulator_weights=reg_weights,
        )
        result.append(data)

    return result


def get_next_version(org_id: str) -> int:
    """Get the next profile_version for an org (max existing + 1, or 1)."""
    r = httpx.get(
        f"{URL}/rest/v1/organization_intelligence_profile"
        f"?select=profile_version&organization_id=eq.{org_id}"
        f"&order=profile_version.desc&limit=1",
        headers=H, timeout=10,
    )
    rows = r.json()
    if rows:
        return rows[0]["profile_version"] + 1
    return 1


def insert_profile(profile, version: int) -> None:
    """Insert a new profile row (never overwrite)."""
    payload = {
        "organization_id": profile.organization_id,
        "ic": hash(profile.ic) % 100,  # Numeric proxy for IC category
        "rss": profile.rss,
        "pgms": profile.pgms,
        "osi": profile.osi,
        "dsi": profile.dsi,
        "ehp": profile.ehp,
        "aigms": profile.aigms,
        "profile_version": version,
        "confidence_score": profile.confidence_score,
    }
    r = httpx.post(
        f"{URL}/rest/v1/organization_intelligence_profile",
        headers={**H, "Content-Type": "application/json", "Prefer": "return=minimal"},
        json=payload,
        timeout=15,
    )
    r.raise_for_status()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    org_data_list = load_org_data()
    log.info("Loaded data for %d organizations", len(org_data_list))

    for data in org_data_list:
        profile = compute_profile(data)
        version = get_next_version(data.organization_id)

        if args.dry_run:
            log.info(
                "[DRY-RUN] %s: IC=%s RSS=%.1f(%s) PGMS=%.1f(%s) OSI=%.1f(%s) "
                "DSI=%.1f(%s) EHP=%.1f(%s) AIGMS=%.1f(%s) VCI=%.4f v=%d",
                data.name, profile.ic,
                profile.rss, profile.tiers["rss"],
                profile.pgms, profile.tiers["pgms"],
                profile.osi, profile.tiers["osi"],
                profile.dsi, profile.tiers["dsi"],
                profile.ehp, profile.tiers["ehp"],
                profile.aigms, profile.tiers["aigms"],
                profile.confidence_score, version,
            )
        else:
            insert_profile(profile, version)
            log.info(
                "INSERTED %s v%d: RSS=%.1f PGMS=%.1f OSI=%.1f DSI=%.1f EHP=%.1f AIGMS=%.1f VCI=%.4f",
                data.name, version,
                profile.rss, profile.pgms, profile.osi,
                profile.dsi, profile.ehp, profile.aigms,
                profile.confidence_score,
            )

    log.info("=== Done: %d profiles computed ===", len(org_data_list))


if __name__ == "__main__":
    main()
