"""F19 — Bulk Screening runner + results assembly.

Product surface on the verified reassessment kernel. Per row, sequentially:
  1. Resolve a FRESH screening organization (never an existing customer tenant —
     the cross-tenant trap: an analyst scanning 200 companies will eventually
     include one of our own customers; that customer is scored fresh from the
     public notice only, under the bulk-job owner's tenant, never attached to
     their real org record).
  2. Intake the URL via the SHARED F01 path (extract → decompose → classify →
     persist_notice) — one intake path, no fork.
  3. Score via trigger_reassessment (the kernel → live_scoring.score_and_persist)
     — the SINGLE scoring path. No forked scorer.

Results are draft-grade: score_and_persist enqueues each assessment as an SME
DRAFT and never auto-approves; the results endpoints surface review_status per
row so the UI can badge it. Vocabulary is exposure/maturity only.
"""

from __future__ import annotations

import csv
import io
import json
import re
import urllib.parse
from uuid import uuid4

from app.db import (
    supabase_rest_get,
    supabase_rest_patch,
    supabase_rest_post,
)
from app.logging import get_logger
from app.services.intake.decompose import decompose
from app.services.intake.discover import discover_policy_url, is_direct_policy_url
from app.services.intake.extract import extract_from_url
from app.services.intake.persist import classify_clauses, persist_notice
from app.services.reassessment import trigger_reassessment
from app.services.scoring.heatmap import TAXONOMY_DOMAINS
from app.services.scoring.vci import SUPPRESSION_THRESHOLD

log = get_logger(__name__)

MAX_ROWS = 200
SUPPRESSED_CELL = "suppressed_low_confidence"

# SME-set copy (F19 OQ-1, acting SME 2026-07-28). Plain-language, no internal
# vocabulary, no verdict terms.
EXPORT_NOTICE = (
    "Screening intelligence — automated analysis, not expert-reviewed. "
    "Scores are draft-grade comparisons, not conclusions."
)
INSUFFICIENT_PROFILE_TEXT = (
    "Not scored — we could not build a reliable company profile or peer "
    "comparison from public information. No score is shown rather than an "
    "unfair one."
)

# Severity ordering for ranking top findings (highest exposure first).
_SEVERITY_RANK = {"critical": 4, "high": 3, "moderate": 2, "medium": 2, "low": 1, "": 0}


# ── URL validation ───────────────────────────────────────────

def url_well_formed(url: str) -> bool:
    """True if url has an http/https scheme and a parseable host."""
    try:
        p = urllib.parse.urlparse((url or "").strip())
    except ValueError:
        return False
    return p.scheme in ("http", "https") and bool(p.netloc)


# ── Job creation + tenancy guard ─────────────────────────────

async def has_active_job(owner_org_id: str) -> bool:
    """True if this tenant already has a queued/running bulk job (AC-11 guard)."""
    r = await supabase_rest_get(
        "bulk_job",
        select="id",
        filters=f"org_id=eq.{owner_org_id}&status=in.(queued,running)",
        limit=1,
    )
    return bool(r.status_code == 200 and r.json())


async def create_job(
    owner_org_id: str, created_by: str, label: str, rows: list[dict],
) -> str:
    """Insert the bulk_job + its pending rows. Returns bulk_job_id."""
    job_id = str(uuid4())
    await supabase_rest_post("bulk_job", {
        "id": job_id,
        "org_id": owner_org_id,
        "created_by": created_by,
        "label": label or "",
        "status": "queued",
        "row_count": len(rows),
        "completed_count": 0,
        "failed_count": 0,
    })
    row_payload = [
        {
            "id": str(uuid4()),
            "bulk_job_id": job_id,
            "position": i,
            "org_name": (row.get("org_name") or "").strip()[:300] or f"row {i + 1}",
            "notice_url": (row.get("notice_url") or "").strip(),
            "status": "pending",
        }
        for i, row in enumerate(rows)
    ]
    if row_payload:
        await supabase_rest_post("bulk_job_row", row_payload)
    return job_id


# ── Screening org (fresh, never an existing customer tenant) ──

def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")[:40] or "org"


async def create_screening_org(owner_org_id: str, org_name: str, job8: str, position: int) -> str:
    """Create a FRESH screening organization for one bulk row.

    ALWAYS creates a new org (never find-by-name) so a row whose name matches an
    existing customer tenant can never resolve to — or leak — that customer's
    org record. The namespaced `name`/`slug` also cannot collide with the
    single-assessment find-or-create lookup in either direction. The display
    name the UI shows comes from bulk_job_row.org_name, not organization.name.
    """
    org_id = str(uuid4())
    await supabase_rest_post("organization", {
        "organization_id": org_id,
        "name": f"{org_name} · screening {job8}",
        "slug": f"screen-{job8}-{position}-{_slug(org_name)}",
        "industry": "unknown",
        "size": "unknown",
        "geography": "US",
        "entity_type": "target",
        "tenant_id": f"bulk:{owner_org_id}",
    })
    return org_id


# ── Per-row worker ───────────────────────────────────────────

async def _process_row(row: dict, owner_org_id: str, job8: str) -> dict:
    """Intake + score one row. Returns {status, assessment_id, error}.

    status ∈ {'succeeded','failed','insufficient_profile'}. Never raises — a
    single bad row must never sink the batch (AC-2).
    """
    url = (row.get("notice_url") or "").strip()
    org_name = row.get("org_name") or ""
    position = row.get("position", 0)

    # A malformed URL fails THIS row alone (AC-2) with a clean message rather
    # than a confusing downstream fetch error; the batch continues.
    if not url_well_formed(url):
        return {"status": "failed", "assessment_id": None,
                "error": "Malformed notice_url — expected an http(s) URL."}

    try:
        # 1. Intake the URL (shared F01 path). Discovery mirrors create_assessment.
        fetch_url = url
        if not is_direct_policy_url(url):
            discovered = await discover_policy_url(url)
            if discovered:
                fetch_url = discovered
        extracted_text, content_hash = await extract_from_url(fetch_url)
        notice = decompose(extracted_text)
        await classify_clauses(notice)

        # No substantive content to profile → honest insufficient_profile (AC-7).
        if not notice.clauses:
            return {"status": "insufficient_profile", "assessment_id": None, "error": None}

        # 2. Fresh screening org (cross-tenant trap, AC-10).
        screen_org_id = await create_screening_org(owner_org_id, org_name, job8, position)

        # 3. Persist via the shared helper, then SCORE via the kernel (single path).
        notice_id = await persist_notice(
            screen_org_id, notice,
            source_url=fetch_url, content_hash=content_hash, intake_method="url",
        )
        out = await trigger_reassessment(notice_ids=[notice_id], triggered_by=f"bulk:{job8}")
        notices = out.get("notices") or []
        nstatus = notices[0].get("status") if notices else "failed"

        if nstatus == "scored":
            return {"status": "succeeded", "assessment_id": notice_id, "error": None}
        if nstatus == "skipped_no_clauses":
            return {"status": "insufficient_profile", "assessment_id": notice_id, "error": None}
        # A real scoring failure is surfaced honestly (not masked as unprofilable).
        err = (notices[0].get("error") if notices else "scoring failed") or "scoring failed"
        return {"status": "failed", "assessment_id": notice_id, "error": str(err)[:500]}

    except Exception as exc:  # noqa: BLE001 — honest per-row failure record
        log.warning("bulk row failed (%s): %s", org_name[:40], exc)
        return {"status": "failed", "assessment_id": None, "error": str(exc)[:500]}


async def run_bulk_job(job_id: str) -> None:
    """Background task: process each row sequentially and finalize the job."""
    await supabase_rest_patch("bulk_job", f"id=eq.{job_id}", {"status": "running"})

    r = await supabase_rest_get(
        "bulk_job_row",
        select="id,position,org_name,notice_url",
        filters=f"bulk_job_id=eq.{job_id}&order=position.asc",
        limit=MAX_ROWS,
    )
    rows = r.json() if r.status_code == 200 else []

    job_r = await supabase_rest_get("bulk_job", select="org_id", filters=f"id=eq.{job_id}", limit=1)
    owner_org_id = (job_r.json()[0]["org_id"] if job_r.status_code == 200 and job_r.json() else "")
    job8 = job_id[:8]

    completed = 0
    failed = 0
    for row in rows:
        await supabase_rest_patch("bulk_job_row", f"id=eq.{row['id']}", {"status": "running"})
        result = await _process_row(row, owner_org_id, job8)
        await supabase_rest_patch("bulk_job_row", f"id=eq.{row['id']}", {
            "status": result["status"],
            "assessment_id": result["assessment_id"],
            "error": result["error"],
        })
        if result["status"] == "succeeded":
            completed += 1
        else:
            failed += 1
        await supabase_rest_patch("bulk_job", f"id=eq.{job_id}", {
            "completed_count": completed, "failed_count": failed,
        })

    # Final status: all ok → completed; some ok + some not → partial; none → failed.
    if completed and not failed:
        final = "completed"
    elif completed:
        final = "partial"
    else:
        final = "failed"
    await supabase_rest_patch("bulk_job", f"id=eq.{job_id}", {
        "status": final, "finished_at": "now()",
    })
    log.info("bulk job %s finished: %s (%d ok, %d not)", job8, final, completed, failed)


# ── Read paths (tenant-scoped) ───────────────────────────────

async def list_jobs(owner_org_id: str) -> list[dict]:
    r = await supabase_rest_get(
        "bulk_job",
        select="id,label,status,row_count,completed_count,failed_count,created_at,finished_at",
        filters=f"org_id=eq.{owner_org_id}&order=created_at.desc",
        limit=200,
    )
    return r.json() if r.status_code == 200 else []


async def get_job(job_id: str, owner_org_id: str) -> dict | None:
    """Job + rows, tenant-scoped. None if not found / cross-org (no leak)."""
    r = await supabase_rest_get(
        "bulk_job", select="*", filters=f"id=eq.{job_id}&org_id=eq.{owner_org_id}", limit=1,
    )
    jobs = r.json() if r.status_code == 200 else []
    if not jobs:
        return None
    rr = await supabase_rest_get(
        "bulk_job_row",
        select="position,org_name,notice_url,status,assessment_id,error",
        filters=f"bulk_job_id=eq.{job_id}&order=position.asc",
        limit=MAX_ROWS,
    )
    return {**jobs[0], "rows": rr.json() if rr.status_code == 200 else []}


def _relaxation_label(relaxations) -> str:
    if not relaxations:
        return "exact cohort"
    if isinstance(relaxations, list):
        return "relaxed: " + ", ".join(str(x) for x in relaxations)[:120]
    return "relaxed"


async def _assemble_results(job_id: str, owner_org_id: str) -> list[dict] | None:
    """Build the per-succeeded-row results. None if job not visible to tenant."""
    job = await get_job(job_id, owner_org_id)
    if job is None:
        return None
    succeeded = [row for row in job["rows"] if row["status"] == "succeeded" and row["assessment_id"]]
    if not succeeded:
        return []

    nids = [row["assessment_id"] for row in succeeded]
    in_list = ",".join(f'"{n}"' for n in nids)

    # Snapshots → vci + cohort. Findings → per-domain + top findings.
    snap_r = await supabase_rest_get(
        "report_snapshot", select="notice_id,payload",
        filters=f"notice_id=in.({in_list})", limit=1000,
    )
    find_r = await supabase_rest_get(
        "risk_finding", select="notice_id,finding_type_code,domain,severity,score",
        filters=f"notice_id=in.({in_list})", limit=5000,
    )
    over_r = await supabase_rest_get(
        "derived_data_item", select="notice_id,score",
        filters=f"notice_id=in.({in_list})&object_type=eq.overall_intelligence", limit=1000,
    )
    rev_r = await supabase_rest_get(
        "assessment_review", select="assessment_id,status",
        filters=f"assessment_id=in.({in_list})", limit=1000,
    )

    def _payload(p):
        if isinstance(p, dict):
            return p
        try:
            return json.loads(p) if p else {}
        except (ValueError, TypeError):
            return {}

    snaps = {s["notice_id"]: _payload(s.get("payload")) for s in (snap_r.json() if snap_r.status_code == 200 else [])}
    overall = {o["notice_id"]: o.get("score") for o in (over_r.json() if over_r.status_code == 200 else [])}
    reviews = {v["assessment_id"]: v.get("status", "draft") for v in (rev_r.json() if rev_r.status_code == 200 else [])}

    findings_by_notice: dict[str, list[dict]] = {}
    for f in (find_r.json() if find_r.status_code == 200 else []):
        findings_by_notice.setdefault(f["notice_id"], []).append(f)

    results = []
    for row in succeeded:
        nid = row["assessment_id"]
        payload = snaps.get(nid, {})
        vci = payload.get("vci") or {}
        vci_score = vci.get("score")
        suppress = bool(vci.get("suppress")) or (
            isinstance(vci_score, (int, float)) and vci_score < SUPPRESSION_THRESHOLD
        )

        # Per-domain exposure from REAL stored findings (max finding score per
        # taxonomy domain; 0.0 where the notice flagged no exposure in it).
        fs = findings_by_notice.get(nid, [])
        dom_max: dict[str, float] = {}
        for f in fs:
            d = f.get("domain")
            if d in TAXONOMY_DOMAINS:
                dom_max[d] = max(dom_max.get(d, 0.0), float(f.get("score") or 0.0))
        domain_scores = [
            {"domain": d, "score": (None if suppress else round(dom_max.get(d, 0.0), 1))}
            for d in TAXONOMY_DOMAINS
        ]

        top_findings = sorted(
            fs,
            key=lambda f: (_SEVERITY_RANK.get((f.get("severity") or "").lower(), 0),
                           float(f.get("score") or 0.0)),
            reverse=True,
        )[:3]

        results.append({
            "org_name": row["org_name"],
            "assessment_id": nid,
            "review_status": reviews.get(nid, "draft"),
            "overall": None if suppress else overall.get(nid),
            "suppressed_reason": "low_confidence" if suppress else None,
            "domain_scores": domain_scores,
            "cohort": {
                "n": payload.get("cohort_size", 0),
                "relaxation_label": _relaxation_label(payload.get("relaxations")),
            },
            "top_findings": [
                {"code": f.get("finding_type_code"), "domain": f.get("domain"),
                 "severity": f.get("severity")}
                for f in top_findings
            ],
            "vci": vci_score,
        })
    return results


async def get_results(job_id: str, owner_org_id: str) -> dict | None:
    """Results + sector heat strip (aggregate domain means over succeeded rows)."""
    results = await _assemble_results(job_id, owner_org_id)
    if results is None:
        return None

    # Sector heat strip: mean of each domain across succeeded rows (suppressed
    # cells excluded from the mean; count shown for honesty).
    strip = []
    for i, d in enumerate(TAXONOMY_DOMAINS):
        vals = [r["domain_scores"][i]["score"] for r in results
                if r["domain_scores"][i]["score"] is not None]
        strip.append({
            "domain": d,
            "mean": round(sum(vals) / len(vals), 1) if vals else None,
            "n": len(vals),
        })
    return {"results": results, "sector_heat_strip": strip}


async def export_csv(job_id: str, owner_org_id: str) -> str | None:
    """Flattened results CSV. Suppressed cells → literal 'suppressed_low_confidence';
    first line is the SME not-expert-reviewed notice. Exposure/maturity vocab only."""
    results = await _assemble_results(job_id, owner_org_id)
    if results is None:
        return None

    buf = io.StringIO()
    w = csv.writer(buf)
    # Notice line first (single cell), then the header row, then data.
    w.writerow([EXPORT_NOTICE])
    w.writerow(["org_name", "review_status", "overall_exposure", "vci", "cohort_n"]
               + [f"domain_{d}" for d in TAXONOMY_DOMAINS]
               + ["top_finding_codes"])
    for r in results:
        overall = SUPPRESSED_CELL if r["overall"] is None else r["overall"]
        vci = SUPPRESSED_CELL if r["vci"] is None else r["vci"]
        dom_cells = [
            SUPPRESSED_CELL if c["score"] is None else c["score"]
            for c in r["domain_scores"]
        ]
        codes = "; ".join(f.get("code") or "" for f in r["top_findings"])
        w.writerow([r["org_name"], r["review_status"], overall, vci, r["cohort"]["n"]]
                   + dom_cells + [codes])
    return buf.getvalue()
