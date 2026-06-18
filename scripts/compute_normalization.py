"""Compute normalization weights for benchmark_membership.

For each org as "target", computes similarity to all 30 peers and writes
normalization_score + benchmark_weight into the EXISTING benchmark_membership
rows. Only updates 4 nullable columns — no other columns touched.

Usage:
    python scripts/compute_normalization.py
    python scripts/compute_normalization.py --dry-run
"""

import argparse
import logging

import httpx
from dotenv import dotenv_values

from app.services.normalization.engine import (
    PeerProfile,
    normalize_cohort,
)
from app.services.profiling.profile import score_to_tier

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("normalization")

CONFIG = dotenv_values(".env")
URL = CONFIG["SUPABASE_URL"]
KEY = CONFIG["SUPABASE_SERVICE_ROLE_KEY"]
H = {"apikey": KEY, "Authorization": f"Bearer {KEY}"}

INDUSTRY_MAP = {
    "fintech": "financial_services",
    "manufacturing": "industrial_manufacturing",
    "logistics": "supply_chain_services",
}


def load_peer_profiles() -> list[PeerProfile]:
    """Load all orgs + their profiles as PeerProfile objects."""
    r = httpx.get(
        f"{URL}/rest/v1/organization?select=organization_id,name,industry",
        headers=H, timeout=15,
    )
    orgs = {o["organization_id"]: o for o in r.json()}

    r2 = httpx.get(
        f"{URL}/rest/v1/organization_intelligence_profile"
        f"?select=organization_id,rss,pgms,osi,dsi,ehp,aigms,profile_version"
        f"&order=profile_version.desc",
        headers=H, timeout=15,
    )
    # Take latest profile per org
    seen = set()
    profiles = {}
    for p in r2.json():
        oid = p["organization_id"]
        if oid not in seen:
            profiles[oid] = p
            seen.add(oid)

    peers = []
    for oid, org in orgs.items():
        p = profiles.get(oid)
        if not p:
            continue
        peers.append(PeerProfile(
            organization_id=oid,
            industry=INDUSTRY_MAP.get(org["industry"], org["industry"]),
            rss_tier=score_to_tier(p["rss"]),
            pgms_tier=score_to_tier(p["pgms"]),
            osi_tier=score_to_tier(p["osi"]),
            dsi_tier=score_to_tier(p["dsi"]),
            ehp_tier=score_to_tier(p["ehp"]),
            aigms_tier=score_to_tier(p["aigms"]),
        ))

    return peers


def update_benchmark_membership(org_id: str, norm_score: float, bw: float,
                                 reason: str, pop_version: int) -> None:
    """UPDATE only the 4 normalization columns by composite key."""
    r = httpx.patch(
        f"{URL}/rest/v1/benchmark_membership?organization_id=eq.{org_id}",
        headers={**H, "Content-Type": "application/json", "Prefer": "return=minimal"},
        json={
            "normalization_score": norm_score,
            "benchmark_weight": bw,
            "inclusion_reason": reason,
            "population_version": pop_version,
        },
        timeout=15,
    )
    r.raise_for_status()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--population-version", type=int, default=1)
    args = parser.parse_args()

    peers = load_peer_profiles()
    log.info("Loaded %d peer profiles", len(peers))

    # For the MVP benchmark, we treat EACH org as a target against ALL 30 peers.
    # This gives each org its own similarity perspective.
    # We average the normalization scores across all target perspectives
    # to get a single weight per peer.

    # Simpler approach for MVP: use a "centroid" target (most common tier per dim)
    # Actually, per the spec, each peer gets weighted relative to a specific target
    # when that target's report is generated. For now, we compute one representative
    # weighting using the first org as target (all peers get a weight).
    # The benchmark_membership table stores per-peer weights.

    # Better: for each org, compute its similarity to all peers.
    # Since benchmark_membership has one row per org (not per org-pair),
    # we compute the AVERAGE similarity each org has to all others.

    from collections import defaultdict
    org_scores = defaultdict(list)

    for target in peers:
        results = normalize_cohort(target, peers, population_version=args.population_version)
        for r in results:
            if r.organization_id != target.organization_id:
                org_scores[r.organization_id].append(
                    (r.normalization_score, r.benchmark_weight, r.inclusion_reason)
                )

    log.info("Computed pairwise similarities for %d orgs", len(org_scores))

    for peer in peers:
        oid = peer.organization_id
        scores = org_scores.get(oid, [])
        if not scores:
            continue

        avg_norm = round(sum(s[0] for s in scores) / len(scores), 6)
        avg_bw = round(sum(s[1] for s in scores) / len(scores), 6)
        # Use the first inclusion_reason as representative (all same band)
        reason = scores[0][2]

        if args.dry_run:
            log.info(
                "[DRY-RUN] %s: norm=%.4f bw=%.4f reason=%s",
                oid[:12], avg_norm, avg_bw, reason,
            )
        else:
            update_benchmark_membership(oid, avg_norm, avg_bw, reason, args.population_version)
            log.info("UPDATED %s: norm=%.4f bw=%.4f", oid[:12], avg_norm, avg_bw)

    log.info("=== Done: %d benchmark_membership rows updated ===", len(org_scores))


if __name__ == "__main__":
    main()
