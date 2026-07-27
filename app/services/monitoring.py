"""Continuous-monitoring read layer (F07 — M-06/M-07/M-08).

Surfaces three deterministic, org-scoped views over already-stored data:

- **trend** (M-06 / F-012): the org's `derived_data_item` score history across
  `report_snapshot`s, with deltas computed by the *versioned* `compute_f012`
  formula — never a fabricated trend. A single-snapshot org returns an explicit
  `baseline_established` state.
- **events** (M-07): `monitoring_event` rows for the org. ⚠️ Live drift: the
  applied `monitoring_event` table has **no `organization_id`** (schema.md §2.8
  declares one; it was never applied). Events are keyed by `source_id` →
  `source_record.url`. We org-scope by matching that URL host to the org's
  `organization.domain` / its `privacy_notice` URLs — the only honest linkage
  that exists live. `trigger_type` is normalized to the schema vocabulary.
- **alerts** (M-08 / F-013): stored `alert_escalation` outputs, joined to
  **resolved** `enforcement_record` rows only. The 623 unresolved enforcement
  rows are never surfaced. Severity is taken from the correlated
  `monitoring_event.severity` when present; F-013→band thresholds are
  expert-owned and are **not** invented here.

Nothing in this module computes a user-facing score itself: trend deltas come
from `compute_f012`, escalations from the stored F-013 outputs.
"""

from __future__ import annotations

import json
from urllib.parse import urlparse

from app.db import supabase_rest_get
from app.services.scoring.formulas_advanced import compute_f012

# object_type → the scored dimensions we surface on the trend hero.
# Keys mirror the stored `derived_data_item.object_type` values (real, not
# invented). F-010 overall_intelligence is the hero figure; the rest are the
# per-dimension scorecards.
OVERALL_TYPE = "overall_intelligence"  # F-010
DIMENSION_TYPES = [
    "regulatory_exposure",   # F-002
    "benchmark_deviation",   # F-003
    "disclosure_maturity",   # F-005
    "transparency",          # F-006
    "ai_transparency",        # F-007
    "compound_risk",         # F-008
]

# Live `monitoring_event.trigger_type` values → the schema.md §2.8 vocabulary
# (notice_changed / score_moved / regulator_signal / cohort_refreshed). A
# content-hash change of a monitored notice *is* a "notice changed" signal.
_TRIGGER_TYPE_MAP = {
    "hash_change": "notice_changed",
    "notice_changed": "notice_changed",
    "score_moved": "score_moved",
    "score_change": "score_moved",
    "regulator_signal": "regulator_signal",
    "cohort_refreshed": "cohort_refreshed",
    "cohort_rebenchmarked": "cohort_refreshed",
}


def _parse_lineage(val) -> dict:
    if isinstance(val, dict):
        return val
    if isinstance(val, str):
        try:
            return json.loads(val)
        except Exception:
            return {}
    return {}


def _vci_from_confidence(conf) -> float | None:
    """Stored confidence is 0–1; surface it as a 0–100 VCI to match the report."""
    if conf is None:
        return None
    try:
        return round(float(conf) * 100, 1)
    except (TypeError, ValueError):
        return None


async def _org_domains(org_id: str) -> set[str]:
    """The URL hosts we can attribute to an org: its `organization.domain` plus
    the hosts of its `privacy_notice` URLs. Used to org-scope `monitoring_event`
    (which carries no organization_id live)."""
    hosts: set[str] = set()

    r = await supabase_rest_get(
        "organization", select="domain",
        filters=f"organization_id=eq.{org_id}", limit=1,
    )
    if r.status_code == 200:
        for row in r.json():
            d = (row or {}).get("domain")
            if d:
                hosts.add(_host(d))

    r = await supabase_rest_get(
        "privacy_notice", select="url",
        filters=f"organization_id=eq.{org_id}", limit=200,
    )
    if r.status_code == 200:
        for row in r.json():
            u = (row or {}).get("url")
            if u:
                hosts.add(_host(u))

    return {h for h in hosts if h}


def _host(value: str) -> str:
    """Normalize a domain or URL to a bare host (no scheme, no www.)."""
    value = (value or "").strip()
    if not value:
        return ""
    if "//" not in value:
        value = "//" + value
    netloc = urlparse(value).netloc or ""
    return netloc.replace("www.", "").lower()


# ── M-06 / F-012: trend ──────────────────────────────────────


async def get_trend(org_id: str) -> dict:
    """F-012 trend over the org's snapshot score history.

    Series is built from stored `derived_data_item` rows grouped by
    `source_snapshot_id`. Deltas use the versioned `compute_f012`; a single
    snapshot returns `baseline_established` (never a fabricated flat line).
    """
    r = await supabase_rest_get(
        "derived_data_item",
        select=(
            "object_type,score,confidence_score,source_snapshot_id,"
            "generated_at,formula_version_id"
        ),
        filters=f"organization_id=eq.{org_id}&order=generated_at.asc",
        limit=2000,
    )
    rows = r.json() if r.status_code == 200 else []
    if not isinstance(rows, list):
        rows = []

    # Group by snapshot, preserving first-seen order (generated_at asc).
    snaps: dict[str, dict] = {}
    order: list[str] = []
    for d in rows:
        sid = d.get("source_snapshot_id")
        if not sid:
            continue
        if sid not in snaps:
            snaps[sid] = {
                "snapshot_id": sid,
                "date": (d.get("generated_at") or "")[:10],
                "generated_at": d.get("generated_at") or "",
                "overall": None,
                "domains": {},
                "vci": None,
            }
            order.append(sid)
        otype = d.get("object_type")
        if otype == OVERALL_TYPE:
            snaps[sid]["overall"] = d.get("score")
            snaps[sid]["vci"] = _vci_from_confidence(d.get("confidence_score"))
        elif otype in DIMENSION_TYPES:
            snaps[sid]["domains"][otype] = d.get("score")

    series = [snaps[sid] for sid in order if snaps[sid]["overall"] is not None]

    if not series:
        return {"org_id": org_id, "state": "no_history", "series": [], "deltas": None}

    if len(series) == 1:
        # First assessment — explicit baseline, deltas hidden (F07 AC-1).
        return {
            "org_id": org_id,
            "state": "baseline_established",
            "series": series,
            "deltas": None,
            "formula_version_id": "F-012_v1",
        }

    prior, current = series[-2], series[-1]

    def _delta(cur_val, prior_val, metric):
        res = compute_f012(
            current_score=cur_val if cur_val is not None else 0.0,
            prior_score=prior_val,
            current_snapshot_id=current["snapshot_id"],
            prior_snapshot_id=prior["snapshot_id"],
            metric_name=metric,
        )
        out = {
            "from": prior_val,
            "to": cur_val,
            "delta_pct": res.score,
            "formula_version_id": res.formula_version_id,
        }
        reason = (res.source_lineage or {}).get("reason")
        if reason:
            out["reason"] = reason
        return out

    domain_deltas = {}
    for k in DIMENSION_TYPES:
        cur = current["domains"].get(k)
        pri = prior["domains"].get(k)
        if cur is not None and pri is not None:
            domain_deltas[k] = _delta(cur, pri, k)

    return {
        "org_id": org_id,
        "state": "populated",
        "series": series,
        "deltas": {
            "overall": _delta(current["overall"], prior["overall"], OVERALL_TYPE),
            "domains": domain_deltas,
        },
        "formula_version_id": "F-012_v1",
    }


# ── M-07: change feed ────────────────────────────────────────


async def get_events(org_id: str, limit: int = 100) -> dict:
    """`monitoring_event` rows attributable to the org, newest first.

    Scoped via source URL ↔ org domain (see module docstring). Returns an
    honest empty feed when the org has no attributable events.
    """
    hosts = await _org_domains(org_id)
    if not hosts:
        return {"org_id": org_id, "state": "no_events", "events": []}

    # Resolve the source_ids whose URL host belongs to the org.
    r = await supabase_rest_get(
        "source_record", select="source_id,url", limit=5000,
    )
    src_rows = r.json() if r.status_code == 200 else []
    source_ids = [
        s["source_id"] for s in src_rows
        if isinstance(s, dict) and _host(s.get("url", "")) in hosts and s.get("source_id")
    ]
    if not source_ids:
        return {"org_id": org_id, "state": "no_events", "events": []}

    in_list = ",".join(source_ids)
    r = await supabase_rest_get(
        "monitoring_event",
        select=(
            "event_id,trigger_type,source_id,prior_value,current_value,"
            "material_change_indicator,severity,ts"
        ),
        filters=f"source_id=in.({in_list})&order=ts.desc",
        limit=limit,
    )
    ev_rows = r.json() if r.status_code == 200 else []
    if not isinstance(ev_rows, list):
        ev_rows = []

    url_by_source = {
        s["source_id"]: s.get("url", "")
        for s in src_rows if isinstance(s, dict) and s.get("source_id")
    }

    events = []
    for e in ev_rows:
        raw = e.get("trigger_type") or ""
        norm = _TRIGGER_TYPE_MAP.get(raw, raw)
        item = {
            "event_id": e.get("event_id"),
            "type": norm,
            "raw_trigger_type": raw,
            "severity": e.get("severity"),
            "material_change_indicator": e.get("material_change_indicator"),
            "source_id": e.get("source_id"),
            "source_url": url_by_source.get(e.get("source_id"), ""),
            "occurred_at": e.get("ts"),
        }
        # Lead with from→to numbers only for score moves (never prose diffs, per
        # F07 guardrails). Notice-changed events carry the content-hash change.
        if norm == "score_moved":
            item["from"] = e.get("prior_value")
            item["to"] = e.get("current_value")
        else:
            item["prior_hash"] = e.get("prior_value")
            item["current_hash"] = e.get("current_value")
        events.append(item)

    state = "populated" if events else "no_events"
    return {"org_id": org_id, "state": state, "events": events}


# ── M-08 / F-013: alert center ───────────────────────────────


async def get_alerts(org_id: str) -> dict:
    """Stored F-013 `alert_escalation` outputs for the org, each carrying its
    finding lineage and — only where they exist — **resolved** enforcement refs.

    Unresolved enforcement (623 rows) is never surfaced (WS1 hard rule).
    """
    r = await supabase_rest_get(
        "derived_data_item",
        select=(
            "derived_data_item_id,score,confidence_score,source_snapshot_id,"
            "source_lineage,formula_version_id,generated_at"
        ),
        filters=(
            f"organization_id=eq.{org_id}"
            "&object_type=eq.alert_escalation"
            "&order=generated_at.desc"
        ),
        limit=200,
    )
    esc_rows = r.json() if r.status_code == 200 else []
    if not isinstance(esc_rows, list):
        esc_rows = []

    # Resolved enforcement for this org ONLY. Never unresolved.
    r = await supabase_rest_get(
        "enforcement_record",
        select=(
            "enforcement_id,entity_name,regulator_id,official_url,"
            "action_date,resolution_status,domains"
        ),
        filters=f"organization_id=eq.{org_id}&resolution_status=eq.resolved",
        limit=200,
    )
    enf_rows = r.json() if r.status_code == 200 else []
    enforcement_refs = [
        {
            "enforcement_id": e.get("enforcement_id"),
            "entity_name": e.get("entity_name"),
            "regulator_id": e.get("regulator_id"),
            "official_url": e.get("official_url"),
            "action_date": e.get("action_date"),
            "resolution_status": e.get("resolution_status"),
        }
        for e in enf_rows if isinstance(e, dict)
    ]

    alerts = []
    for d in esc_rows:
        lineage = _parse_lineage(d.get("source_lineage"))
        alerts.append({
            "alert_id": d.get("derived_data_item_id"),
            "escalation_score": d.get("score"),
            # Severity is only surfaced when a real stored value backs it.
            # F-013→severity band thresholds are expert-owned; not invented here.
            "severity": lineage.get("severity"),
            "formula_version_id": d.get("formula_version_id") or "F-013_v1",
            "vci": _vci_from_confidence(d.get("confidence_score")),
            "snapshot_id": d.get("source_snapshot_id"),
            "generated_at": d.get("generated_at"),
            "finding_lineage": lineage,
            "enforcement_refs": enforcement_refs,
        })

    state = "populated" if alerts else "no_alerts"
    return {"org_id": org_id, "state": state, "alerts": alerts}
