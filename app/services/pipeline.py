"""Full assessment pipeline — intake → decompose → score → findings → snapshot.

Reuses Phase 4 scoring engine and findings logic. No duplicate scoring code.
"""

from __future__ import annotations

import json
import logging
from collections import Counter, defaultdict
from uuid import uuid4

import httpx
from dotenv import dotenv_values

from app.services.intake.decompose import DecomposedNotice
from app.services.scoring.engine import (
    load_element_checklist,
    load_jurisdiction_weights,
    get_expected_elements,
)
from app.services.scoring.formulas import (
    ScoringContext,
    compute_f002,
    compute_f003,
    compute_f005,
    compute_f006,
    compute_f007,
)
from app.services.scoring.formulas_advanced import (
    compute_f008,
    compute_f009,
    compute_f010,
    compute_f011,
    compute_f012,
    compute_f013,
    compute_f014,
)
from app.services.scoring.vci import compute_vci
from app.services.scoring.findings import FindingInput, select_findings

log = logging.getLogger(__name__)


def score_notice(
    organization_id: str,
    notice_id: str,
    notice: DecomposedNotice,
    regulators: list[dict],
    jurisdiction_weights: dict[str, float],
    f002_thresholds: dict,
    f010_weights: dict,
    peer_scores: list[dict],
    org_pgms: float,
    avg_source_reliability: float,
    finding_types: dict,
    recommendations: dict,
    f004_score: float | None = None,
) -> dict:
    """Score a decomposed notice end-to-end using Phase 4 formulas.

    Returns a dict with all scores, findings, VCI, and snapshot data.
    """
    # Build scoring context from decomposed notice.
    # decompose-v2 noise filter: presence-count dimensions, averages, and
    # findings are computed from SUBSTANTIVE clauses only (is_noise == False).
    # Noise clauses stay persisted for lineage but never inflate a count.
    clauses = [c for c in notice.clauses if not getattr(c, "is_noise", False)]

    cats = Counter(c.category for c in clauses)
    domains = set(c.category for c in clauses if c.category != "other")
    avg_amb = sum(c.ambiguity_score for c in clauses) / max(len(clauses), 1)
    avg_read = sum(c.readability_score for c in clauses) / max(len(clauses), 1)
    avg_conf = sum(c.nlp_confidence for c in clauses) / max(len(clauses), 1)

    ctx = ScoringContext(
        organization_id=organization_id,
        notice_id=notice_id,
        clause_categories=cats,
        total_clauses=len(clauses),
        avg_ambiguity=avg_amb,
        avg_readability=avg_read,
        avg_nlp_confidence=avg_conf,
        domains_present=domains,
        regulators=regulators,
        jurisdiction_weights=jurisdiction_weights,
        peer_scores=peer_scores,
        org_score=org_pgms,
        ai_clauses=cats.get("ai_automated_decisions", 0),
    )

    # Load checklist
    checklist = load_element_checklist()
    all_elements = get_expected_elements(checklist)
    ai_elements = get_expected_elements(checklist, ai_only=True)

    # F-002 through F-007
    f002 = compute_f002(ctx, f002_thresholds)
    f003 = compute_f003(ctx)
    f005 = compute_f005(ctx, all_elements)
    f006 = compute_f006(ctx)
    f007 = compute_f007(ctx, ai_elements)

    # F-008: Compound Risk
    risk_scores = {
        "regulatory": f002.score,
        "benchmark": f003.score,
        "disclosure": max(0, 100 - f005.score),
        "ai": max(0, 100 - f007.score),
    }
    ftc_rpw = next((r["rpw"] for r in regulators if r["id"] == "FTC"), {})
    f008 = compute_f008(risk_scores, ftc_rpw)

    # F-010: Overall Intelligence
    enforcement_value = f004_score if f004_score is not None else 50
    component_map = {
        "regulatory": f002.score,
        "benchmark": f003.score,
        "disclosure": max(0, 100 - f005.score),
        "enforcement": enforcement_value,
        "ai": max(0, 100 - f007.score),
        "compound": f008.score,
    }
    f010 = compute_f010(component_map, f010_weights)
    # Auditable lineage: mark when enforcement is a neutral prior
    if f004_score is None:
        f010.source_lineage["enforcement_prior"] = "neutral_50_f004_not_computed"

    # F-011: Benchmark Percentile
    f011 = compute_f011(org_pgms, peer_scores, len(peer_scores) + 1)

    # VCI
    vci = compute_vci(
        nlp_confidence=avg_conf if len(clauses) > 0 else 0.3,
        benchmark_confidence=0.4 if len(peer_scores) < 50 else 0.7,
        regulatory_confidence=0.7 if f002.score > 0 else 0.3,
        enforcement_confidence=0.5,
        source_reliability=avg_source_reliability,
    )

    # F-009, F-012–F-014
    f009 = compute_f009(f010.score, vci.score / 100)
    f012 = compute_f012(f010.score, None)
    f013 = compute_f013()
    total_findings_count = sum(1 for s in [f002, f003, f005, f006, f007] if s.score > 0)
    f014 = compute_f014(total_findings_count, max(total_findings_count, 1),
                        avg_source_reliability, avg_conf)
    # F14-001: on the fresh scoring path NO findings are human-validated yet, so the
    # validated/total ratio is 1.0 by construction — this is NOT completed human
    # validation. Label the value honestly as pre-review so no consumer/renderer
    # presents it as SME-confirmed Report Confidence. (Governed formula math is
    # unchanged; F-014 is recomputed after the SME queue clears — its lifecycle.)
    if isinstance(f014.source_lineage, dict):
        f014.source_lineage["review_stage"] = "pre_review"
        f014.source_lineage["validated_basis"] = (
            "pre_review_placeholder: validated==total because the SME queue has not "
            "cleared; recompute post-review for confirmed Report Confidence"
        )

    # Findings
    clause_ids_by_domain = defaultdict(list)
    for c in clauses:
        clause_ids_by_domain[c.category].append(c.clause_id)

    domain_scores = {}
    for domain in cats:
        if domain != "other":
            count = cats[domain]
            domain_scores[domain] = min(count * 15, 100)

    avg_amb_by_domain = defaultdict(list)
    for c in clauses:
        avg_amb_by_domain[c.category].append(c.ambiguity_score)
    avg_amb_dict = {d: sum(v)/len(v) for d, v in avg_amb_by_domain.items()}

    finding_input = FindingInput(
        organization_id=organization_id,
        notice_id=notice_id,
        clause_categories=cats,
        clause_ids_by_domain=dict(clause_ids_by_domain),
        domain_scores=domain_scores,
        avg_ambiguity_by_domain=avg_amb_dict,
        enforcement_matches=[],
        vci_score=vci.score,
        finding_types=finding_types,
        recommendations=recommendations,
    )
    findings = select_findings(finding_input)

    scores_dict = {
        "f002": {"score": f002.score, "tier": f002.tier, "lineage": f002.source_lineage},
        "f003": {"score": f003.score, "lineage": f003.source_lineage},
        "f005": {"score": f005.score, "lineage": f005.source_lineage},
        "f006": {"score": f006.score, "lineage": f006.source_lineage},
        "f007": {"score": f007.score, "lineage": f007.source_lineage},
        "f008": {"score": f008.score, "lineage": f008.source_lineage},
        "f009": {"score": f009.score, "lineage": f009.source_lineage},
        "f010": {"score": f010.score, "lineage": f010.source_lineage},
        "f011": {"score": f011.score, "lineage": f011.source_lineage},
    }
    # Include f004 when computed externally
    if f004_score is not None:
        scores_dict["f004"] = {
            "score": f004_score,
            "lineage": {"source": "live_f004", "value": f004_score},
        }

    return {
        "scores": scores_dict,
        "vci": {
            "score": vci.score,
            "label": vci.label,
            "suppress": vci.suppress,
            "components": vci.components,
        },
        "findings": [
            {
                "code": f.finding_type_code,
                "domain": f.domain,
                "severity": f.severity,
                "score": f.score,
                "clause_ids": f.triggering_clause_ids,
            }
            for f in findings
        ],
        "summary": {
            "overall_intelligence": f010.score,
            "benchmark_percentile": f011.score,
            "finding_count": len(findings),
            "vci_label": vci.label,
            "suppress": vci.suppress,
        },
    }
