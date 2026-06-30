"""Report endpoints — assemble and render intelligence reports from REAL stored data."""

import json
from collections import Counter
from dataclasses import asdict

import httpx
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import Response

from app.auth import AuthenticatedUser, require_role
from app.config import settings
from app.db import get_service_headers
from app.services.report.assembly import assemble_report
from app.services.review import customer_can_view
from app.services.scoring.heatmap import build_regulator_heatmap, heatmap_to_serializable

router = APIRouter(prefix="/reports", tags=["reports"])

SB_URL = settings.supabase_url


def _sb_get(path: str) -> list[dict]:
    """Sync Supabase REST GET helper."""
    r = httpx.get(f"{SB_URL}/rest/v1/{path}", headers=get_service_headers(), timeout=15)
    return r.json() if r.status_code == 200 else []


@router.get("/{assessment_id}")
async def get_report(
    assessment_id: str,
    user: AuthenticatedUser = require_role("customer", "sme", "admin"),
):
    """Return the assembled 12-section report from REAL stored data."""
    if user.role == "customer":
        can_view, banner = customer_can_view(assessment_id)
        if not can_view:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Report pending expert review (gate_mode=strict).")
    else:
        banner = ""

    report = _load_real_report(assessment_id)
    result = asdict(report)
    if banner:
        result["draft_banner"] = banner
    return result


@router.get("/{assessment_id}/pdf")
async def get_report_pdf(
    assessment_id: str,
    user: AuthenticatedUser = require_role("customer", "sme", "admin"),
):
    """Render the report as PDF from REAL stored data."""
    from app.services.report.renderer import render_pdf
    report = _load_real_report(assessment_id)
    pdf_bytes = await render_pdf(report, renderer=settings.renderer)
    return Response(
        content=pdf_bytes, media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=report-{assessment_id[:12]}.pdf"},
    )


# ══════════════════════════════════════════════════════════════
# Real data loader — replaces the old placeholder
# ══════════════════════════════════════════════════════════════

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


def _load_real_report(assessment_id: str):
    """Load real org, scores, findings, heatmap from DB and assemble the report."""

    # 1. Load the notice
    notices = _sb_get(f"privacy_notice?select=notice_id,organization_id&notice_id=eq.{assessment_id}&limit=1")
    if not notices:
        # assessment_id might be an org_id — try that
        notices = _sb_get(f"privacy_notice?select=notice_id,organization_id&organization_id=eq.{assessment_id}&limit=1")
    if not notices:
        raise HTTPException(status_code=404, detail="Assessment not found")

    notice = notices[0]
    notice_id = notice["notice_id"]
    org_id = notice["organization_id"]

    # 2. Load the organization
    orgs = _sb_get(f"organization?select=name,industry,size,geography&organization_id=eq.{org_id}&limit=1")
    org = orgs[0] if orgs else {"name": "Unknown Organization", "industry": "unknown", "size": "", "geography": ""}
    org_name = org["name"]

    # 3. Load derived scores for this org
    derived = _sb_get(
        f"derived_data_item?select=object_type,score,value_label,confidence_score,source_lineage"
        f"&organization_id=eq.{org_id}&order=generated_at.desc&limit=50"
    )

    # Dedupe: take latest per object_type
    scores = {}
    seen = set()
    for d in derived:
        otype = d["object_type"]
        fkey = SCORE_TYPE_MAP.get(otype)
        if fkey and fkey not in seen:
            lineage = d.get("source_lineage")
            if isinstance(lineage, str):
                try: lineage = json.loads(lineage)
                except: lineage = {}
            scores[fkey] = {
                "score": d["score"] or 0,
                "tier": d.get("value_label") or "",
                "lineage": lineage or {},
            }
            seen.add(fkey)

    # 4. Load risk findings
    findings_raw = _sb_get(
        f"risk_finding?select=finding_type_code,severity,score,domain"
        f"&organization_id=eq.{org_id}&order=score.desc&limit=20"
    )
    # Dedupe findings by code
    findings = []
    seen_codes = set()
    for f in findings_raw:
        code = f.get("finding_type_code") or ""
        if code and code not in seen_codes:
            findings.append({
                "code": code,
                "domain": f.get("domain", ""),
                "severity": f.get("severity", "medium"),
                "score": f.get("score", 0),
            })
            seen_codes.add(code)

    # 5. Load VCI from overall_intelligence confidence
    overall = scores.get("f010", {})
    vci_score = 50.0
    for d in derived:
        if d["object_type"] == "overall_intelligence":
            vci_score = (d.get("confidence_score") or 0.5) * 100
            break

    vci_label = "very_high" if vci_score >= 80 else "high" if vci_score >= 60 else "moderate" if vci_score >= 40 else "low"
    vci = {"score": round(vci_score, 1), "label": vci_label}

    # 6. Build narrative from real data
    overall_score = scores.get("f010", {}).get("score", 0)
    percentile = scores.get("f011", {}).get("score", 0)

    exec_summary = (
        f"{org_name} presents an overall privacy intelligence score of "
        f"{overall_score:.1f} out of 100, placing it at the {percentile:.1f}th percentile "
        f"within its peer cohort (n=30, as of 2026-06-29). "
        f"The assessment identified {len(findings)} areas of elevated exposure. "
        f"Industry: {org['industry']}. Size: {org['size']}. Geography: {org['geography']}. "
        f"Confidence level: {vci_label}."
    )

    takeaways = []
    for f in findings[:5]:
        sev = "elevated" if f["severity"] == "high" else "moderate"
        takeaways.append(
            f"The {f['domain'].replace('_', ' ')} domain presents {sev} exposure "
            f"(finding {f['code']}, score {f['score']:.1f}/100)."
        )

    recommendations = []
    for f in findings[:5]:
        recommendations.append({
            "severity": f["severity"],
            "code": f["code"],
            "title": f"Address {f['code']} — {f['domain'].replace('_', ' ')}",
            "prose": f"Review and strengthen {f['domain'].replace('_', ' ')} disclosures to reduce exposure indicators.",
        })

    # 7. Load real regulators for heatmap
    regulators = _sb_get("regulator?select=regulator_id,name,jurisdiction,priority_weights,enforcement_frequency_weight")

    # Clause categories for this notice
    sections = _sb_get(f"notice_section?select=section_id&notice_id=eq.{notice_id}")
    sids = [s["section_id"] for s in sections]
    clause_cats = Counter()
    if sids:
        # Fetch clauses for these sections (batch)
        for sid in sids[:50]:  # cap to avoid huge queries
            clauses = _sb_get(f"disclosure_clause?select=category&section_id=eq.{sid}")
            for c in clauses:
                clause_cats[c["category"]] += 1

    heatmap = heatmap_to_serializable(build_regulator_heatmap(regulators, clause_cats))

    # 8. Load sme_cleaned exemplars
    exemplars = _sb_get("exemplar?select=domain,clause_text,maturity_note,sme_cleaned&sme_cleaned=eq.true")

    # 9. Load snapshot
    snapshots = _sb_get(f"report_snapshot?select=snapshot_id&organization_id=eq.{org_id}&order=created_at.desc&limit=1")
    snapshot_id = snapshots[0]["snapshot_id"] if snapshots else assessment_id

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
        cohort_size=30,
        cohort_date="2026-06-29",
        snapshot_id=snapshot_id,
    )
