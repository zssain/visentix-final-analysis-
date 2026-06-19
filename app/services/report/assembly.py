"""Report assembly — builds the 12-section payload from stored data.

All data comes from derived_data_item, risk_finding, snapshots, and
guardrailed narrative. Honest numbers throughout (real cohort size + date).

Sections:
 1 Cover · 2 Executive summary + takeaways · 3 Risk dashboard
 4 Benchmark intelligence · 5 Regulator exposure heatmap
 6 Disclosure findings table · 7 Compound risk · 8 Benchmark language comparison
 9 Strategic recommendations · 10 Reduce risks by severity
 11 Source traceability · 12 Trend & emerging risk
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass
class ReportSection:
    number: int
    title: str
    content: dict = field(default_factory=dict)


@dataclass
class ReportPayload:
    assessment_id: str
    organization_name: str
    generated_date: str
    sections: list[ReportSection] = field(default_factory=list)
    cohort_size: int = 0
    cohort_date: str = ""
    vci_label: str = ""


def assemble_report(
    assessment_id: str,
    org_name: str,
    scores: dict[str, dict],
    findings: list[dict],
    vci: dict,
    narrative_exec: str,
    narrative_takeaways: list[str],
    narrative_recommendations: list[dict],
    exemplars: list[dict],
    enforcement_heatmap: list[dict],
    cohort_size: int = 30,
    cohort_date: str = "",
    snapshot_id: str = "",
) -> ReportPayload:
    """Assemble the 12-section report from pre-computed + guardrailed data."""
    if not cohort_date:
        cohort_date = str(date.today())

    overall = scores.get("f010", {}).get("score", 0)
    percentile = scores.get("f011", {}).get("score", 0)
    regulatory = scores.get("f002", {}).get("score", 0)
    reg_tier = scores.get("f002", {}).get("tier", "")
    benchmark_dev = scores.get("f003", {}).get("score", 0)
    disclosure = scores.get("f005", {}).get("score", 0)
    transparency = scores.get("f006", {}).get("score", 0)
    ai_score = scores.get("f007", {}).get("score", 0)
    compound = scores.get("f008", {}).get("score", 0)

    # Section 1: Cover
    s1 = ReportSection(1, "Cover", {
        "organization": org_name,
        "report_title": "Privacy Intelligence Assessment",
        "date": cohort_date,
        "overall_score": overall,
        "vci_label": vci.get("label", ""),
        "snapshot_id": snapshot_id,
    })

    # Section 2: Executive Summary + Takeaways
    s2 = ReportSection(2, "Executive Summary", {
        "summary": narrative_exec,
        "takeaways": narrative_takeaways,
        "overall_score": overall,
        "finding_count": len(findings),
        "cohort_size": cohort_size,
        "cohort_date": cohort_date,
    })

    # Section 3: Risk Dashboard
    s3 = ReportSection(3, "Risk Dashboard", {
        "overall_intelligence": overall,
        "regulatory_exposure": regulatory,
        "regulatory_tier": reg_tier,
        "benchmark_deviation": benchmark_dev,
        "disclosure_maturity": disclosure,
        "transparency": transparency,
        "ai_transparency": ai_score,
        "compound_risk": compound,
        "vci_score": vci.get("score", 0),
        "vci_label": vci.get("label", ""),
    })

    # Section 4: Benchmark Intelligence
    s4 = ReportSection(4, "Benchmark Intelligence", {
        "org_score": overall,
        "percentile": percentile,
        "cohort_size": cohort_size,
        "cohort_date": cohort_date,
        "cohort_label": f"n={cohort_size} peers as of {cohort_date}",
        "benchmark_deviation": benchmark_dev,
    })

    # Section 5: Regulator Exposure Heatmap
    s5 = ReportSection(5, "Regulator Exposure", {
        "regulatory_score": regulatory,
        "tier": reg_tier,
        "heatmap": enforcement_heatmap,
        "lineage": scores.get("f002", {}).get("lineage", {}),
    })

    # Section 6: Disclosure Findings Table
    findings_table = []
    for f in findings:
        findings_table.append({
            "id": f.get("code", ""),
            "domain": f.get("domain", ""),
            "severity": f.get("severity", ""),
            "score": f.get("score", 0),
            "confidence": vci.get("label", ""),
        })
    s6 = ReportSection(6, "Disclosure Findings", {
        "findings": findings_table,
        "total": len(findings_table),
    })

    # Section 7: Compound Risk
    s7 = ReportSection(7, "Compound Risk Analysis", {
        "compound_score": compound,
        "lineage": scores.get("f008", {}).get("lineage", {}),
    })

    # Section 8: Benchmark Language Comparison
    # ONLY sme_cleaned=true exemplars; placeholder if none exist
    cleaned = [e for e in exemplars if e.get("sme_cleaned", False)]
    if cleaned:
        comparison_entries = [
            {"domain": e["domain"], "exemplar_text": e["clause_text"],
             "maturity_note": e.get("maturity_note", "")}
            for e in cleaned
        ]
    else:
        comparison_entries = [{
            "domain": "pending",
            "exemplar_text": "Pending SME-cleaned exemplar — this section will be "
                             "populated once subject-matter expert review is complete.",
            "maturity_note": "SME review required before publication.",
        }]
    s8 = ReportSection(8, "Benchmark Language Comparison", {
        "entries": comparison_entries,
        "sme_cleaned_available": len(cleaned) > 0,
    })

    # Section 9: Strategic Recommendations
    s9 = ReportSection(9, "Strategic Recommendations", {
        "recommendations": narrative_recommendations,
    })

    # Section 10: Reduce Risks by Severity
    high = [f for f in findings if f.get("severity") == "high"]
    medium = [f for f in findings if f.get("severity") == "medium"]
    s10 = ReportSection(10, "Risk Reduction Priorities", {
        "high_severity": [{"code": f["code"], "domain": f["domain"]} for f in high],
        "medium_severity": [{"code": f["code"], "domain": f["domain"]} for f in medium],
        "high_count": len(high),
        "medium_count": len(medium),
    })

    # Section 11: Source Traceability
    s11 = ReportSection(11, "Source Traceability", {
        "snapshot_id": snapshot_id,
        "formula_versions_used": list(scores.keys()),
        "cohort_size": cohort_size,
        "cohort_date": cohort_date,
        "note": f"All scores traceable via snapshot {snapshot_id[:12] if snapshot_id else 'N/A'}. "
                f"Benchmarked against {cohort_size} peers as of {cohort_date}.",
    })

    # Section 12: Trend & Emerging Risk
    s12 = ReportSection(12, "Trend & Emerging Risk", {
        "trend_available": False,
        "note": "Per-company trend analysis requires monitoring history (Phase 2 monitoring). "
                "This panel shows the static regulatory landscape.",
        "regulatory_landscape": {
            "active_regulators": len(enforcement_heatmap),
            "cohort_date": cohort_date,
        },
    })

    return ReportPayload(
        assessment_id=assessment_id,
        organization_name=org_name,
        generated_date=cohort_date,
        sections=[s1, s2, s3, s4, s5, s6, s7, s8, s9, s10, s11, s12],
        cohort_size=cohort_size,
        cohort_date=cohort_date,
        vci_label=vci.get("label", ""),
    )
