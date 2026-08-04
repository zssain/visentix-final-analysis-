"""F20 — Partner Portal service.

Tenancy (partner → workspace → one client org), API keys (hash only, plaintext
once), render-only branding frozen at approval, and the hardened white-label
feed aggregation (per-cohort, identity-free, same population exclusions as the
benchmark/quarterly population, n<10 suppressed per OD-05 + DIR-006).

No forked review, no forked scorer — partner assessments run the normal
pipeline; this module only adds tenancy, branding provenance, and feed shaping.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import statistics
from uuid import uuid4

import httpx

from app.config import settings
from app.db import (
    get_service_headers,
    supabase_rest_get,
    supabase_rest_patch,
    supabase_rest_post,
)
from app.logging import get_logger
from app.services.products.mapping import objects_for_product

log = get_logger(__name__)

SB = settings.supabase_url

# OD-05 (LOW_CONFIDENCE_COHORT_N) + DIR-006 — no aggregate below the minimum cohort.
MIN_COHORT_N = 10
FEED_SCHEMA_VERSION = "vicbnf-3.0.0"  # per-cohort reshape (was 2.0.0 per-org)
KEY_PREFIX = "vsx_"


# ── API keys ─────────────────────────────────────────────────
#
# SEC-009 — storage scheme.
#   Preferred: HMAC-SHA256(key=partner_key_pepper, msg=plaintext). The pepper is
#   a server-side secret (settings.partner_key_pepper); an attacker who reads the
#   DB cannot reconstruct/brute-force keys without it (unlike a bare sha256).
#   Legacy: unsalted sha256(plaintext) — how keys were stored before SEC-009.
#
# New keys are ALWAYS stored with the preferred scheme when the pepper is set.
# Verify accepts EITHER digest so already-issued (legacy) keys keep working.
# Rotating existing keys onto HMAC is an EXTERNAL step: re-issue the key
# (create_api_key + revoke the old one). We deliberately never re-hash on verify
# because we only have the plaintext momentarily and must not persist it.


def _legacy_hash_key(plaintext: str) -> str:
    """Legacy unsalted sha256 (pre-SEC-009). Kept for migration-safe verify."""
    return hashlib.sha256(plaintext.encode()).hexdigest()


def _hmac_hash_key(plaintext: str) -> str:
    """HMAC-SHA256 with the server-side pepper (SEC-009 preferred scheme)."""
    return hmac.new(settings.partner_key_pepper.encode(),
                    plaintext.encode(), hashlib.sha256).hexdigest()


def _hash_key(plaintext: str) -> str:
    """Digest used to STORE a new key. HMAC when a pepper is configured, else
    the legacy sha256 (dev/local) — with a warning so it's never silent."""
    if settings.partner_key_pepper:
        return _hmac_hash_key(plaintext)
    log.warning("PARTNER_KEY_PEPPER unset — storing partner API key with legacy "
                "unsalted sha256. Set PARTNER_KEY_PEPPER for HMAC hashing.")
    return _legacy_hash_key(plaintext)


async def create_api_key(partner_id: str, label: str) -> dict:
    """Generate a key, store ONLY its hash, return the plaintext ONCE."""
    plaintext = KEY_PREFIX + secrets.token_urlsafe(32)
    key_id = str(uuid4())
    await supabase_rest_post("partner_api_key", {
        "id": key_id,
        "partner_id": partner_id,
        "key_hash": _hash_key(plaintext),
        "key_last4": plaintext[-4:],
        "label": label or "",
    })
    # The plaintext is returned here and NEVER persisted or retrievable again.
    return {"api_key_id": key_id, "api_key": plaintext, "label": label or ""}


async def list_api_keys(partner_id: str) -> list[dict]:
    """List keys MASKED (never the hash, never the plaintext)."""
    r = await supabase_rest_get(
        "partner_api_key",
        select="id,label,key_last4,created_at,last_used_at,revoked_at",
        filters=f"partner_id=eq.{partner_id}&order=created_at.desc",
        limit=200,
    )
    rows = r.json() if r.status_code == 200 else []
    return [{
        "api_key_id": k["id"], "label": k.get("label") or "",
        "masked": f"{KEY_PREFIX}…{k.get('key_last4') or ''}",
        "created_at": k.get("created_at"), "last_used_at": k.get("last_used_at"),
        "revoked": k.get("revoked_at") is not None,
    } for k in rows]


async def revoke_api_key(partner_id: str, key_id: str) -> bool:
    """Revoke a key (immediate). Scoped to the caller's partner_id."""
    r = await supabase_rest_get(
        "partner_api_key", select="id",
        filters=f"id=eq.{key_id}&partner_id=eq.{partner_id}", limit=1,
    )
    if not (r.status_code == 200 and r.json()):
        return False
    await supabase_rest_patch("partner_api_key", f"id=eq.{key_id}", {"revoked_at": "now()"})
    return True


async def verify_api_key(plaintext: str) -> dict | None:
    """Return {partner_id, api_key_id} for a valid, non-revoked key, else None.

    Stamps last_used_at. Hash-compare only — plaintext is never stored.

    MIGRATION-SAFE (SEC-009): accept EITHER the new HMAC digest OR the legacy
    unsalted sha256, so keys issued before the pepper was configured keep
    working until they are re-issued. When no pepper is set the two candidates
    collapse to the single legacy digest.
    """
    if not plaintext:
        return None
    candidates = {_legacy_hash_key(plaintext)}
    if settings.partner_key_pepper:
        candidates.add(_hmac_hash_key(plaintext))
    in_list = ",".join(sorted(candidates))
    r = await supabase_rest_get(
        "partner_api_key", select="id,partner_id,revoked_at",
        filters=f"key_hash=in.({in_list})&revoked_at=is.null", limit=1,
    )
    rows = r.json() if r.status_code == 200 else []
    if not rows:
        return None
    key = rows[0]
    await supabase_rest_patch("partner_api_key", f"id=eq.{key['id']}", {"last_used_at": "now()"})
    return {"partner_id": key["partner_id"], "api_key_id": key["id"]}


async def log_feed_access(partner_id: str | None, api_key_id: str | None,
                          endpoint: str, row_count: int) -> None:
    await supabase_rest_post("feed_access_log", {
        "id": str(uuid4()), "partner_id": partner_id, "api_key_id": api_key_id,
        "endpoint": endpoint, "row_count": row_count,
    })


# ── Workspaces (partner → one client org) ────────────────────

async def create_workspace(partner_id: str, name: str, client_org: dict) -> dict:
    """Create a workspace + its one client org (normal profiling path)."""
    from app.routers.assessments import _find_or_create_org
    org_id = await _find_or_create_org(client_org.get("name") or name)
    industry = client_org.get("industry")
    if industry:
        await supabase_rest_patch("organization", f"organization_id=eq.{org_id}",
                                  {"industry": industry})
    ws_id = str(uuid4())
    await supabase_rest_post("partner_workspace", {
        "id": ws_id, "partner_id": partner_id, "client_org_id": org_id, "name": name,
    })
    return {"workspace_id": ws_id, "client_org_id": org_id}


async def resolve_workspace(workspace_id: str, partner_id: str | None, is_admin: bool) -> dict | None:
    """Return the workspace row iff the caller owns it (or is our admin). Else None.

    This is the partner analogue of F10 org isolation: a partner_admin can only
    ever reach a workspace whose partner_id matches their claim.
    """
    r = await supabase_rest_get(
        "partner_workspace", select="id,partner_id,client_org_id,name,created_at",
        filters=f"id=eq.{workspace_id}", limit=1,
    )
    rows = r.json() if r.status_code == 200 else []
    if not rows:
        return None
    ws = rows[0]
    if is_admin or ws["partner_id"] == partner_id:
        return ws
    return None  # cross-partner → invisible (no existence leak)


async def list_workspaces(partner_id: str | None, is_admin: bool) -> list[dict]:
    """List workspaces for the caller's partner (admin sees all), each with the
    latest assessment status for its client org."""
    filt = "order=created_at.desc"
    if not is_admin:
        filt = f"partner_id=eq.{partner_id}&{filt}"
    r = await supabase_rest_get(
        "partner_workspace", select="id,partner_id,client_org_id,name,created_at",
        filters=filt, limit=500,
    )
    workspaces = r.json() if r.status_code == 200 else []
    out = []
    for ws in workspaces:
        status = await _latest_assessment_status(ws["client_org_id"])
        out.append({**ws, "latest_status": status})
    return out


async def _latest_assessment_status(org_id: str) -> dict | None:
    """Latest notice for an org + its review status (draft/in_review/approved)."""
    r = await supabase_rest_get(
        "privacy_notice", select="notice_id,retrieval_date",
        filters=f"organization_id=eq.{org_id}&order=retrieval_date.desc", limit=1,
    )
    rows = r.json() if r.status_code == 200 else []
    if not rows:
        return None
    nid = rows[0]["notice_id"]
    rv = await supabase_rest_get(
        "assessment_review", select="status", filters=f"assessment_id=eq.{nid}", limit=1,
    )
    review = rv.json() if rv.status_code == 200 else []
    # Latest snapshot id (for the branded-PDF link).
    sn = await supabase_rest_get(
        "report_snapshot", select="snapshot_id",
        filters=f"notice_id=eq.{nid}&order=created_at.desc", limit=1,
    )
    snaps = sn.json() if sn.status_code == 200 else []
    return {
        "assessment_id": nid,
        "snapshot_id": (snaps[0]["snapshot_id"] if snaps else None),
        "review_status": (review[0]["status"] if review else "draft"),
        "last_activity": rows[0].get("retrieval_date"),
    }


# ── Branding (render-only; frozen at approval) ───────────────

async def get_partner_for_org(org_id: str) -> dict | None:
    """Resolve the owning partner (via workspace) for a client org, else None."""
    r = await supabase_rest_get(
        "partner_workspace", select="partner_id", filters=f"client_org_id=eq.{org_id}", limit=1,
    )
    rows = r.json() if r.status_code == 200 else []
    if not rows:
        return None
    pr = await supabase_rest_get(
        "partner", select="id,name,logo_url,logo_hash,brand_color,status",
        filters=f"id=eq.{rows[0]['partner_id']}", limit=1,
    )
    prows = pr.json() if pr.status_code == 200 else []
    return prows[0] if prows else None


def record_branding_on_approval(assessment_id: str, snapshot_id: str | None) -> None:
    """Freeze branding onto the snapshot AT APPROVAL (sync — called from the
    review approve path). No-op for non-partner assessments. Never raises into
    the approval flow."""
    if not snapshot_id:
        return
    try:
        headers = get_service_headers()
        with httpx.Client(timeout=15) as client:
            # org for this assessment
            r = client.get(f"{SB}/rest/v1/privacy_notice?select=organization_id"
                           f"&notice_id=eq.{assessment_id}&limit=1", headers=headers)
            notices = r.json() if r.status_code == 200 else []
            if not notices:
                return
            org_id = notices[0]["organization_id"]
            # owning partner (via workspace)
            r = client.get(f"{SB}/rest/v1/partner_workspace?select=partner_id"
                           f"&client_org_id=eq.{org_id}&limit=1", headers=headers)
            ws = r.json() if r.status_code == 200 else []
            if not ws:
                return  # normal customer assessment — no branding
            r = client.get(f"{SB}/rest/v1/partner?select=id,logo_hash,brand_color"
                           f"&id=eq.{ws[0]['partner_id']}&limit=1", headers=headers)
            prows = r.json() if r.status_code == 200 else []
            if not prows:
                return
            p = prows[0]
            branding = {"partner_id": p["id"], "logo_hash": p.get("logo_hash"),
                        "brand_color": p.get("brand_color"), "frozen_at": "approval"}
            client.patch(
                f"{SB}/rest/v1/report_snapshot?snapshot_id=eq.{snapshot_id}",
                headers={**headers, "Content-Type": "application/json", "Prefer": "return=minimal"},
                json={"branding_applied": branding},
            )
    except Exception as exc:  # noqa: BLE001 — branding freeze must never fail approval
        log.warning("branding freeze skipped for %s: %s", assessment_id[:12], exc)


# ── White-label feed aggregation (per-cohort, identity-free) ──

_PERMITTED_USE = (
    "Aggregate privacy intelligence by industry cohort. No organization "
    "identities, cohort membership, or raw source clause text is included. "
    "Each record carries confidence metadata and versioning. Redistribution "
    "requires a data license agreement."
)


def _vci_band_label(score: float) -> str:
    if score >= 90:
        return "Very High"
    if score >= 75:
        return "High"
    if score >= 60:
        return "Moderate"
    if score >= 40:
        return "Low"
    return "Very Low"


async def build_feed_aggregates() -> dict:
    """Per-cohort (industry × object_type) aggregates with the SAME population
    exclusions as the benchmark/quarterly population (CQS-eligible, non-rehearsal),
    n<10 suppressed. Computed live per call — never baked at insert."""
    allowed = objects_for_product("white_label")
    allowed_types = {o["object_type"] for o in allowed}
    visibility_map = {o["object_type"]: o["visibility"] for o in allowed}

    # Eligibility (live): CQS-eligible = has an open_web notice (population.py parity).
    cqs_r = await supabase_rest_get(
        "privacy_notice", select="organization_id", filters="notice_type=eq.open_web", limit=10000)
    cqs_eligible = {n["organization_id"] for n in (cqs_r.json() if cqs_r.status_code == 200 else [])
                    if n.get("organization_id")}
    # Excluded: origin='rehearsal' (same exclusion as the quarterly population).
    reh_r = await supabase_rest_get(
        "organization", select="organization_id", filters="origin=eq.rehearsal", limit=10000)
    rehearsal = {o["organization_id"] for o in (reh_r.json() if reh_r.status_code == 200 else [])}

    # Org → industry.
    org_r = await supabase_rest_get("organization", select="organization_id,industry", limit=10000)
    industry_of = {o["organization_id"]: (o.get("industry") or "unknown")
                   for o in (org_r.json() if org_r.status_code == 200 else [])}

    # Latest derived item per org × object_type (dedupe, newest first).
    der_r = await supabase_rest_get(
        "derived_data_item",
        select="object_type,organization_id,score,confidence_score,formula_version_id,"
               "scoring_model_version,source_corpus_version,benchmark_population_version,generated_at",
        filters="order=generated_at.desc", limit=5000)
    derived = der_r.json() if der_r.status_code == 200 else []

    # cohort key = (industry, object_type) → {orgs:set, scores:[], vcis:[], meta}
    cohorts: dict[tuple[str, str], dict] = {}
    seen: set[str] = set()
    for d in derived:
        otype = d.get("object_type", "")
        org_id = d.get("organization_id", "")
        if otype not in allowed_types or not org_id:
            continue
        # SAME exclusions as the benchmark/quarterly population — applied LIVE.
        if org_id not in cqs_eligible or org_id in rehearsal:
            continue
        dedupe = f"{org_id}:{otype}"
        if dedupe in seen:
            continue
        seen.add(dedupe)

        industry = industry_of.get(org_id, "unknown")
        ck = (industry, otype)
        c = cohorts.setdefault(ck, {"orgs": set(), "scores": [], "vcis": [], "meta": d})
        c["orgs"].add(org_id)
        if d.get("score") is not None:
            c["scores"].append(float(d["score"]))
        c["vcis"].append(float(d.get("confidence_score") or 0) * 100)

    records = []
    suppressed = 0
    for (industry, otype), c in sorted(cohorts.items()):
        n = len(c["orgs"])
        if n < MIN_COHORT_N:  # OD-05 + DIR-006 — never leaves the process
            suppressed += 1
            continue
        m = c["meta"]
        vci_mean = round(statistics.mean(c["vcis"]), 1) if c["vcis"] else 0.0
        records.append({
            "segment": industry,
            "object_type": otype,
            "population_n": n,
            "score_mean": round(statistics.mean(c["scores"]), 2) if c["scores"] else None,
            "score_median": round(statistics.median(c["scores"]), 2) if c["scores"] else None,
            "vci": {"score": vci_mean, "band": _vci_band_label(vci_mean)},
            "formula_version": m.get("formula_version_id", ""),
            "scoring_model_version": m.get("scoring_model_version") or settings.scoring_model_version,
            "source_corpus_version": m.get("source_corpus_version") or settings.source_corpus_version,
            "benchmark_population_version": m.get("benchmark_population_version") or "",
            "visibility_note": visibility_map.get(otype, ""),
        })

    from datetime import date
    return {
        "dataset_id": str(uuid4()),
        "schema_version": FEED_SCHEMA_VERSION,
        "grain": "industry_x_object_type",
        "refresh_date": str(date.today()),
        "record_count": len(records),
        "suppressed_cohort_count": suppressed,
        "min_cohort_n": MIN_COHORT_N,
        "permitted_use": _PERMITTED_USE,
        "confidence_metadata": {
            "vci_formula": "NLP 30% + Benchmark 25% + Regulatory 15% + Enforcement 15% + Source 15%",
            "suppression_threshold": 40,
            "min_cohort_n": MIN_COHORT_N,
            "population_note": "CQS-eligible orgs only; origin='rehearsal' excluded (live).",
        },
        "records": records,
    }
