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



def _build_source_summary(
    *,
    findings_table: list[dict],
    scores: dict[str, dict],
    cohort_size: int,
    cohort_date: str,
    vci: dict,
    guardrail_result: dict | None,
    extraction_quality: dict | None,
    assessment_scope: dict | None,
    enforcement_heatmap: list[dict],
) -> dict:
    """Holistic statement of what the judgments rest on (F05 RPT-007).

    Per-figure lineage already answers "where did this number come from". It does
    not answer the question a third-party reader actually opens with: *which
    evidence is carrying the conclusion, and where is it thin?* This assembles
    that from values ALREADY in the snapshot.

    Hard Rule 7 discipline: every field below is counted or copied, never
    estimated. A missing input produces an explicit absence, never a default that
    reads like a measurement. Nothing here is a new claim -- if a fact is not in
    the snapshot, it does not appear.
    """
    total = len(findings_table)
    evidenced = sum(1 for f in findings_table if f.get("clause_ids") or f.get("evidence"))
    with_obligation = sum(1 for f in findings_table if f.get("obligation_refs"))
    with_enforcement = sum(1 for f in findings_table if f.get("enforcement_refs"))

    scope = assessment_scope or {}
    source_label = scope.get("source_label") or scope.get("source") or None
    captured_at = scope.get("captured_at") or scope.get("assessed_at") or None

    extraction_status = (extraction_quality or {}).get("status") or "not_recorded"
    guardrail_status = (guardrail_result or {}).get("status") or "not_recorded"
    vci_label = vci.get("label") or None
    vci_score = vci.get("score") if isinstance(vci.get("score"), (int, float)) else None

    # ── Which sources drive the key judgments ────────────────────────────────
    # One row per headline score that is actually present. `strength` describes
    # the EVIDENCE BASE, not the score: a good score on thin evidence is still
    # thin evidence, and that distinction is the whole point of this block.
    drivers: list[dict] = []

    if "f010" in scores:
        drivers.append({
            "judgment": "Overall standing",
            "rests_on": "This organization's published notice, compared against the peer cohort",
            "strength": "limited" if cohort_size == 0 else ("moderate" if cohort_size < 10 else "strong"),
            "why": (
                "No peer cohort was constructed, so the overall figure describes this notice "
                "on its own scale rather than against comparable organizations."
                if cohort_size == 0 else
                # DATA-002: no date in this string. It is meaningful content and
                # IS hashed, so a timestamp inside it would make byte-identical
                # reports hash differently across days. The as-of date lives
                # structurally in `evidence_base.cohort_date`, which the
                # canonicalizer excludes by name.
                f"Compared against {cohort_size} comparable organizations."
            ),
        })

    if total:
        drivers.append({
            "judgment": "Individual findings",
            "rests_on": "Clauses extracted from the assessed notice",
            # A majority must be evidenced to read as "moderate": 1 of 3 cited
            # clauses is a limited base, not a middling one.
            "strength": (
                "strong" if evidenced == total else
                "moderate" if evidenced * 2 >= total else
                "limited"
            ),
            "why": f"{evidenced} of {total} findings cite a specific clause from the notice.",
        })

    if "f002" in scores:
        drivers.append({
            "judgment": "Regulator exposure",
            "rests_on": "Published regulator expectations mapped to disclosure domains",
            "strength": "limited" if not enforcement_heatmap else "moderate",
            "why": (
                "No regulator baselines were available for this assessment."
                if not enforcement_heatmap else
                f"{len(enforcement_heatmap)} regulators' published expectations were in scope."
            ),
        })

    # ── Strengths and limitations of the evidence base ────────────────────────
    strengths: list[str] = []
    limitations: list[str] = []

    if evidenced == total and total:
        strengths.append("Every finding cites a specific clause from the assessed notice.")
    elif evidenced:
        limitations.append(
            f"{total - evidenced} of {total} findings are not tied to a specific clause, "
            "so they are weaker evidence than the rest."
        )

    if cohort_size >= 10:
        strengths.append(f"The peer comparison uses {cohort_size} comparable organizations.")
    elif cohort_size > 0:
        limitations.append(
            f"The peer cohort is small ({cohort_size}), so comparative figures should be read "
            "as indicative rather than settled."
        )
    else:
        limitations.append(
            "No peer cohort was constructed, so no comparative position is reported."
        )

    if with_obligation:
        strengths.append(f"{with_obligation} findings reference a citable published obligation.")
    if with_enforcement:
        strengths.append(f"{with_enforcement} findings reference recorded enforcement activity.")

    if extraction_status not in ("not_recorded", "ok", "passed"):
        limitations.append(f"Clause extraction quality was recorded as \"{extraction_status}\".")
    if extraction_status == "not_recorded":
        limitations.append("Clause extraction quality was not recorded for this assessment.")

    if not source_label:
        limitations.append("The assessed source was not recorded on this snapshot.")
    if not captured_at:
        limitations.append("The date the notice was captured was not recorded on this snapshot.")

    limitations.append(
        "This assessment reads the organization's published notice only. It does not "
        "observe internal practice, contracts, or systems, so it cannot report whether "
        "what the notice says matches what the organization does."
    )

    return {
        "drivers": drivers,
        "evidence_base": {
            "findings_total": total,
            "findings_clause_evidenced": evidenced,
            "findings_with_obligation_ref": with_obligation,
            "findings_with_enforcement_ref": with_enforcement,
            "cohort_size": cohort_size,
            "cohort_date": cohort_date,
            "regulators_in_scope": len(enforcement_heatmap),
            "extraction_status": extraction_status,
            "guardrail_status": guardrail_status,
            "confidence_label": vci_label,
            "confidence_score": vci_score,
            "source_label": source_label,
            "captured_at": captured_at,
        },
        "strengths": strengths,
        "limitations": limitations,
    }


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
    org_clauses_by_domain: dict[str, dict | str] | None = None,
    cohort_size: int = 0,
    cohort_date: str = "",
    snapshot_id: str = "",
    guardrail_result: dict | None = None,
    extraction_quality: dict | None = None,
    cohort_methodology: dict | None = None,
    assessment_scope: dict | None = None,
) -> ReportPayload:
    """Assemble the 12-section report from pre-computed + guardrailed data.

    `guardrail_result` (GRD-001) is the real outcome of running the banned-term
    guardrail over all generated prose, persisted in Section 11 lineage so the
    explainability receipt (GRD-002) reports fact, not a default.
    """
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

    extraction_quality = extraction_quality or {"status": "not_recorded"}
    cohort_methodology = cohort_methodology or {}
    assessment_scope = assessment_scope or {}
    suppress_parse_dependent = extraction_quality.get("status") in {"mismatch", "insufficient"}

    # Section 1: Cover. Assessment Scope is front matter inside the Cover so the
    # governed 12-section sequence remains stable (F05 AC-8).
    s1 = ReportSection(1, "Cover", {
        "organization": org_name,
        "report_title": "Privacy Intelligence Assessment",
        "date": cohort_date,
        "overall_score": overall,
        "vci_label": vci.get("label", ""),
        "snapshot_id": snapshot_id,
        "assessment_scope": assessment_scope,
    })

    # Section 2: Executive Summary + Takeaways
    # PHASE 6 (render): percentile / regulatory exposure+tier / overall band are
    # surfaced here READ-ONLY (already computed above) so the exec-summary KPI
    # cards read real values. No math is performed — pure exposure of scores.*.
    s2 = ReportSection(2, "Executive Summary", {
        "summary": narrative_exec,
        "takeaways": narrative_takeaways,
        "overall_score": overall,
        "overall_band": scores.get("f010", {}).get("band", ""),
        "percentile": percentile,
        "regulatory_exposure": regulatory,
        "regulatory_tier": reg_tier,
        "finding_count": len(findings),
        "cohort_size": cohort_size,
        "cohort_date": cohort_date,
    })

    # Section 3: Risk Dashboard
    s3 = ReportSection(3, "Risk Dashboard", {
        "assessment_id": assessment_id,
        "overall_intelligence": overall,
        "regulatory_exposure": regulatory,
        "regulatory_tier": reg_tier,
        "benchmark_deviation": None if suppress_parse_dependent else benchmark_dev,
        "disclosure_maturity": None if suppress_parse_dependent else disclosure,
        "transparency": None if suppress_parse_dependent else transparency,
        "ai_transparency": None if suppress_parse_dependent else ai_score,
        "compound_risk": compound,
        "vci_score": vci.get("score"),
        "vci_label": vci.get("label", ""),
        "snapshot_id": snapshot_id,
        "date": cohort_date,
        "cohort_size": cohort_size,
        "cohort_date": cohort_date,
        "extraction_quality": extraction_quality,
    })

    # Section 4: Benchmark Intelligence
    s4 = ReportSection(4, "Benchmark Intelligence", {
        # F-003 and F-011 both benchmark PGMS; never mix the F-010 headline score
        # into this chart. Missing F-003 lineage is honest absence.
        "org_score": None if suppress_parse_dependent else scores.get("f003", {}).get("lineage", {}).get("org_score"),
        "measure_label": "Governance Maturity (PGMS)",
        "percentile": None if suppress_parse_dependent else percentile,
        "cohort_size": cohort_size,
        "cohort_date": cohort_date,
        # DATA-002: `cohort_label` is DERIVED PROSE embedding the volatile "as of
        # <date>" stamp; the immutable peer count is already in `cohort_size`. It
        # is excluded from the content hash (see _CONTENT_HASH_EXCLUDE_KEYS).
        "cohort_label": f"n={cohort_size} peers as of {cohort_date}",
        "benchmark_deviation": benchmark_dev,
        # PHASE 6 (render): F-003 already computes the WEIGHTED top-quartile
        # threshold + peer count; surface them READ-ONLY so §4 can draw a real
        # "your score vs top quartile" comparison. `None` when F-003 had no peers,
        # so the renderer shows honest absence instead of a fabricated average.
        "top_quartile_score": None if suppress_parse_dependent else scores.get("f003", {}).get("lineage", {}).get("top_quartile_score"),
        "peer_n": scores.get("f003", {}).get("lineage", {}).get("n_peers"),
        "formula_ids": {"comparison": "F-003", "percentile": "F-011"},
        "methodology": cohort_methodology,
        "extraction_quality": extraction_quality,
    })

    # Section 5: Regulator Exposure Heatmap
    s5 = ReportSection(5, "Regulator Exposure", {
        "regulatory_score": regulatory,
        "tier": reg_tier,
        "heatmap": enforcement_heatmap,
        "lineage": scores.get("f002", {}).get("lineage", {}),
        # Provenance + cohort, carried like sections 2 and 3 already carry them.
        # Section 5 was the only score surface without them, so its lineage
        # drawer rendered "-" for the snapshot id and n=0 for the cohort on
        # every report — honest absence, but absence of data that existed two
        # frames up the stack. The heatmap cell panel (AC-13) gates its peer
        # comparison on the cohort, and a cohort that is always 0 makes that
        # gate untestable. `snapshot_id` and `cohort_date` are excluded from the
        # content hash by name (_CONTENT_HASH_EXCLUDE_KEYS); `cohort_size` is a
        # counted figure and hashes as content, which is correct.
        "snapshot_id": snapshot_id,
        "date": cohort_date,
        "cohort_size": cohort_size,
        "cohort_date": cohort_date,
    })

    # Section 6: Disclosure Findings Table
    findings_table = []
    for f in findings:
        findings_table.append({
            "id": f.get("code", ""),
            "domain": f.get("domain", ""),
            "severity": f.get("severity", ""),
            "score": f.get("score", 0),
            # RPT-005: per-finding confidence shows the finding's REAL stored
            # value or honest absence — never the global VCI label, which would
            # mask a missing per-finding value with a plausible one. Renderer
            # and React both map a falsy value to "Not recorded".
            "confidence": f.get("confidence"),
            "clause_ids": f.get("clause_ids", []),
            "evidence": f.get("evidence", []),
            "obligation_refs": f.get("obligation_refs", []),
            "enforcement_refs": f.get("enforcement_refs", []),
            "formula_version": f.get("formula_version"),
            "benchmark_reference": f.get("benchmark_reference"),
        })
    s6 = ReportSection(6, "Disclosure Findings", {
        "assessment_id": assessment_id,
        "findings": findings_table,
        "total": len(findings_table),
    })

    # Section 7: Compound Risk
    s7 = ReportSection(7, "Compound Risk Analysis", {
        "compound_score": compound,
        "lineage": scores.get("f008", {}).get("lineage", {}),
    })

    # Section 8: Benchmark Language Comparison
    org_clauses = org_clauses_by_domain or {}
    cleaned = {e["domain"]: e for e in exemplars if e.get("sme_cleaned", False)}
    comparison_entries = []
    for domain in sorted(org_clauses):
        org_clause = org_clauses[domain]
        your_text = org_clause.get("text", "") if isinstance(org_clause, dict) else org_clause
        exemplar = cleaned.get(domain)
        comparison_entries.append({
            "domain": domain,
            "your_text": your_text,
            "your_clause_id": org_clause.get("clause_id") if isinstance(org_clause, dict) else None,
            "exemplar_text": exemplar.get("clause_text", "") if exemplar else "",
            "exemplar_clause_id": exemplar.get("clause_id") if exemplar else None,
            "similarity": exemplar.get("similarity") if exemplar else None,
            "maturity_note": exemplar.get("maturity_note", "") if exemplar else "No comparable approved peer language is available for this domain.",
        })
    s8 = ReportSection(8, "Benchmark Language Comparison", {
        "entries": comparison_entries,
        "sme_cleaned_available": any(entry.get("exemplar_text") for entry in comparison_entries),
        "org_language_available": bool(comparison_entries),
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
        # GRD-001/GRD-002: the REAL guardrail outcome for this snapshot's prose.
        # "not_recorded" (never a manufactured "passed") if the build didn't run it.
        "guardrail": guardrail_result or {"status": "not_recorded"},
        "template_tokens": (guardrail_result or {}).get("template_tokens", {"status": "not_recorded"}),
        "extraction_quality": extraction_quality,
        "finding_evidence": findings_table,
        # RPT-007 source summary — which evidence carries the conclusions, and
        # where the base is thin. Assembled here so it FREEZES into the snapshot
        # (DIR-008: presentation never recalculates).
        "source_summary": _build_source_summary(
            findings_table=findings_table,
            scores=scores,
            cohort_size=cohort_size,
            cohort_date=cohort_date,
            vci=vci,
            guardrail_result=guardrail_result,
            extraction_quality=extraction_quality,
            assessment_scope=assessment_scope,
            enforcement_heatmap=enforcement_heatmap,
        ),
        # DATA-002: this `note` is DERIVED PROSE that re-states volatile data
        # (the snapshot id + "as of <date>") already carried structurally by the
        # `snapshot_id`, `cohort_size` and `cohort_date` keys. It is excluded from
        # the content hash (see _CONTENT_HASH_EXCLUDE_KEYS) so it stays human-
        # readable without making the tamper-evidence hash drift across snapshots.
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
