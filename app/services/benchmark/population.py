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

import hashlib

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


def _population_version(
    member_org_ids,
    *,
    population_key: str = "",
    member_profile_versions=None,
    corpus_version=None,
) -> int:
    """Deterministic, content-derived benchmark population version (DATA-001).

    The version is a CANONICAL identity of the population's actual content, NOT a
    wall-clock timestamp. Two identical re-scores (same member set + same cohort
    config + same corpus/profile versions) MUST produce the same version; any
    change to the member set (or the config/versions) MUST produce a different
    one.

    Inputs folded into the identity (whatever is available in scope):
      - sorted(member_org_ids)           — the population membership itself
      - population_key                   — cohort config (industry + tier key)
      - member_profile_versions          — the formula/profile-version set of members
      - corpus_version                   — source corpus version

    Returns a STABLE POSITIVE 31-bit int. `report_snapshot.benchmark_population_version`
    is a Postgres `integer` (int32) column, and the same value is also written to
    `derived_data_item.benchmark_population_version` (text) via str(). We therefore
    derive a positive int that fits int32 (mask to 31 bits) rather than the raw
    hex digest, so nothing downstream breaks.
    """
    # Sorted, de-duplicated member ids — order-independent identity.
    ids = sorted({str(m) for m in (member_org_ids or []) if m})
    # Sorted set of member profile/formula versions (stringified for stability).
    pvs = sorted({str(v) for v in (member_profile_versions or []) if v is not None})

    canonical = "\x1f".join(
        [
            "members=" + ",".join(ids),
            "population_key=" + (population_key or ""),
            "profile_versions=" + ",".join(pvs),
            "corpus_version=" + ("" if corpus_version is None else str(corpus_version)),
        ]
    ).encode("utf-8")

    digest = hashlib.sha256(canonical).hexdigest()
    # Mask to 31 bits → always a positive value that fits a signed int32 column.
    return int(digest[:12], 16) & 0x7FFFFFFF


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

    # ── CQS gate (F03 parity, Rule 6) ──────────────────────────────
    # The F03 demo-cohort job includes only orgs with a fresh `open_web` notice
    # (CQS-eligible). The dynamic population must apply the SAME gate, or a live
    # org is benchmarked against CQS-excluded stale-corpus orgs (e.g. 2019
    # Princeton) that would never appear in a demo cohort — an inconsistency the
    # Stage-3 rehearsal surfaced (17 of 90 members were CQS-excluded). Filter the
    # candidate pool to CQS-eligible orgs before any similarity/expansion pass.
    cqs_r = await client.get(
        f"{SB}/rest/v1/privacy_notice?select=organization_id&notice_type=eq.open_web&limit=10000",
        headers=headers,
    )
    cqs_eligible = {
        n["organization_id"] for n in (cqs_r.json() if cqs_r.status_code == 200 else [])
        if n.get("organization_id")
    }
    # The target org is the subject, never a peer member — always keep its own
    # profile in the pool so it isn't counted as a CQS exclusion.
    if cqs_eligible and target_org_id:
        cqs_eligible.add(target_org_id)
    # Count only PEER profiles excluded (target never contributes to the count).
    profiles_before_cqs = sum(1 for p in profiles if p.get("organization_id") != target_org_id)
    if cqs_eligible:
        profiles = [p for p in profiles if p.get("organization_id") in cqs_eligible]
    profiles_after_cqs = sum(1 for p in profiles if p.get("organization_id") != target_org_id)

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

    # Disclose the CQS gate in the relaxations (surfaced on the cohort label):
    # how many profiled orgs were held out for being CQS-excluded (stale corpus).
    cqs_excluded = (profiles_before_cqs - profiles_after_cqs) if cqs_eligible else 0
    if cqs_excluded > 0:
        relaxations.append(f"cqs_gated_excluded_{cqs_excluded}")

    # Determine population version — CANONICAL, content-derived (DATA-001).
    # Identical populations produce identical versions; a changed member set
    # produces a different one. No wall-clock is involved.
    member_org_ids = [m["organization_id"] for m in normalized_members]
    member_profile_versions = [
        m.get("profile", {}).get("profile_version") for m in normalized_members
    ]
    pop_version = _population_version(
        member_org_ids,
        population_key=pop_key,
        member_profile_versions=member_profile_versions,
    )

    return {
        "population_key": pop_key,
        "members": normalized_members,
        "cohort_size": len(normalized_members),
        "relaxations": relaxations,
        "cqs_excluded": cqs_excluded,
        "benchmark_population_version": pop_version,
        "confidence_penalty": confidence_penalty,
        "band": band,
    }
