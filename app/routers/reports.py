"""Report endpoints — IMMUTABLE snapshot-based report delivery.

GET /reports/{id} returns the STORED snapshot payload verbatim (deterministic).
Only re-assembles if no snapshot exists (not yet scored) or if ?refresh=true
(admin/sme only) — which writes a NEW snapshot and leaves prior ones intact.

All lists sorted by stable keys before serialization.
All dates frozen into the snapshot at creation time.
LLM-smoothed prose generated ONCE at snapshot time and stored.
"""

import hashlib
import json
from collections import Counter
from dataclasses import asdict
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import Response

from app.auth import AuthenticatedUser, require_role
from app.config import settings
from app.db import get_service_headers
from app.services.report.assembly import assemble_report, ReportPayload
from app.services.review import customer_can_view
from app.services.scoring.heatmap import build_regulator_heatmap, heatmap_to_serializable

router = APIRouter(prefix="/reports", tags=["reports"])

# PDF render is CPU+memory heavy (WeasyPrint). Serialize renders (semaphore=1) so
# concurrent exports can't exhaust a small VM's RAM; on contention fail fast with
# an honest "being prepared" 503 rather than piling up and OOMing. Combined with
# render_pdf running WeasyPrint in a worker thread, the event loop (and /health)
# stays responsive. UPGRADE TRIGGER: if these 503s recur with >1 concurrent user,
# resize the VM to 8 GB (see LAUNCH-READINESS-v2.md).
import asyncio
_PDF_RENDER_SEM = asyncio.Semaphore(1)

SB_URL = settings.supabase_url

# object_type → score key mapping
SCORE_TYPE_MAP = {
    "regulatory_exposure": "f002",
    "benchmark_deviation": "f003",
    "enforcement_correlation": "f004",
    "disclosure_maturity": "f005",
    "transparency": "f006",
    "ai_transparency": "f007",
    "compound_risk": "f008",
    "confidence_weighted": "f009",
    "overall_intelligence": "f010",
    "benchmark_percentile": "f011",
}

# Spec VCI bands
_VCI_BANDS = [
    (90, 100, "Very High",  "Suitable for executive presentation without caveat"),
    (75, 89,  "High",       "Suitable for standard reporting"),
    (60, 74,  "Moderate",   "Include with confidence caveat"),
    (40, 59,  "Low",        "Present with clear confidence limitations"),
    (0,  39,  "Very Low",   "Do not present as definitive; route for review"),
]

_MATURITY_BANDS = [
    (90, 100, "Leading"), (75, 89, "Mature"), (60, 74, "Developing"),
    (40, 59, "Lagging"), (0, 39, "Deficient"),
]


def _sb_get(path: str) -> list[dict]:
    r = httpx.get(f"{SB_URL}/rest/v1/{path}", headers=get_service_headers(), timeout=15)
    return r.json() if r.status_code == 200 else []


def assessment_org_id(assessment_id: str) -> str | None:
    """Resolve the organization that owns an assessment (by notice_id, then by
    a snapshot, then treating the id itself as an organization_id)."""
    rows = _sb_get(f"privacy_notice?select=organization_id&notice_id=eq.{assessment_id}&limit=1")
    if rows:
        return rows[0].get("organization_id")
    rows = _sb_get(f"report_snapshot?select=organization_id&notice_id=eq.{assessment_id}&limit=1")
    if rows:
        return rows[0].get("organization_id")
    rows = _sb_get(f"organization?select=organization_id&organization_id=eq.{assessment_id}&limit=1")
    return rows[0].get("organization_id") if rows else None


def assert_customer_owns(assessment_id: str, user) -> None:
    """F10: a customer may only reach its own organization's assessments. Raises
    403 on any cross-tenant access. No-op for sme/admin."""
    if user.role != "customer":
        return
    if not user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="No organization is associated with this account.")
    owner = assessment_org_id(assessment_id)
    # Unknown owner → treat as not-yours (never leak another org's data).
    if owner != user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Not permitted to view this assessment.")


def _vci_band(score: float) -> tuple[str, str]:
    for lo, hi, label, guidance in _VCI_BANDS:
        if lo <= score <= hi:
            return label, guidance
    return "Very Low", "Do not present as definitive; route for review"


def _maturity_band(score: float) -> str:
    for lo, hi, label in _MATURITY_BANDS:
        if lo <= score <= hi:
            return label
    return "Deficient"


def _content_hash(data: dict) -> str:
    """Deterministic SHA-256 of the report payload."""
    canonical = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


# domain_id (CR/DC/…) → legacy_slug used by the report's your-text lookup.
# Sourced from config/clause_taxonomy.json — authoritative, never invented.
_DOMAIN_ID_TO_SLUG: dict[str, str] = {}


def _domain_id_to_slug() -> dict[str, str]:
    global _DOMAIN_ID_TO_SLUG
    if not _DOMAIN_ID_TO_SLUG:
        import os
        path = os.path.join(os.path.dirname(__file__), "..", "..", "config", "clause_taxonomy.json")
        try:
            with open(os.path.abspath(path), encoding="utf-8") as fh:
                for entry in json.load(fh):
                    did = entry.get("domain_id")
                    slug = entry.get("legacy_slug")
                    # First non-"other" slug per domain wins (a domain's canonical slug).
                    if did and slug and slug != "other" and did not in _DOMAIN_ID_TO_SLUG:
                        _DOMAIN_ID_TO_SLUG[did] = slug
        except Exception:
            pass
    return _DOMAIN_ID_TO_SLUG


def _load_exemplar_clauses() -> list[dict]:
    """M-03: approved `disclosure_clause` exemplars, mapped to the assembly
    exemplar shape ({domain: legacy_slug, clause_text, maturity_note, sme_cleaned}).

    One exemplar per domain (first approved). Clauses with no mappable domain
    are skipped — the section renders honest absence for those domains.
    """
    rows = _sb_get(
        "disclosure_clause?select=domain_id,normalized_text,raw_text,exemplar_status"
        "&is_exemplar=eq.true&exemplar_status=eq.approved"
    )
    slug_map = _domain_id_to_slug()
    out: list[dict] = []
    seen: set[str] = set()
    for r in rows:
        did = r.get("domain_id")
        slug = slug_map.get(did or "")
        if not slug or slug in seen:
            continue
        text = (r.get("normalized_text") or r.get("raw_text") or "").strip()
        if not text:
            continue
        out.append({
            "domain": slug,
            "clause_text": text,
            "maturity_note": "",
            "sme_cleaned": True,  # exemplar_status=approved → de-id-passed, SME-gated
        })
        seen.add(slug)
    return out


# ── Endpoints ────────────────────────────────────────────────

@router.get("/{assessment_id}")
async def get_report(
    assessment_id: str,
    refresh: Optional[bool] = Query(None),
    user: AuthenticatedUser = require_role("customer", "sme", "admin"),
):
    """Return the report. Snapshot-first (deterministic); ?refresh=true for new version."""
    if user.role == "customer":
        # F10: verify org ownership BEFORE the gate check — never leak another
        # org's report even when gate mode would otherwise allow viewing.
        assert_customer_owns(assessment_id, user)
        can_view, banner = customer_can_view(assessment_id)
        if not can_view:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Report pending expert review (gate_mode=strict).",
            )
    else:
        banner = ""

    # Try stored snapshot first (deterministic)
    if not refresh:
        stored = _load_stored_report(assessment_id)
        if stored:
            if banner:
                stored["draft_banner"] = banner
            return stored

    # No snapshot OR refresh requested (admin/sme only for refresh)
    if refresh and user.role not in ("sme", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only SME/admin can refresh a report.",
        )

    # Assemble from live data
    report = _assemble_from_live(assessment_id)
    result = asdict(report)

    # Store as new immutable snapshot
    _store_snapshot(assessment_id, result)

    if banner:
        result["draft_banner"] = banner
    return result


@router.get("/{assessment_id}/pdf")
async def get_report_pdf(
    assessment_id: str,
    user: AuthenticatedUser = require_role("customer", "sme", "admin"),
):
    """Render the report as PDF. Uses stored snapshot for determinism."""
    from app.services.report.renderer import render_pdf

    # F10: a customer may only export its own organization's report.
    assert_customer_owns(assessment_id, user)

    # Try snapshot first
    stored = _load_stored_report(assessment_id)
    if stored:
        # Reconstruct ReportPayload from stored dict
        from app.services.report.assembly import ReportSection
        sections = [
            ReportSection(number=s["number"], title=s["title"], content=s.get("content", {}))
            for s in stored.get("sections", [])
        ]
        report = ReportPayload(
            assessment_id=stored.get("assessment_id", assessment_id),
            organization_name=stored.get("organization_name", ""),
            generated_date=stored.get("generated_date", ""),
            sections=sections,
            cohort_size=stored.get("cohort_size", 0),
            cohort_date=stored.get("cohort_date", ""),
            vci_label=stored.get("vci_label", ""),
        )
    else:
        report = _assemble_from_live(assessment_id)

    # Fail fast on contention (another render in flight) — honest, retryable.
    if _PDF_RENDER_SEM.locked():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The report is being prepared. Please retry in a moment.",
            headers={"Retry-After": "3"},
        )
    async with _PDF_RENDER_SEM:
        pdf_bytes = await render_pdf(report, renderer=settings.renderer)
    return Response(
        content=pdf_bytes, media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=report-{assessment_id[:12]}.pdf"},
    )


# ── Snapshot storage ─────────────────────────────────────────

def _load_stored_report(assessment_id: str) -> dict | None:
    """Load the latest rendered_report from report_snapshot. Returns None if not found."""
    snapshots = _sb_get(
        f"report_snapshot?select=snapshot_id,rendered_report,content_hash,"
        f"report_version,created_at"
        f"&notice_id=eq.{assessment_id}"
        f"&order=created_at.desc&limit=1"
    )
    if not snapshots:
        snapshots = _sb_get(
            f"report_snapshot?select=snapshot_id,rendered_report,content_hash,"
            f"report_version,created_at"
            f"&organization_id=eq.{assessment_id}"
            f"&order=created_at.desc&limit=1"
        )

    if not snapshots:
        return None

    snap = snapshots[0]
    rendered = snap.get("rendered_report")
    if not rendered:
        return None

    if isinstance(rendered, str):
        try:
            rendered = json.loads(rendered)
        except Exception:
            return None

    # Inject snapshot metadata into the report
    rendered["_snapshot_id"] = snap.get("snapshot_id", "")
    rendered["_report_version"] = snap.get("report_version", 1)
    rendered["_content_hash"] = snap.get("content_hash", "")
    rendered["_generated_at"] = snap.get("created_at", "")

    return rendered


def _store_snapshot(assessment_id: str, report_dict: dict) -> str:
    """Store a new immutable snapshot. Returns the snapshot_id."""
    from uuid import uuid4

    snapshot_id = str(uuid4())
    ch = _content_hash(report_dict)

    # Determine report_version (max existing + 1)
    existing = _sb_get(
        f"report_snapshot?select=report_version"
        f"&notice_id=eq.{assessment_id}"
        f"&order=report_version.desc&limit=1"
    )
    version = (existing[0]["report_version"] + 1) if existing and existing[0].get("report_version") else 1

    # Add version metadata to the report
    report_dict["_snapshot_id"] = snapshot_id
    report_dict["_report_version"] = version
    report_dict["_content_hash"] = ch

    # Resolve org_id
    notices = _sb_get(f"privacy_notice?select=organization_id&notice_id=eq.{assessment_id}&limit=1")
    org_id = notices[0]["organization_id"] if notices else ""

    payload = {
        "snapshot_id": snapshot_id,
        "organization_id": org_id,
        "notice_id": assessment_id,
        "rendered_report": json.dumps(report_dict, sort_keys=True, default=str),
        "content_hash": ch,
        "report_version": version,
        "payload": json.dumps({
            "cohort_size": report_dict.get("cohort_size", 0),
            "cohort_date": report_dict.get("cohort_date", ""),
        }),
        "formula_version_set": json.dumps([]),
        "scoring_model_version": settings.scoring_model_version,
        "glossary_version": "glossary-v1",
        "template_version": "template-v1",
    }

    headers = {**get_service_headers(), "Content-Type": "application/json", "Prefer": "return=minimal"}
    httpx.post(f"{SB_URL}/rest/v1/report_snapshot", headers=headers, json=payload, timeout=15)

    return snapshot_id


# ── Live assembly (only when no snapshot exists) ─────────────

def _extract_scores(derived_rows: list[dict]) -> tuple[dict, float | None]:
    scores: dict[str, dict] = {}
    seen: set[str] = set()
    vci_confidence: float | None = None

    for d in derived_rows:
        otype = d.get("object_type", "")
        fkey = SCORE_TYPE_MAP.get(otype)
        if not fkey or fkey in seen:
            continue

        lineage = d.get("source_lineage")
        if isinstance(lineage, str):
            try:
                lineage = json.loads(lineage)
            except Exception:
                lineage = {}

        score_val = d.get("score") or d.get("value") or 0
        tier = d.get("value_label") or ""
        band = _maturity_band(score_val) if fkey in ("f010", "f005") else ""

        scores[fkey] = {
            "score": score_val,
            "tier": tier,
            "band": band,
            "lineage": lineage or {},
        }
        seen.add(fkey)

        if otype == "overall_intelligence":
            vci_confidence = d.get("confidence_score")

    return scores, vci_confidence


def _assemble_from_live(assessment_id: str) -> ReportPayload:
    """Assemble report from live DB data. Used when no snapshot exists."""

    notices = _sb_get(
        f"privacy_notice?select=notice_id,organization_id"
        f"&notice_id=eq.{assessment_id}&limit=1"
    )
    if not notices:
        notices = _sb_get(
            f"privacy_notice?select=notice_id,organization_id"
            f"&organization_id=eq.{assessment_id}"
            f"&order=retrieval_date.desc&limit=1"
        )
    if not notices:
        raise HTTPException(status_code=404, detail="Assessment not found")

    notice = notices[0]
    notice_id = notice["notice_id"]
    org_id = notice["organization_id"]

    orgs = _sb_get(f"organization?select=name,industry,size,geography&organization_id=eq.{org_id}&limit=1")
    org = orgs[0] if orgs else {"name": "Unknown Organization", "industry": "unknown", "size": "", "geography": ""}
    org_name = org["name"]

    # Scores
    derived = _sb_get(
        f"derived_data_item?select=object_type,score,value,value_label,"
        f"confidence_score,source_lineage"
        f"&notice_id=eq.{notice_id}&order=generated_at.desc&limit=50"
    )
    if not derived:
        derived = _sb_get(
            f"derived_data_item?select=object_type,score,value,value_label,"
            f"confidence_score,source_lineage"
            f"&organization_id=eq.{org_id}&order=generated_at.desc&limit=50"
        )

    scores, vci_confidence = _extract_scores(derived)

    # Findings — sorted by code for determinism
    findings_raw = _sb_get(
        f"risk_finding?select=finding_type_code,severity,score,domain"
        f"&notice_id=eq.{notice_id}&order=finding_type_code.asc&limit=20"
    )
    if not findings_raw:
        findings_raw = _sb_get(
            f"risk_finding?select=finding_type_code,severity,score,domain"
            f"&organization_id=eq.{org_id}&order=finding_type_code.asc&limit=20"
        )

    findings: list[dict] = []
    seen_codes: set[str] = set()
    for f in sorted(findings_raw, key=lambda x: x.get("finding_type_code", "")):
        code = f.get("finding_type_code") or ""
        if code and code not in seen_codes:
            findings.append({
                "code": code,
                "domain": f.get("domain", ""),
                "severity": f.get("severity", "medium"),
                "score": f.get("score", 0),
            })
            seen_codes.add(code)

    # VCI
    if vci_confidence is not None:
        vci_score = vci_confidence * 100
    else:
        vci_score = 25.0

    vci_label, vci_guidance = _vci_band(vci_score)
    vci = {"score": round(vci_score, 1), "label": vci_label, "guidance": vci_guidance}

    # Cohort from existing snapshot metadata
    snap_rows = _sb_get(
        f"report_snapshot?select=snapshot_id,payload,created_at,benchmark_population_version"
        f"&notice_id=eq.{notice_id}&order=created_at.desc&limit=1"
    )
    if snap_rows:
        sp = snap_rows[0]
        snap_payload = sp.get("payload", {})
        if isinstance(snap_payload, str):
            try: snap_payload = json.loads(snap_payload)
            except: snap_payload = {}
        cohort_size = snap_payload.get("cohort_size", 0)
        cohort_date = (sp.get("created_at") or "")[:10]
        snapshot_id = sp["snapshot_id"]
    else:
        cohort_size = 0
        cohort_date = ""
        snapshot_id = ""

    # Narrative — frozen at assembly time
    overall_score = scores.get("f010", {}).get("score", 0)
    overall_band = _maturity_band(overall_score) if overall_score > 0 else ""
    percentile = scores.get("f011", {}).get("score", 0)

    if scores:
        cohort_desc = f"n={cohort_size} peers" if cohort_size > 0 else "cohort not yet constructed"
        exec_summary = (
            f"{org_name} presents an overall privacy intelligence score of "
            f"{overall_score:.1f} out of 100"
            f"{f' ({overall_band})' if overall_band else ''}"
            f", placing it at the {percentile:.1f}th percentile "
            f"within its peer cohort ({cohort_desc}"
            f"{f', as of {cohort_date}' if cohort_date else ''}). "
            f"The assessment identified {len(findings)} areas of elevated exposure. "
            f"Confidence level: {vci_label}."
        )
    else:
        exec_summary = (
            f"Scoring for {org_name} has not yet completed. "
            f"Clause decomposition is available; scores will appear once the scoring pipeline runs."
        )

    takeaways = []
    for f in sorted(findings[:5], key=lambda x: x["code"]):
        sev = "elevated" if f["severity"] == "high" else "moderate"
        takeaways.append(
            f"The {f['domain'].replace('_', ' ')} domain presents {sev} exposure "
            f"(finding {f['code']}, score {f['score']:.1f}/100)."
        )

    # Load real recommendations from recommendation_library
    rec_lib = _sb_get("recommendation_library?select=finding_type_code,title,body_template,severity_bucket")
    rec_map = {r["finding_type_code"]: r for r in rec_lib}

    recommendations = []
    for f in sorted(findings[:5], key=lambda x: x["code"]):
        rec = rec_map.get(f["code"])
        if rec:
            recommendations.append({
                "severity": f["severity"],
                "code": f["code"],
                "title": rec["title"],
                "prose": rec["body_template"],
            })
        else:
            recommendations.append({
                "severity": f["severity"],
                "code": f["code"],
                "title": f"Address {f['code']} — {f['domain'].replace('_', ' ')}",
                "prose": f"Review and strengthen {f['domain'].replace('_', ' ')} disclosures to reduce exposure indicators.",
            })

    # Heatmap
    regulators = _sb_get("regulator?select=regulator_id,name,jurisdiction,priority_weights,enforcement_frequency_weight")
    sections = _sb_get(f"notice_section?select=section_id&notice_id=eq.{notice_id}")
    sids = [s["section_id"] for s in sections]
    clause_cats: Counter = Counter()
    for i in range(0, len(sids), 40):
        chunk = sids[i:i + 40]
        id_list = ",".join(f'"{sid}"' for sid in chunk)
        clauses = _sb_get(f"disclosure_clause?select=category,domain_id&section_id=in.({id_list})&limit=2000")
        for c in clauses:
            key = c.get("domain_id") or c.get("category") or "other"
            clause_cats[key] += 1

    heatmap = heatmap_to_serializable(build_regulator_heatmap(regulators, clause_cats))

    # M-03: best-practice exemplars come from the approved `disclosure_clause`
    # exemplars (is_exemplar=true, exemplar_status=approved — de-id-passing).
    # A domain with no approved exemplar simply renders honest absence.
    exemplars = _load_exemplar_clauses()

    # Fetch org's best clause per domain for benchmark comparison
    org_clauses_by_domain: dict[str, str] = {}
    for i in range(0, len(sids), 40):
        chunk = sids[i:i + 40]
        id_list = ",".join(f'"{sid}"' for sid in chunk)
        c_rows = _sb_get(
            f"disclosure_clause?select=category,normalized_text,nlp_confidence"
            f"&section_id=in.({id_list})&limit=2000"
        )
        for c in c_rows:
            cat = c.get("category", "other")
            if cat == "other":
                continue
            text = c.get("normalized_text", "")
            conf = c.get("nlp_confidence", 0)
            # Keep the highest-confidence clause per domain
            if cat not in org_clauses_by_domain or conf > 0.5:
                if len(text) > 30:
                    org_clauses_by_domain[cat] = text[:1000]

    return assemble_report(
        assessment_id=assessment_id,
        org_name=org_name,
        scores=scores,
        findings=findings,
        vci=vci,
        narrative_exec=exec_summary,
        narrative_takeaways=takeaways,
        narrative_recommendations=recommendations,
        exemplars=exemplars,
        enforcement_heatmap=heatmap,
        cohort_size=cohort_size,
        cohort_date=cohort_date,
        snapshot_id=snapshot_id,
        org_clauses_by_domain=org_clauses_by_domain,
    )
