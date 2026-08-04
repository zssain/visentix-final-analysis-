"""Explainability service — builds the explanation bundle for the info panel.

Pure function: no DB calls, no side effects. Takes pre-loaded data and returns
a structured dict keyed by element id explaining how each value was produced.

Formula descriptions are written by reading the actual formula implementations
in app/services/scoring/formulas.py, formulas_advanced.py, f001.py, and vci.py.
"""

from __future__ import annotations


def _guardrail_provenance(status: str) -> str:
    """Honest provenance sentence for the banned-term guardrail (GRD-002).

    Only claims the guardrail ran when a real ``"passed"`` result was recorded.
    Any other value (notably the ``"not_recorded"`` default) renders honest
    absence — never a manufactured pass. Never let a trust field's provenance
    assert a control that did not run.
    """
    if status == "passed":
        return (
            "That text passed the banned-term guardrail (it carries no "
            "legal-verdict language)."
        )
    if status == "not_recorded":
        return "Guardrail status was not recorded for this snapshot."
    # An explicit non-pass status (e.g. a recorded failure) — report it plainly.
    return f"Guardrail status for this snapshot: {status}."


# ── Plain-language formula descriptions ──────────────────────
# Each entry has a short label, a plain-language formula sentence,
# and a detailed methodology paragraph for the info panel.

FORMULA_DESCRIPTIONS: dict[str, dict[str, str]] = {
    "F-001_v1": {
        "label": "Source Reliability",
        "formula_plain": (
            "Weighted sum of four components: authority, freshness, completeness, "
            "and extraction confidence, each weighted 0.25. Produces a 0-1 score "
            "(scaled to 0-100 for display). Weights read from formula_version."
        ),
        "methodology": (
            "Each privacy notice source is scored on four axes: (1) Authority — how "
            "authoritative is the publishing domain (e.g., a .gov or official company "
            "site scores higher). (2) Freshness — how recently the notice was published "
            "or updated. (3) Completeness — whether the full notice was extracted without "
            "truncation. (4) Extraction confidence — how cleanly the text was parsed from "
            "the source format (PDF, HTML). Each component is 0-1 and weighted equally "
            "at 0.25. The formula is: SR = 0.25 x Authority + 0.25 x Freshness + "
            "0.25 x Completeness + 0.25 x Extraction Confidence."
        ),
    },
    "F-002_v1": {
        "label": "Regulatory Exposure",
        "formula_plain": (
            "Sum of (Jurisdiction Weight x Regulator Priority Weight x "
            "Disclosure Severity x Enforcement Frequency Weight) across all "
            "regulators and domains, normalized to 0-100."
        ),
        "methodology": (
            "This score quantifies how exposed the organization is to regulatory "
            "scrutiny based on what its privacy notice discloses. For each regulator "
            "in the database, the formula computes: JW (Jurisdiction Weight, from "
            "targets.yaml — e.g., US-federal = 1.0, state-level = 0.7) x RPW "
            "(Regulator Priority Weight per domain — e.g., the FTC weights 'data_sharing' "
            "at 0.9) x DS (Disclosure Severity = proportion of clauses in that domain "
            "out of total clauses) x EFW (Enforcement Frequency Weight — how actively "
            "that regulator enforces). All regulator contributions are summed and "
            "normalized: score = (raw_sum / max_possible) x 100. A higher score means "
            "the notice touches areas that regulators actively enforce. The 'regulator_contributions' "
            "in the lineage shows exactly which regulators contributed how much."
        ),
    },
    "F-003_v1": {
        "label": "Benchmark Deviation",
        "formula_plain": (
            "Computes the weighted 75th-percentile score among peers, then "
            "deviation = max(0, top_quartile - org_score). Normalized as a "
            "percentage of the top quartile score, capped at 100."
        ),
        "methodology": (
            "This measures how far this organization's privacy posture deviates from "
            "the top quartile of its peer cohort. Peers are weighted using benchmark_membership "
            "normalization (closer industry/size peers count more). The formula: "
            "(1) Sort all weighted peers by score. (2) Find the weighted 75th percentile "
            "(top quartile threshold). (3) Deviation = max(0, top_quartile_score - org_score). "
            "(4) Normalize: score = (deviation / top_quartile_score) x 100. A score of 0 "
            "means the org is at or above the top quartile. A higher score means greater "
            "deviation from top performers. Confidence is lower for small cohorts (< 50 peers)."
        ),
    },
    "F-004_v1": {
        "label": "Enforcement Correlation",
        "formula_plain": (
            "Per-match score = Cosine Similarity x Regulator Priority Weight x "
            "Enforcement Frequency Weight x 100. Aggregate = weighted mean, clamped 0-100."
        ),
        "methodology": (
            "This score measures how closely the organization's disclosure clauses match "
            "known enforcement actions. Using vector embeddings, each clause is compared "
            "against enforcement records. For matches above the similarity floor (0.30): "
            "match_score = ES (cosine similarity) x RPW (regulator priority weight for "
            "that domain) x EFW (enforcement frequency weight) x 100. The aggregate is "
            "a cosine-weighted mean of all match scores: stronger similarity matches "
            "carry more weight in the average. A high score means the organization's "
            "disclosures overlap significantly with topics that regulators have previously "
            "enforced. The lineage includes the top 20 individual clause-enforcement matches."
        ),
    },
    "F-005_v1": {
        "label": "Disclosure Maturity",
        "formula_plain": (
            "(Elements present / elements expected) x 100, minus ambiguity and "
            "missing-category penalties. Clamped 0-100."
        ),
        "methodology": (
            "Measures how complete and mature the privacy notice is relative to a "
            "checklist of expected disclosure elements. The formula: "
            "Base = (present_count / total_expected) x 100. Then two penalties: "
            "(1) Ambiguity penalty = avg_ambiguity x 150 (max ~15 points) — vague "
            "language like 'may', 'sometimes', 'certain' lowers the score. "
            "(2) Missing category penalty = 5 points per missing taxonomy domain. "
            "Final score = max(0, base - ambiguity_penalty - missing_penalty). "
            "The lineage shows exactly which domains are present vs. missing, "
            "the base score before penalties, and the penalty amounts."
        ),
    },
    "F-006_v1": {
        "label": "Transparency",
        "formula_plain": (
            "Product of Completeness x Clarity x Specificity x Explainability, "
            "each 0-1, scaled to 0-100."
        ),
        "methodology": (
            "A holistic transparency measure combining four factors: "
            "(1) Completeness = fraction of 8 taxonomy domains covered (data_sharing, "
            "tracking_cookies, consumer_rights, cross_border, sensitive_data, retention, "
            "children_teens, ai_automated_decisions). (2) Clarity = 1 - (avg_ambiguity x 10) — "
            "lower ambiguity = higher clarity. (3) Specificity = average readability score — "
            "measures how specific and concrete the language is. (4) Explainability = average "
            "NLP confidence — how well-structured the notice is for automated parsing. "
            "The product is multiplicative: score = Completeness x Clarity x Specificity x "
            "Explainability x 100. This means a weakness in any single factor pulls the "
            "entire score down significantly."
        ),
    },
    "F-007_v1": {
        "label": "AI Transparency Maturity",
        "formula_plain": (
            "(AI clauses / expected AI controls) x 100 minus AI ambiguity penalty. "
            "Clamped 0-100."
        ),
        "methodology": (
            "Measures how thoroughly the organization discloses its AI and automated "
            "decision-making practices. The formula: depth_ratio = AI_clauses / expected_controls. "
            "Base = depth_ratio x 100. Penalty = avg_ambiguity x 100 (heavier than general "
            "ambiguity because vague AI disclosures are particularly concerning). "
            "Score = max(0, base - penalty). A score of 0 means no AI clauses were found. "
            "Organizations that disclose specific AI use cases, provide human review mechanisms, "
            "and describe bias assessment practices score highest."
        ),
    },
    "F-008_v1": {
        "label": "Compound Risk",
        "formula_plain": (
            "Sum of (domain risk x correlation multiplier x regulator weight) / "
            "maximum possible, scaled to 0-100."
        ),
        "methodology": (
            "Captures how risks compound when multiple domains are simultaneously exposed. "
            "For each domain with a risk score: contribution = domain_score x CM (correlation "
            "multiplier, default 1.2) x regulator_weight. The multiplier > 1.0 reflects that "
            "having gaps in data_sharing AND retention AND ai_governance simultaneously is "
            "worse than each individually (compounding effect). Normalized by dividing by "
            "the maximum possible (all domains at 100 with max weights). A high compound "
            "risk indicates the organization has exposure across multiple correlated domains."
        ),
    },
    "F-009_v1": {
        "label": "Confidence-Weighted Score",
        "formula_plain": (
            "Derived Score x Confidence factor. Produces a conservative estimate."
        ),
        "methodology": (
            "Scales any derived score by its VCI (confidence) factor. If a score of 70 has "
            "confidence 0.5, the confidence-weighted score is 35. This provides a conservative "
            "estimate that accounts for data quality uncertainty. Used for internal ranking "
            "and comparison — ensures high-confidence scores dominate over uncertain ones."
        ),
    },
    "F-010_v1": {
        "label": "Overall Privacy Intelligence",
        "formula_plain": (
            "100 minus the weighted risk aggregate. Higher = lower exposure."
        ),
        "methodology": (
            "The top-level score combining all risk dimensions. The formula: "
            "Score = 100 - weighted_risk, where weighted_risk = sum of each component "
            "score multiplied by its dimension weight (regulatory: 0.25, benchmark: 0.20, "
            "disclosure: 0.15, transparency: 0.15, AI: 0.10, compound: 0.10, enforcement: 0.05). "
            "A score of 100 would mean zero exposure across all dimensions (theoretical maximum). "
            "A score of 0 would mean maximum exposure everywhere. The component_scores and weights "
            "in the lineage show exactly how each dimension contributed to the final number."
        ),
    },
    "F-011_v1": {
        "label": "Benchmark Percentile",
        "formula_plain": (
            "Weighted percentile rank over normalization-weighted peers. "
            "Honest cohort size and date always attached."
        ),
        "methodology": (
            "Computes where this organization ranks among its peer cohort. The formula uses "
            "weighted percentile rank: percentile = (below_weight + 0.5 x equal_weight) / "
            "total_weight x 100, where weights come from benchmark_membership normalization "
            "(industry/size/geography similarity). The 71st percentile means 71% of weighted "
            "peers scored lower. IMPORTANT: The current cohort size is explicitly attached — "
            "with fewer than 50 peers this carries a 'small_cohort' confidence label. Confidence "
            "increases with larger cohorts (< 20 = very_small, < 50 = small, < 100 = moderate, "
            "100+ = full)."
        ),
    },
    "F-012_v1": {
        "label": "Trend Delta",
        "formula_plain": (
            "(Current score - prior score) / prior score x 100. Returns 0 with "
            "'no prior history' label when no prior snapshot exists."
        ),
        "methodology": (
            "Measures the percentage change between the current assessment and the "
            "most recent prior snapshot. A positive delta means the score improved "
            "(less exposure). A negative delta means increased exposure. When no prior "
            "history exists, returns 0 with very low confidence (0.1) and an honest "
            "label: 'Trend unavailable — single point in time.' Trend analysis requires "
            "at least two snapshots to be meaningful."
        ),
    },
    "F-013_v1": {
        "label": "Alert Escalation",
        "formula_plain": (
            "Risk increase x Enforcement Correlation x Monitoring Priority x "
            "Confidence x 100, clamped 0-100."
        ),
        "methodology": (
            "Determines whether a risk change warrants an alert. Combines: risk_increase "
            "(how much the risk went up), enforcement_correlation (overlap with enforced "
            "topics), monitoring_priority (how important this domain is to monitor), "
            "and confidence. Without monitoring events, this score has very low confidence "
            "(0.2) and carries an honest caveat: 'Based on static analysis only.'"
        ),
    },
    "F-014_v1": {
        "label": "Report Confidence Index",
        "formula_plain": (
            "(Validated findings / total findings) x avg source reliability x "
            "avg NLP confidence x 100. Clamped 0-100."
        ),
        "methodology": (
            "Meta-score indicating overall confidence in the report. Higher when: "
            "more findings have been SME-validated, source documents are reliable, "
            "and NLP classification was confident. formula: (validated/total) x avg_SR x "
            "avg_NC x 100. Before SME review, the validated ratio is low, keeping this "
            "score honest about the review status."
        ),
    },
    "VCI": {
        "label": "Visentix Confidence Index",
        "formula_plain": (
            "Weighted sum of five dimension confidences: NLP 30%, Benchmark 25%, "
            "Regulatory 15%, Enforcement 15%, Source 15%. Scale: 0-100."
        ),
        "methodology": (
            "The VCI is Visentix's honesty mechanism. It tells you how much to trust "
            "each derived value. Five dimensions contribute: (1) NLP confidence (30%) — "
            "how reliably clauses were classified. (2) Benchmark confidence (25%) — "
            "how representative the peer cohort is. (3) Regulatory confidence (15%) — "
            "coverage of relevant regulators. (4) Enforcement confidence (15%) — "
            "quality of enforcement data. (5) Source reliability (15%) — quality of "
            "the notice source. Labels: very_high (80-100) = 'Suitable for executive "
            "presentation', high (60-79) = 'Suitable for standard reporting', "
            "moderate (40-59) = 'Include with confidence caveat', low (20-39) = "
            "'Route to review', very_low (0-19) = 'Suppress — insufficient data'. "
            "Scores below 40 trigger automatic suppression (do-not-present flag)."
        ),
    },
}

# Reverse map: object_type → formula_version_id
_OBJECT_TYPE_TO_FORMULA: dict[str, str] = {
    "regulatory_exposure": "F-002_v1",
    "benchmark_deviation": "F-003_v1",
    "enforcement_correlation": "F-004_v1",
    "disclosure_maturity": "F-005_v1",
    "transparency": "F-006_v1",
    "ai_transparency": "F-007_v1",
    "compound_risk": "F-008_v1",
    "confidence_weighted": "F-009_v1",
    "overall_intelligence": "F-010_v1",
    "benchmark_percentile": "F-011_v1",
}

# Score key (f002, etc.) → object_type
_SCORE_KEY_TO_OBJECT_TYPE: dict[str, str] = {
    "f002": "regulatory_exposure",
    "f003": "benchmark_deviation",
    "f004": "enforcement_correlation",
    "f005": "disclosure_maturity",
    "f006": "transparency",
    "f007": "ai_transparency",
    "f008": "compound_risk",
    "f009": "confidence_weighted",
    "f010": "overall_intelligence",
    "f011": "benchmark_percentile",
}

_SCORE_KEY_TO_LABEL: dict[str, str] = {
    "f002": "Regulatory Exposure",
    "f003": "Benchmark Deviation",
    "f004": "Enforcement Correlation",
    "f005": "Disclosure Maturity",
    "f006": "Transparency",
    "f007": "AI Transparency Maturity",
    "f008": "Compound Risk",
    "f009": "Confidence-Weighted Score",
    "f010": "Overall Privacy Intelligence",
    "f011": "Benchmark Percentile",
}

# Finding code → detailed catalog description
_FINDING_CATALOG: dict[str, dict[str, str]] = {
    "AI-004": {
        "title": "AI/Automated Decision Governance Gap",
        "description": (
            "The organization's privacy notice discloses AI or automated decision-making "
            "but the disclosure maturity is below the 70-point threshold or ambiguity "
            "exceeds 5%. This indicates potential gaps in explaining how AI affects users, "
            "what human review mechanisms exist, and how bias is assessed."
        ),
    },
    "TRK-007": {
        "title": "Tracking & Cookie Disclosure Gap",
        "description": (
            "The notice mentions tracking technologies (cookies, pixels, beacons) but "
            "disclosure maturity is below 70 or ambiguity is elevated. Users may not "
            "have clear information about what is tracked, for how long, and how to opt out."
        ),
    },
    "SH-002": {
        "title": "Data Sharing Transparency Gap",
        "description": (
            "Third-party data sharing is disclosed but without sufficient specificity. "
            "The maturity score is below 70 or ambiguity exceeds 5%, meaning the notice "
            "may lack details on sharing categories, purposes, or recipient safeguards."
        ),
    },
    "RT-003": {
        "title": "Retention Period Clarity Gap",
        "description": (
            "Data retention practices are mentioned but disclosure maturity is below 70 "
            "or language is ambiguous. Specific retention periods per data category, "
            "legal basis for retention, or deletion timelines may be missing."
        ),
    },
    "CR-001": {
        "title": "Consumer Rights Disclosure Gap",
        "description": (
            "Consumer rights (access, deletion, correction, opt-out) are referenced "
            "but the disclosure lacks specificity or completeness. The maturity score "
            "is below 70 or ambiguity is elevated."
        ),
    },
    "SEC-002": {
        "title": "Sensitive Data Handling Gap",
        "description": (
            "The notice references sensitive data categories (biometric, health, "
            "financial) but disclosure maturity is below the threshold. May lack "
            "details on consent mechanisms, safeguards, or lawful basis."
        ),
    },
    "XB-001": {
        "title": "Cross-Border Transfer Disclosure Gap",
        "description": (
            "International data transfers are mentioned but the disclosure is "
            "insufficiently detailed. May lack information about transfer mechanisms, "
            "recipient countries, or adequacy decisions."
        ),
    },
    "DC-005": {
        "title": "Thin Overall Disclosure Coverage",
        "description": (
            "The notice covers fewer than 4 out of 8 expected taxonomy domains, "
            "indicating thin overall privacy disclosure. Score = (4 - domains_present) x 25. "
            "This finding fires when large categories (sharing, retention, rights, etc.) "
            "are entirely absent from the notice."
        ),
    },
}


def build_explanation_bundle(
    scores: dict[str, dict],
    findings: list[dict],
    vci: dict,
    narrative_meta: dict | None = None,
    notice_refs: dict | None = None,
) -> dict:
    """Build the full explanation bundle. Pure function — no DB calls.

    Args:
        scores: {fkey: {score, tier, lineage, confidence_score, generated_at}}
        findings: [{code, domain, severity, score, confidence_score}]
        vci: {score, label, components}
        narrative_meta: {executive_summary: {...}, takeaways: [...]}
        notice_refs: {notice_id, clause_count, org_name, clause_categories, ...}

    Returns:
        Explanation bundle dict with scores, findings, narrative sections.
    """
    notice_refs = notice_refs or {}
    narrative_meta = narrative_meta or {}
    clause_cats = notice_refs.get("clause_categories", {})
    clause_ids = notice_refs.get("clause_ids_by_domain", {})

    # ── Scores ──
    scores_bundle = {}
    for fkey, score_data in scores.items():
        otype = _SCORE_KEY_TO_OBJECT_TYPE.get(fkey, "")
        fv_id = _OBJECT_TYPE_TO_FORMULA.get(otype, "")
        desc = FORMULA_DESCRIPTIONS.get(fv_id, {})
        lineage = score_data.get("lineage", {})
        per_score_conf = score_data.get("confidence_score", 0.5)

        # Build a human-readable interpretation of this specific score
        score_val = score_data.get("score", 0)
        tier = score_data.get("tier", "")
        interpretation = _interpret_score(fkey, score_val, tier, lineage, notice_refs)

        scores_bundle[fkey] = {
            "label": desc.get("label", _SCORE_KEY_TO_LABEL.get(fkey, fkey)),
            "score": score_val,
            "tier": tier,
            "formula_version": fv_id,
            "formula_plain": desc.get("formula_plain", ""),
            "methodology": desc.get("methodology", ""),
            "interpretation": interpretation,
            "inputs": lineage,
            "confidence": {
                "vci": vci.get("score", 0),
                "label": vci.get("label", ""),
                "guidance": _vci_guidance(vci.get("label", "")),
                "components": vci.get("components", {}),
                "per_score_confidence": round(per_score_conf, 4),
            },
            "source_refs": {
                "notice_id": notice_refs.get("notice_id", ""),
                "clause_count": notice_refs.get("clause_count", 0),
                "org_name": notice_refs.get("org_name", ""),
                "org_industry": notice_refs.get("org_industry", ""),
            },
            "generated_at": score_data.get("generated_at", ""),
        }

    # ── Findings ──
    findings_bundle = {}
    for f in findings:
        code = f.get("code", "")
        domain = f.get("domain", "")
        score_val = f.get("score", 0)
        catalog = _FINDING_CATALOG.get(code, {})
        domain_clauses = clause_ids.get(domain, [])
        domain_clause_count = clause_cats.get(domain, 0)

        findings_bundle[code] = {
            "title": catalog.get("title", f"Finding {code}"),
            "catalog_description": catalog.get("description", ""),
            "domain": domain,
            "domain_label": domain.replace("_", " ").title(),
            "severity": f.get("severity", "medium"),
            "score": score_val,
            "how_selected": (
                f"This finding was deterministically selected from the fixed finding-type "
                f"catalog (code: {code}). It triggered because the '{domain.replace('_', ' ')}' "
                f"domain had {domain_clause_count} clause(s) in the notice AND the domain "
                f"maturity score was below 70 (exposure score: {score_val:.1f}, meaning "
                f"maturity = {100 - score_val:.1f}) or clause ambiguity exceeded the 0.05 "
                f"threshold. The model did NOT invent this finding — it was selected by "
                f"deterministic rules from a pre-authored catalog."
            ),
            "triggering_clause_ids": domain_clauses,
            "triggering_clause_count": domain_clause_count,
            "formula_version": f.get("formula_version", "F-002_v1"),
            "finding_confidence": round(f.get("confidence_score", 0.5), 4),
        }

    # ── Narrative ──
    narrative_bundle = {}
    org_name = notice_refs.get("org_name", "the organization")

    # GRD-002: never default the guardrail receipt to "passed". A missing
    # result renders as honest absence ("not_recorded"); the provenance prose
    # only asserts the guardrail ran when a real "passed" result was recorded.
    exec_meta = narrative_meta.get("executive_summary", {})
    exec_guardrail = exec_meta.get("guardrail", "not_recorded")
    narrative_bundle["executive_summary"] = {
        "text": exec_meta.get("text", ""),
        "provenance": (
            f"The executive summary for {org_name} contains numbers computed entirely "
            f"by the Visentix formula engine: the overall privacy intelligence score "
            f"(F-010), the benchmark percentile (F-011), the finding count (from the "
            f"deterministic finding selector), and the cohort size/date (from benchmark_membership). "
            f"The wording was produced from a fixed template with these pre-computed values "
            f"inserted. If an LLM rephrased the text, the output was verified to contain "
            f"exactly the same numbers (no new numbers introduced, no critical numbers lost). "
            + _guardrail_provenance(exec_guardrail)
            + " The LLM did NOT invent any claim, score, or finding."
        ),
        "numbers_from": exec_meta.get("numbers_from", ["f010", "f011"]),
        "guardrail": exec_guardrail,
        "llm_used": exec_meta.get("llm_used", False),
    }

    takeaways_meta = narrative_meta.get("takeaways", [])
    narrative_bundle["takeaways"] = [
        {
            "text": t.get("text", ""),
            "provenance": (
                "This takeaway presents a finding from the deterministic finding engine. "
                "The finding code, domain, severity, and score were selected by rule-based "
                "matching against the fixed finding-type catalog (see findings section for "
                "details on how each finding was triggered). The wording was produced from "
                "a fixed template — the LLM did NOT author or invent this takeaway. "
                + _guardrail_provenance(t.get("guardrail", "not_recorded"))
            ),
            "numbers_from": t.get("numbers_from", []),
            "guardrail": t.get("guardrail", "not_recorded"),
            "llm_used": t.get("llm_used", False),
        }
        for t in takeaways_meta
    ]

    # ── Report-level metadata ──
    meta = {
        "assessment_notice_id": notice_refs.get("notice_id", ""),
        "org_name": notice_refs.get("org_name", ""),
        "org_industry": notice_refs.get("org_industry", ""),
        "org_size": notice_refs.get("org_size", ""),
        "org_geography": notice_refs.get("org_geography", ""),
        "total_clauses_analyzed": notice_refs.get("clause_count", 0),
        "clause_category_breakdown": clause_cats,
        "domains_covered": sorted(k for k, v in clause_cats.items() if v > 0 and k != "other"),
        "domains_missing": sorted(
            d for d in [
                "data_sharing", "tracking_cookies", "consumer_rights", "cross_border",
                "sensitive_data", "retention", "children_teens", "ai_automated_decisions",
            ]
            if d not in clause_cats or clause_cats.get(d, 0) == 0
        ),
        "philosophy": (
            "Visentix produces privacy INTELLIGENCE, not legal opinions. All scores come "
            "from the formula engine; all findings come from the fixed finding-type catalog; "
            "all recommendations come from the authored library. The LLM only smooths tone "
            "over pre-computed, guardrailed statements — it never invents claims, numbers, "
            "scores, or findings. Every value is traceable to its formula version, input "
            "data, and confidence level."
        ),
    }

    return {
        "scores": scores_bundle,
        "findings": findings_bundle,
        "narrative": narrative_bundle,
        "meta": meta,
    }


def _interpret_score(
    fkey: str, score: float, tier: str,
    lineage: dict, notice_refs: dict,
) -> str:
    """Generate a human-readable interpretation of a specific score value."""
    org = notice_refs.get("org_name", "This organization")
    clause_count = notice_refs.get("clause_count", 0)

    if fkey == "f002":
        n_regs = len(lineage.get("regulator_contributions", {}))
        domains = lineage.get("domains_scored", [])
        return (
            f"{org}'s regulatory exposure score is {score:.1f}/100 ({tier or 'n/a'} tier). "
            f"This was computed across {n_regs} regulator(s) and {len(domains)} domain(s) "
            f"({', '.join(d.replace('_', ' ') for d in domains[:5])}). "
            f"Based on {lineage.get('total_clauses', clause_count)} analyzed clauses."
        )
    elif fkey == "f003":
        tq = lineage.get("top_quartile_score", 0)
        dev = lineage.get("deviation", 0)
        n = lineage.get("n_peers", 0)
        return (
            f"{org} deviates {dev:.1f} points from the top quartile ({tq:.1f}) "
            f"among {n} weighted peers. "
            f"{'Small cohort — interpret with caution.' if n < 50 else ''}"
        )
    elif fkey == "f005":
        present = lineage.get("present_count", 0)
        total = lineage.get("total_expected", 0)
        amb = lineage.get("ambiguity_penalty", 0)
        missing = lineage.get("missing_domains", [])
        return (
            f"Disclosure maturity: {present}/{total} expected elements present. "
            f"Ambiguity penalty: -{amb:.1f} pts. "
            f"{'Missing domains: ' + ', '.join(d.replace('_', ' ') for d in missing) + '.' if missing else 'All expected domains covered.'}"
        )
    elif fkey == "f006":
        comp = lineage.get("completeness", 0)
        clar = lineage.get("clarity", 0)
        spec = lineage.get("specificity", 0)
        expl = lineage.get("explainability", 0)
        return (
            f"Transparency = {comp:.0%} completeness x {clar:.0%} clarity x "
            f"{spec:.0%} specificity x {expl:.0%} explainability = {score:.1f}/100. "
            f"{'Low completeness: not all taxonomy domains are covered. ' if comp < 0.5 else ''}"
            f"{'Low clarity: ambiguous language detected. ' if clar < 0.5 else ''}"
        )
    elif fkey == "f007":
        ai_clauses = lineage.get("ai_clauses", 0)
        return (
            f"AI transparency: {ai_clauses} AI-related clause(s) found. "
            f"{'No AI disclosures detected — score reflects absence of AI governance language.' if ai_clauses == 0 else ''}"
            f"Score: {score:.1f}/100."
        )
    elif fkey == "f008":
        cm = lineage.get("cm", 1.2)
        return (
            f"Compound risk across correlated domains: {score:.1f}/100. "
            f"Correlation multiplier: {cm}x. "
            f"Higher scores indicate exposure in multiple related areas simultaneously."
        )
    elif fkey == "f010":
        wr = lineage.get("weighted_risk", 0)
        components = lineage.get("component_scores", {})
        top_risk = max(components.items(), key=lambda x: x[1])[0] if components else "n/a"
        return (
            f"{org}'s overall score is {score:.1f}/100 (100 - {wr:.1f} weighted risk). "
            f"Highest risk contributor: {top_risk.replace('_', ' ')}. "
            f"{'Strong privacy posture.' if score >= 70 else 'Areas for improvement identified.' if score >= 40 else 'Significant exposure detected.'}"
        )
    elif fkey == "f011":
        cs = lineage.get("cohort_size", 0)
        cd = lineage.get("cohort_date", "")
        cl = lineage.get("cohort_label", "")
        return (
            f"{org} ranks at the {score:.1f}th percentile among {cs} peers "
            f"(as of {cd}). Cohort: {cl.replace('_', ' ')}. "
            f"{'This is a small cohort — percentile may shift as more organizations are assessed.' if cs < 50 else ''}"
        )
    else:
        return f"Score: {score:.1f}/100{' (' + tier + ')' if tier else ''}."


def _vci_guidance(label: str) -> str:
    """Map VCI label to guidance string (matches vci.py VCI_LABELS)."""
    mapping = {
        "very_high": "Suitable for executive presentation",
        "high": "Suitable for standard reporting",
        "moderate": "Include with confidence caveat",
        "low": "Route to review — do not present as definitive",
        "very_low": "Suppress — insufficient data for meaningful output",
    }
    return mapping.get(label, "")
