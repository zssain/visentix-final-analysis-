"""F21 — Quarterly Global Privacy Intelligence Report (Deliverable 4, v1 BASELINE).

Manual build only: materialize the eligible population → compute the in-scope
Service-4 metrics (cited verbatim against reference/derived-catalog-S4.md) →
suppress (OD-05 n<10 + single-org max-share) → anonymization gate → freeze on
expert approval. v1 has no prior quarter → ZERO QoQ deltas.

`compute_metrics` is pure (takes fetched data) so the suppression / gate /
baseline rules are unit-testable without a DB.
"""

from __future__ import annotations

import json
from collections import defaultdict
from uuid import uuid4

from app.config import settings
from app.db import supabase_rest_get, supabase_rest_patch, supabase_rest_post
from app.logging import get_logger

log = get_logger(__name__)

MIN_N = 10                       # OD-05 LOW_CONFIDENCE_COHORT_N + DIR-006
MAX_SHARE = 0.50                 # single-org dominance: no entity > 50% of a numerator
DMI_OBJECT = "disclosure_maturity"   # F-005_v1
AI_OBJECT = "ai_transparency"        # F-007_v1

# Metric → authoritative Catalog citation (reference/derived-catalog-S4.md).
CITATION = {
    "S4-001": "S4-001 Organizations Analyzed",
    "S4-002": "S4-002 Privacy Clauses Analyzed (v1 proxy: non-noise clauses; no extraction_confidence threshold in config)",
    "S4-003": "S4-003 Industries Benchmarked (sample_size >= 10)",
    "S4-004": "S4-004 Jurisdictions Covered (active regulator mapping)",
    "S4-005": "S4-005 Disclosure Maturity Index (avg F-005, confidence + industry-representation weighted)",
    "S4-006": "S4-006 AI Transparency Index (avg F-007 over AI-relevant notices, industry + confidence weighted)",
    "S4-018": "S4-018 Top Enforcement Theme Share (resolved-only — deliberate Rule-3 tightening vs catalog)",
    "GAPS": "Top Disclosure Gaps — finding-frequency report aggregate (not a numbered Service-4 formula)",
}


# ── Quarter window ───────────────────────────────────────────

def quarter_window(quarter: str) -> tuple[str, str]:
    """'2026-Q3' → ('2026-07-01','2026-09-30'). Raises ValueError on bad input."""
    try:
        year_s, q = quarter.split("-Q")
        year, qn = int(year_s), int(q)
    except (ValueError, AttributeError):
        raise ValueError(f"Bad quarter '{quarter}', expected e.g. '2026-Q3'")
    if qn not in (1, 2, 3, 4):
        raise ValueError(f"Quarter must be Q1–Q4, got Q{qn}")
    starts = {1: "01-01", 2: "04-01", 3: "07-01", 4: "10-01"}
    ends = {1: "03-31", 2: "06-30", 3: "09-30", 4: "12-31"}
    return f"{year}-{starts[qn]}", f"{year}-{ends[qn]}"


# ── Suppression primitives ───────────────────────────────────

def _max_share(contributions: list[float]) -> float:
    total = sum(contributions)
    if total <= 0:
        return 0.0
    return max(contributions) / total


def _suppress_decision(population_n: int, contributions: list[float]) -> tuple[bool, str | None]:
    """Return (suppressed, reason). n<10 (OD-05/DIR-006) OR single-org dominance."""
    if population_n < MIN_N:
        return True, "below_min_sample_n10"
    if contributions and _max_share(contributions) > MAX_SHARE:
        return True, "single_org_dominance"
    return False, None


def _metric(metric_id: str, *, value=None, value_label=None, population_n=0,
            contributions=None) -> dict:
    suppressed, reason = _suppress_decision(population_n, contributions or [])
    return {
        "metric_id": metric_id,
        "value": None if suppressed else value,
        "value_label": None if suppressed else value_label,
        "population_n": population_n,
        "suppressed": suppressed,
        "suppression_reason": reason,
        "formula_citation": CITATION.get(metric_id, metric_id),
    }


# ── Weighted index (S4-005 / S4-006) ─────────────────────────

def _weighted_index(rows: list[dict], industry_of: dict) -> tuple[float | None, int, list[float]]:
    """Confidence-weighted mean per industry, then equal-industry average over
    industries with n>=10 (S4-005/006 'weighted by source confidence and
    industry representation'). Returns (value, population_n, contributions)."""
    by_ind: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        ind = industry_of.get(r["org_id"]) or "unknown"
        if ind in ("", "unknown"):
            continue
        by_ind[ind].append(r)
    ind_means: list[float] = []
    ind_counts: list[float] = []
    total = 0
    for _ind, rs in by_ind.items():
        if len(rs) < MIN_N:
            continue
        wsum = sum(x["confidence"] for x in rs) or 1e-9
        ind_means.append(sum(x["score"] * x["confidence"] for x in rs) / wsum)
        ind_counts.append(len(rs))
        total += len(rs)
    if not ind_means:
        return None, 0, []
    return round(sum(ind_means) / len(ind_means), 2), total, ind_counts


# ── Pure compute over already-fetched data ───────────────────

def compute_metrics(data: dict) -> list[dict]:
    """Compute all in-scope S4 metrics. `data` keys:
      population: set[str]                      eligible org ids
      industry_of: {org_id: industry}
      snapshot_of: {org_id: {scored_clause_count:int}}   latest snapshot payload per org
      notice_of:   {org_id: {jurisdictions:[..], ai_relevant:bool}}  latest notice per org
      dmi_rows / ai_rows: [{org_id, score, confidence}]
      findings_of: {org_id: set[finding_code]}
      resolved_enforcement: [{issue_tags:[..], target_org}]
      regulator_jurisdictions: set[str]
    NO QoQ deltas are produced (baseline)."""
    pop = data["population"]
    industry_of = data["industry_of"]
    n_orgs = len(pop)
    metrics: list[dict] = []

    # S4-001 Organizations Analyzed
    metrics.append(_metric("S4-001", value=n_orgs, population_n=n_orgs,
                           contributions=[1] * n_orgs))

    # S4-002 Privacy Clauses Analyzed (non-noise proxy; latest snapshot per org)
    per_org_clauses = [int(data["snapshot_of"].get(o, {}).get("scored_clause_count", 0)) for o in pop]
    metrics.append(_metric("S4-002", value=sum(per_org_clauses), population_n=n_orgs,
                           contributions=[float(c) for c in per_org_clauses]))

    # S4-003 Industries Benchmarked (distinct industries with >=10 orgs)
    ind_counts: dict[str, int] = defaultdict(int)
    for o in pop:
        ind = industry_of.get(o)
        if ind and ind != "unknown":
            ind_counts[ind] += 1
    industries = [i for i, c in ind_counts.items() if c >= MIN_N]
    metrics.append(_metric("S4-003", value=len(industries), population_n=n_orgs,
                           contributions=[1] * n_orgs))

    # S4-004 Jurisdictions Covered (population jurisdictions ∩ active regulator mapping)
    pop_juris: set[str] = set()
    for o in pop:
        for j in data["notice_of"].get(o, {}).get("jurisdictions", []):
            pop_juris.add(j)
    covered = pop_juris & set(data["regulator_jurisdictions"])
    metrics.append(_metric("S4-004", value=len(covered), population_n=n_orgs,
                           contributions=[1] * n_orgs))

    # S4-005 Disclosure Maturity Index
    dmi_rows = [r for r in data["dmi_rows"] if r["org_id"] in pop]
    dmi_val, dmi_n, dmi_contrib = _weighted_index(dmi_rows, industry_of)
    metrics.append(_metric("S4-005", value=dmi_val, population_n=dmi_n, contributions=dmi_contrib))

    # S4-006 AI Transparency Index (AI-relevant notices only)
    ai_rows = [r for r in data["ai_rows"]
               if r["org_id"] in pop and data["notice_of"].get(r["org_id"], {}).get("ai_relevant")]
    ai_val, ai_n, ai_contrib = _weighted_index(ai_rows, industry_of)
    metrics.append(_metric("S4-006", value=ai_val, population_n=ai_n, contributions=ai_contrib))

    # S4-018 Top Enforcement Theme Share (RESOLVED only; Rule-3 tightening)
    theme_orgs: dict[str, set] = defaultdict(set)   # theme → set of target_orgs (per-theme drop)
    theme_count: dict[str, int] = defaultdict(int)
    org_records: dict[str, int] = defaultdict(int)  # target_org → records (metric-level max-share)
    total_tags = 0
    for rec in data["resolved_enforcement"]:
        tgt = rec.get("target_org") or "?"
        for tag in (rec.get("issue_tags") or []):
            theme_count[tag] += 1
            theme_orgs[tag].add(tgt)
            org_records[tgt] += 1
            total_tags += 1
    themes = []
    for tag, cnt in sorted(theme_count.items(), key=lambda kv: kv[1], reverse=True):
        # per-theme single-org dominance: drop a theme one target_org fully owns
        if len(theme_orgs[tag]) < 2:
            continue
        themes.append({"theme": tag, "share_pct": round(100 * cnt / total_tags, 1) if total_tags else 0.0})
    # metric-level single-org dominance = one TARGET ORG owning >50% of records
    # (a top theme legitimately dominating the distribution is NOT suppression).
    metrics.append(_metric("S4-018",
                           value_label=json.dumps(themes[:8]) if themes else None,
                           population_n=total_tags,
                           contributions=[float(c) for c in org_records.values()]))

    # Top Disclosure Gaps (finding frequency; per-org presence; drop single-org gaps)
    code_orgs: dict[str, set] = defaultdict(set)
    for o, codes in data["findings_of"].items():
        if o in pop:
            for c in codes:
                code_orgs[c].add(o)
    gaps = []
    for code, orgs in sorted(code_orgs.items(), key=lambda kv: len(kv[1]), reverse=True):
        if len(orgs) < 2:                     # single-org → not published
            continue
        gaps.append({"code": code, "prevalence_pct": round(100 * len(orgs) / n_orgs, 1) if n_orgs else 0.0})
    metrics.append(_metric("GAPS",
                           value_label=json.dumps(gaps[:8]) if gaps else None,
                           population_n=n_orgs,
                           contributions=[1] * n_orgs))
    return metrics


def run_anonymization_gate(metrics: list[dict]) -> dict:
    """Independent re-check: ANY unsuppressed metric that still violates the
    rules is a hard failure — the snapshot stays draft-invalid (step 3)."""
    violations = []
    for m in metrics:
        if m["suppressed"]:
            continue
        if (m["population_n"] or 0) < MIN_N:
            violations.append({"metric_id": m["metric_id"], "reason": "unsuppressed_below_n10",
                               "population_n": m["population_n"]})
    return {"passed": len(violations) == 0, "violations": violations}


# ── Async fetch + persist ────────────────────────────────────

async def _fetch_data(quarter: str) -> tuple[dict, dict]:
    """Fetch everything needed and shape it for compute_metrics. Returns
    (data, population_criteria)."""
    start, end = quarter_window(quarter)

    # completed assessment in window = a report_snapshot created in-window
    r = await supabase_rest_get(
        "report_snapshot", select="organization_id,notice_id,payload,created_at",
        filters=f"created_at=gte.{start}&created_at=lte.{end}T23:59:59&order=created_at.desc", limit=10000)
    snaps = r.json() if r.status_code == 200 else []
    completed = {s["organization_id"] for s in snaps if s.get("organization_id")}

    # CQS-eligible = has an open_web notice (population.py parity)
    r = await supabase_rest_get("privacy_notice", select="organization_id",
                                filters="notice_type=eq.open_web", limit=10000)
    cqs = {n["organization_id"] for n in (r.json() if r.status_code == 200 else []) if n.get("organization_id")}

    # rehearsal excluded
    r = await supabase_rest_get("organization", select="organization_id",
                                filters="origin=eq.rehearsal", limit=10000)
    rehearsal = {o["organization_id"] for o in (r.json() if r.status_code == 200 else [])}

    population = (completed & cqs) - rehearsal

    # org → industry
    r = await supabase_rest_get("organization", select="organization_id,industry", limit=10000)
    industry_of = {o["organization_id"]: (o.get("industry") or "unknown")
                   for o in (r.json() if r.status_code == 200 else [])}

    # latest snapshot payload per org (snaps already desc by created_at)
    snapshot_of: dict[str, dict] = {}
    for s in snaps:
        oid = s.get("organization_id")
        if oid in population and oid not in snapshot_of:
            p = s.get("payload")
            try:
                snapshot_of[oid] = json.loads(p) if isinstance(p, str) else (p or {})
            except (ValueError, TypeError):
                snapshot_of[oid] = {}

    # latest notice per org: jurisdictions + ai relevance
    r = await supabase_rest_get(
        "privacy_notice", select="organization_id,jurisdiction_scope,ai_disclosure_presence,retrieval_date",
        filters="order=retrieval_date.desc", limit=10000)
    notice_of: dict[str, dict] = {}
    for n in (r.json() if r.status_code == 200 else []):
        oid = n.get("organization_id")
        if oid in population and oid not in notice_of:
            notice_of[oid] = {"jurisdictions": n.get("jurisdiction_scope") or [],
                              "ai_relevant": bool(n.get("ai_disclosure_presence"))}

    # latest derived per org × object_type (DMI, AI)
    r = await supabase_rest_get(
        "derived_data_item", select="organization_id,object_type,score,confidence_score,generated_at",
        filters=f"object_type=in.({DMI_OBJECT},{AI_OBJECT})&order=generated_at.desc", limit=20000)
    seen: set[str] = set()
    dmi_rows, ai_rows = [], []
    for d in (r.json() if r.status_code == 200 else []):
        oid, ot = d.get("organization_id"), d.get("object_type")
        if oid not in population:
            continue
        key = f"{oid}:{ot}"
        if key in seen:
            continue
        seen.add(key)
        row = {"org_id": oid, "score": float(d.get("score") or 0),
               "confidence": float(d.get("confidence_score") or 0.5)}
        (dmi_rows if ot == DMI_OBJECT else ai_rows).append(row)

    # findings per org (distinct codes)
    r = await supabase_rest_get("risk_finding", select="organization_id,finding_type_code", limit=50000)
    findings_of: dict[str, set] = defaultdict(set)
    for f in (r.json() if r.status_code == 200 else []):
        if f.get("organization_id") in population and f.get("finding_type_code"):
            findings_of[f["organization_id"]].add(f["finding_type_code"])

    # resolved enforcement only
    r = await supabase_rest_get("enforcement_record", select="issue_tags,target_org",
                                filters="resolution_status=eq.resolved", limit=10000)
    resolved_enforcement = r.json() if r.status_code == 200 else []

    # regulator jurisdictions (active mapping)
    r = await supabase_rest_get("regulator", select="jurisdiction", limit=1000)
    regulator_jurisdictions = {x.get("jurisdiction") for x in (r.json() if r.status_code == 200 else []) if x.get("jurisdiction")}

    data = {
        "population": population, "industry_of": industry_of,
        "snapshot_of": snapshot_of, "notice_of": notice_of,
        "dmi_rows": dmi_rows, "ai_rows": ai_rows, "findings_of": dict(findings_of),
        "resolved_enforcement": resolved_enforcement,
        "regulator_jurisdictions": regulator_jurisdictions,
    }
    criteria = {
        "rule": "completed assessment in quarter window AND CQS-eligible (open_web notice) AND origin != 'rehearsal'",
        "quarter_window": [start, end], "eligible_org_count": len(population),
        "min_sample_n": MIN_N, "max_single_org_share": MAX_SHARE,
        "s4_002_note": "extraction_confidence threshold absent in config → non-noise-clause proxy",
        "s4_018_note": "enforcement themes restricted to resolution_status='resolved' (Rule-3 tightening)",
        "s4_005_006_weighting": "confidence-weighted mean per industry, equal-industry average over industries with n>=10",
        "baseline": True, "qoq_deltas": "none (v1 baseline)",
    }
    return data, criteria


FORMULA_VERSIONS = {"S4-005": "F-005_v1", "S4-006": "F-007_v1", "corpus": settings.source_corpus_version}


async def build_quarterly(quarter: str) -> dict:
    """Manual build: materialize → compute → gate → persist DRAFT snapshot."""
    quarter_window(quarter)  # validate
    data, criteria = await _fetch_data(quarter)
    metrics = compute_metrics(data)
    gate = run_anonymization_gate(metrics)

    snapshot_id = str(uuid4())
    await supabase_rest_post("quarterly_snapshot", {
        "id": snapshot_id, "quarter": quarter, "status": "draft",
        "corpus_version": str(settings.source_corpus_version),
        "formula_versions": json.dumps(FORMULA_VERSIONS),
        "population_criteria": json.dumps(criteria),
        "gate_result": json.dumps(gate),
    })
    rows = [{
        "id": str(uuid4()), "snapshot_id": snapshot_id, "metric_id": m["metric_id"],
        "value": m["value"], "value_label": m["value_label"], "population_n": m["population_n"],
        "suppressed": m["suppressed"], "suppression_reason": m["suppression_reason"],
        "formula_citation": m["formula_citation"],
    } for m in metrics]
    if rows:
        await supabase_rest_post("quarterly_metric", rows)

    log.info("quarterly build %s: %d metrics, gate=%s", quarter, len(rows), gate["passed"])
    return {"snapshot_id": snapshot_id, "quarter": quarter, "gate_result": gate,
            "metric_count": len(rows)}


# ── Approval (expert-review permission) + freeze guard ───────

async def _snapshot(snapshot_id: str) -> dict | None:
    r = await supabase_rest_get("quarterly_snapshot", select="*",
                                filters=f"id=eq.{snapshot_id}", limit=1)
    rows = r.json() if r.status_code == 200 else []
    return rows[0] if rows else None


async def approve_quarterly(snapshot_id: str, approver_id: str) -> dict:
    """Freeze on expert approval. Requires the gate passed. Service-layer guard
    against re-approving/mutating an already-approved snapshot (the DB trigger
    is the second line)."""
    snap = await _snapshot(snapshot_id)
    if not snap:
        raise ValueError("snapshot_not_found")
    if snap["status"] == "approved":
        raise ValueError("already_approved")
    gate = snap.get("gate_result")
    if isinstance(gate, str):
        gate = json.loads(gate) if gate else {}
    if not (gate or {}).get("passed"):
        raise ValueError("gate_failed")  # cannot approve a draft-invalid snapshot
    await supabase_rest_patch("quarterly_snapshot", f"id=eq.{snapshot_id}", {
        "status": "approved", "approved_by": approver_id,
        "approved_at": "now()", "frozen_at": "now()",
    })
    return {"snapshot_id": snapshot_id, "status": "approved", "approved_by": approver_id}


# ── Read paths ───────────────────────────────────────────────

def _public_metrics(rows: list[dict]) -> list[dict]:
    """Public payload = NON-suppressed metrics only (suppressed are absent)."""
    return [{
        "metric_id": m["metric_id"], "value": m["value"], "value_label": m["value_label"],
        "population_n": m["population_n"], "formula_citation": m["formula_citation"],
    } for m in rows if not m["suppressed"]]


async def _metrics_for(snapshot_id: str) -> list[dict]:
    r = await supabase_rest_get("quarterly_metric",
                                select="metric_id,value,value_label,population_n,suppressed,suppression_reason,formula_citation",
                                filters=f"snapshot_id=eq.{snapshot_id}&order=metric_id.asc", limit=1000)
    return r.json() if r.status_code == 200 else []


# ── Public methodology copy — SME-approved verbatim (OQ-4, acting SME 2026-07-28) ──
METHODOLOGY_INTRO = (
    "Every figure in this report is computed from our maintained corpus using "
    "versioned formulas, frozen at publication. Corpus size, population criteria, "
    "and formula versions are stated below."
)
SUPPRESSION_PUBLIC = (
    "Statistics are published only for groups of 10 or more organizations, and "
    "never where a single organization dominates a figure. Where those conditions "
    "are not met, the statistic is omitted."
)
S4018_PUBLIC = (
    "Enforcement themes are computed only from actions we have fully verified "
    "against the acting regulator and named company — a stricter standard than "
    "raw counts."
)


def methodology_block(snap: dict, metrics: list[dict]) -> dict:
    """Auto-generated from snapshot metadata — NO hand-written numbers. Prose is
    the SME-approved public copy (OQ-4)."""
    crit = snap.get("population_criteria")
    crit = json.loads(crit) if isinstance(crit, str) else (crit or {})
    fv = snap.get("formula_versions")
    fv = json.loads(fv) if isinstance(fv, str) else (fv or {})
    by_id = {m["metric_id"]: m for m in metrics}

    def _val(mid):
        m = by_id.get(mid) or {}
        return None if m.get("suppressed") else m.get("value")

    return {
        "quarter": snap["quarter"],
        "quarter_window": crit.get("quarter_window"),
        "intro": METHODOLOGY_INTRO,
        "corpus": {
            "organizations": _val("S4-001"), "clauses_analyzed": _val("S4-002"),
            "industries_benchmarked": _val("S4-003"), "jurisdictions_covered": _val("S4-004"),
        },
        "population_criteria": crit.get("rule"),
        "formula_versions": fv,
        "suppression_rule": SUPPRESSION_PUBLIC,
        "s4_002_note": crit.get("s4_002_note"),
        "s4_018_note": S4018_PUBLIC,
        "weighting": crit.get("s4_005_006_weighting"),
        "baseline_note": "Baseline edition — trend deltas begin next quarter.",
        "reproducible": "Every number is a stored quarterly_metric; the snapshot is frozen (DIR-010).",
    }


async def get_latest_approved() -> dict | None:
    r = await supabase_rest_get("quarterly_snapshot", select="*",
                                filters="status=eq.approved&order=created_at.desc", limit=1)
    rows = r.json() if r.status_code == 200 else []
    if not rows:
        return None
    return await _public_payload(rows[0])


async def get_by_quarter(quarter: str) -> dict | None:
    r = await supabase_rest_get("quarterly_snapshot", select="*",
                                filters=f"quarter=eq.{quarter}&status=eq.approved&order=created_at.desc", limit=1)
    rows = r.json() if r.status_code == 200 else []
    if not rows:
        return None
    return await _public_payload(rows[0])


async def _public_payload(snap: dict) -> dict:
    metrics = await _metrics_for(snap["id"])
    return {
        "quarter": snap["quarter"], "status": snap["status"],
        "snapshot_id": snap["id"], "frozen_at": snap.get("frozen_at"),
        "baseline": True, "qoq_deltas": None,   # v1 baseline — MUST NOT publish deltas
        "metrics": _public_metrics(metrics),
        "methodology": methodology_block(snap, metrics),
    }


async def list_all_snapshots() -> list[dict]:
    r = await supabase_rest_get(
        "quarterly_snapshot",
        select="id,quarter,status,gate_result,created_at,approved_by,approved_at,frozen_at",
        filters="order=created_at.desc", limit=500)
    return r.json() if r.status_code == 200 else []


async def get_admin_snapshot(snapshot_id: str) -> dict | None:
    snap = await _snapshot(snapshot_id)
    if not snap:
        return None
    metrics = await _metrics_for(snapshot_id)
    return {"snapshot": snap, "metrics": metrics, "methodology": methodology_block(snap, metrics)}
