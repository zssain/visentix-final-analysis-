"""Dynamic benchmark population builder (VICBNF-003/004).

Constructs a peer population for a target org using the spec's population key:
  Industry + RSS_tier + PGMS_tier + OSI_tier + DSI_tier + AIGMS_tier + EHP_tier.

Applies size rules with recorded relaxation:
  >=100 → full dimensional cohort
  50-99 → minor weighting relaxation
  20-49 → adjacent-tier expansion (relax one dimension, record which)
  <20   → broader industry cohort + reduced confidence
"""

from __future__ import annotations

import httpx

from app.config import settings
from app.db import get_service_headers
from app.services.normalization.engine import (
    PeerProfile,
    compute_peer_similarity,
    compute_benchmark_weight,
    determine_relaxation_band,
)

SB = settings.supabase_url


def _population_key(profile: dict) -> str:
    """Build the population key string from a profile dict."""
    parts = [
        profile.get("industry_id") or profile.get("industry", "unknown"),
        profile.get("rss_tier", ""),
        profile.get("pgms_tier", ""),
        profile.get("osi_tier", ""),
        profile.get("dsi_tier", ""),
        profile.get("aigms_tier", ""),
        profile.get("ehp_tier", ""),
    ]
    return "|".join(parts)


async def build_population(
    client: httpx.AsyncClient,
    target_profile: dict,
) -> dict:
    """Build a dynamic benchmark population for the target org.

    Returns {population_key, members, cohort_size, relaxations,
             benchmark_population_version, confidence_penalty,
             normalized_members}.
    """
    headers = get_service_headers()
    target_org_id = target_profile.get("organization_id", "")
    pop_key = _population_key(target_profile)

    # Load all org profiles (latest version per org)
    r = await client.get(
        f"{SB}/rest/v1/organization_intelligence_profile"
        f"?select=organization_id,industry_id,rss,pgms,osi,dsi,ehp,aigms,"
        f"rss_tier,pgms_tier,osi_tier,dsi_tier,ehp_tier,aigms_tier,"
        f"profile_version,confidence_score"
        f"&order=profile_version.desc&limit=500",
        headers=headers,
    )
    all_profiles = r.json() if r.status_code == 200 else []

    # Dedupe: latest version per org
    seen: set[str] = set()
    profiles: list[dict] = []
    for p in all_profiles:
        oid = p.get("organization_id", "")
        if oid and oid not in seen:
            seen.add(oid)
            profiles.append(p)

    # Load org industry info for matching
    r2 = await client.get(
        f"{SB}/rest/v1/organization?select=organization_id,industry,name&limit=500",
        headers=headers,
    )
    orgs = {o["organization_id"]: o for o in (r2.json() if r2.status_code == 200 else [])}

    # Build target PeerProfile
    target_industry = orgs.get(target_org_id, {}).get("industry", target_profile.get("industry", "unknown"))
    target_peer = PeerProfile(
        organization_id=target_org_id,
        industry=target_industry,
        rss_tier=target_profile.get("rss_tier", "Moderate"),
        pgms_tier=target_profile.get("pgms_tier", "Developing"),
        osi_tier=target_profile.get("osi_tier", "Developing"),
        dsi_tier=target_profile.get("dsi_tier", "Low"),
        ehp_tier=target_profile.get("ehp_tier", "Clean"),
        aigms_tier=target_profile.get("aigms_tier", "Minimal"),
    )

    # Find matching members — start with full dimensional match
    members = []
    relaxations: list[str] = []

    for p in profiles:
        oid = p.get("organization_id", "")
        if oid == target_org_id:
            continue
        org_info = orgs.get(oid, {})
        peer = PeerProfile(
            organization_id=oid,
            industry=org_info.get("industry", "unknown"),
            rss_tier=p.get("rss_tier", ""),
            pgms_tier=p.get("pgms_tier", ""),
            osi_tier=p.get("osi_tier", ""),
            dsi_tier=p.get("dsi_tier", ""),
            ehp_tier=p.get("ehp_tier", ""),
            aigms_tier=p.get("aigms_tier", ""),
        )
        sim = compute_peer_similarity(target_peer, peer)
        if sim >= 0.5:  # inclusion threshold
            members.append({
                "organization_id": oid,
                "name": org_info.get("name", ""),
                "industry": org_info.get("industry", ""),
                "pgms": p.get("pgms", 0),
                "rss": p.get("rss", 0),
                "similarity": sim,
                "profile": p,
            })

    # Apply size rules
    cohort_size = len(members)
    band, _ = determine_relaxation_band(cohort_size)
    confidence_penalty = 0.0

    if cohort_size < 20:
        # Broader industry cohort — include all orgs with same industry
        relaxations.append("broader_industry_cohort")
        confidence_penalty = 0.15
        for p in profiles:
            oid = p.get("organization_id", "")
            if oid == target_org_id or any(m["organization_id"] == oid for m in members):
                continue
            org_info = orgs.get(oid, {})
            if org_info.get("industry", "").lower() == target_industry.lower():
                peer = PeerProfile(
                    organization_id=oid,
                    industry=org_info.get("industry", "unknown"),
                    rss_tier=p.get("rss_tier", ""),
                    pgms_tier=p.get("pgms_tier", ""),
                    osi_tier=p.get("osi_tier", ""),
                    dsi_tier=p.get("dsi_tier", ""),
                    ehp_tier=p.get("ehp_tier", ""),
                    aigms_tier=p.get("aigms_tier", ""),
                )
                sim = compute_peer_similarity(target_peer, peer)
                members.append({
                    "organization_id": oid,
                    "name": org_info.get("name", ""),
                    "industry": org_info.get("industry", ""),
                    "pgms": p.get("pgms", 0),
                    "similarity": sim,
                    "profile": p,
                })
        cohort_size = len(members)

    if 20 <= cohort_size < 50:
        relaxations.append(f"adjacent_tier_expansion_n{cohort_size}")
        confidence_penalty = 0.08
    elif 50 <= cohort_size < 100:
        relaxations.append(f"minor_relaxation_n{cohort_size}")
        confidence_penalty = 0.03

    # If still < 20 after industry expansion, include ALL profiled orgs
    if cohort_size < 20:
        relaxations.append("all_orgs_fallback")
        confidence_penalty = 0.20
        existing_ids = {m["organization_id"] for m in members}
        for p in profiles:
            oid = p.get("organization_id", "")
            if oid == target_org_id or oid in existing_ids:
                continue
            org_info = orgs.get(oid, {})
            peer = PeerProfile(
                organization_id=oid,
                industry=org_info.get("industry", "unknown"),
                rss_tier=p.get("rss_tier", ""),
                pgms_tier=p.get("pgms_tier", ""),
                osi_tier=p.get("osi_tier", ""),
                dsi_tier=p.get("dsi_tier", ""),
                ehp_tier=p.get("ehp_tier", ""),
                aigms_tier=p.get("aigms_tier", ""),
            )
            sim = compute_peer_similarity(target_peer, peer)
            members.append({
                "organization_id": oid,
                "name": org_info.get("name", ""),
                "industry": org_info.get("industry", ""),
                "pgms": p.get("pgms", 0),
                "similarity": sim,
                "profile": p,
            })
        cohort_size = len(members)

    # Normalize: compute benchmark_weight per member
    band, _ = determine_relaxation_band(cohort_size)
    normalized_members = []
    for m in members:
        bw = compute_benchmark_weight(m["similarity"], band)
        normalized_members.append({
            **m,
            "normalization_score": m["similarity"],
            "benchmark_weight": bw,
        })

    # Determine population version (timestamp-based)
    import time
    pop_version = int(time.time())

    return {
        "population_key": pop_key,
        "members": normalized_members,
        "cohort_size": len(normalized_members),
        "relaxations": relaxations,
        "benchmark_population_version": pop_version,
        "confidence_penalty": confidence_penalty,
        "band": band,
    }
