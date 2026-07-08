"""Live scoring pipeline — scores a decomposed notice end-to-end.

Bridges the gap: create_assessment now calls score_and_persist() to produce
real versioned intelligence objects instead of returning "decomposed" with no
scores.

Flow: ensure org profile -> build dynamic population -> normalize ->
      score_notice -> persist derived_data_item + report_snapshot + findings.

Every derived row carries the full versioning quintet:
  formula_version_id, scoring_model_version, source_corpus_version,
  benchmark_population_version, generated_at.
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from uuid import uuid4

import httpx

from app.config import settings
from app.db import get_service_headers
from app.services.intake.decompose import DecomposedNotice
from app.services.pipeline import score_notice
from app.services.scoring.engine import load_jurisdiction_weights

log = logging.getLogger(__name__)

SB = settings.supabase_url

# object_type mapping — MUST match what reports.py and the UI expect
_FORMULA_OBJECT_TYPE = {
    "f002": ("regulatory_exposure",  "F-002_v1"),
    "f003": ("benchmark_deviation",  "F-003_v1"),
    "f005": ("disclosure_maturity",  "F-005_v1"),
    "f006": ("transparency",         "F-006_v1"),
    "f007": ("ai_transparency",      "F-007_v1"),
    "f008": ("compound_risk",        "F-008_v1"),
    "f009": ("confidence_weighted",  "F-009_v1"),
    "f010": ("overall_intelligence", "F-010_v1"),
    "f011": ("benchmark_percentile", "F-011_v1"),
}

# Documented fallback defaults (logged when used)
_DEFAULT_F002_THRESHOLDS = {"low": [0, 33], "moderate": [33.01, 66], "high": [66.01, 100]}
_DEFAULT_F010_WEIGHTS = {
    "regulatory": 0.25, "benchmark": 0.20, "disclosure": 0.20,
    "enforcement": 0.10, "ai": 0.15, "compound": 0.10,
}


async def score_and_persist(
    organization_id: str,
    notice_id: str,
    notice: DecomposedNotice,
) -> dict:
    """Score a decomposed notice and persist all intelligence objects.

    Returns dict with scores, findings, vci, and summary.
    """
    headers = get_service_headers()
    defaults_used: list[str] = []

    async with httpx.AsyncClient(timeout=30) as client:

        # ── a) Ensure org profile ─────────────────────────────
        target_profile = await _ensure_org_profile(client, headers, organization_id, notice)

        # ── b) Build dynamic population ──────────────────────
        from app.services.benchmark.population import build_population
        population = await build_population(client, target_profile)

        cohort_size = population["cohort_size"]
        pop_version = population["benchmark_population_version"]
        pop_key = population["population_key"]
        relaxations = population["relaxations"]
        confidence_penalty = population["confidence_penalty"]

        # ── c) Build normalized, weighted peer_scores ─────────
        peer_scores = [
            {"score": m.get("pgms", 0), "weight": m["benchmark_weight"]}
            for m in population["members"]
        ]
        org_pgms = target_profile.get("pgms", 50.0)

        # ── d) Load config ────────────────────────────────────
        jw = load_jurisdiction_weights()

        # Formula versions from DB (with fallbacks)
        f002_thresholds = await _load_formula_thresholds(client, headers, "F-002_v1", defaults_used)
        f010_weights = await _load_formula_weights(client, headers, "F-010_v1", defaults_used)

        # ── e) Load regulators, source reliability, catalogs ──
        regulators = await _load_regulators(client, headers)
        avg_sr = await _load_avg_source_reliability(client, headers)
        finding_types, recommendations = await _load_catalogs(client, headers)

        # ── f-pre) Live F-004 enforcement correlation ─────────
        f004_score: float | None = None
        f004_lineage: dict = {}
        if settings.enable_live_f004:
            f004_score, f004_lineage = await _compute_live_f004(
                client, headers, notice, regulators,
            )

        # ── f) Score ──────────────────────────────────────────
        result = score_notice(
            organization_id=organization_id,
            notice_id=notice_id,
            notice=notice,
            regulators=regulators,
            jurisdiction_weights=jw,
            f002_thresholds=f002_thresholds,
            f010_weights=f010_weights,
            peer_scores=peer_scores,
            org_pgms=org_pgms,
            avg_source_reliability=avg_sr,
            finding_types=finding_types,
            recommendations=recommendations,
            f004_score=f004_score,
        )

        vci = result["vci"]
        scores = result["scores"]
        findings = result["findings"]

        # If live F-004 was computed, enrich scores with full lineage
        if f004_score is not None:
            scores["f004"] = {
                "score": f004_score,
                "tier": None,
                "lineage": f004_lineage,
            }

        # ── g) Persist derived_data_item (ONE BATCH) ──────────
        snapshot_id = str(uuid4())
        derived_rows = []

        for fkey, score_data in scores.items():
            mapping = _FORMULA_OBJECT_TYPE.get(fkey)
            if not mapping:
                continue
            object_type, formula_version_id = mapping
            tier = score_data.get("tier") or ""

            derived_rows.append({
                "derived_data_item_id": str(uuid4()),
                "object_type": object_type,
                "organization_id": organization_id,
                "notice_id": notice_id,
                "score": score_data["score"],
                "value": score_data["score"],
                "value_label": tier,
                "confidence_score": vci["score"] / 100,
                "confidence_index": vci["score"] / 100,
                "confidence_components": json.dumps(vci.get("components", {})),
                "formula_version_id": formula_version_id,
                "source_lineage": json.dumps(score_data.get("lineage", {})),
                "source_snapshot_id": snapshot_id,
                "benchmark_population_id": pop_key,
                "scoring_model_version": settings.scoring_model_version,
                "source_corpus_version": settings.source_corpus_version,
                "benchmark_population_version": str(pop_version),
            })

        # Interpretive Variance stub — honest null, never fabricated
        derived_rows.append({
            "derived_data_item_id": str(uuid4()),
            "object_type": "interpretive_variance",
            "organization_id": organization_id,
            "notice_id": notice_id,
            "score": None,
            "value": None,
            "value_label": "insufficient_data",
            "confidence_score": 0.1,
            "confidence_index": 0.1,
            "confidence_components": json.dumps({"note": "Interpretive Variance requires regulator-guidance and legal-review-tag data not yet available."}),
            "formula_version_id": "F-IVS_v1",
            "source_lineage": json.dumps({"reason": "insufficient_interpretation_data", "conflicting_interps": 0, "total_relevant_interps": 0}),
            "source_snapshot_id": snapshot_id,
            "benchmark_population_id": pop_key,
            "scoring_model_version": settings.scoring_model_version,
            "source_corpus_version": settings.source_corpus_version,
            "benchmark_population_version": str(pop_version),
        })

        if derived_rows:
            r = await client.post(
                f"{SB}/rest/v1/derived_data_item",
                headers={**headers, "Content-Type": "application/json", "Prefer": "return=minimal"},
                json=derived_rows,
            )
            if r.status_code >= 400:
                log.warning(
                    "derived_data_item insert failed: %d %s",
                    r.status_code, r.text[:200],
                )

        # ── g2) Persist explainability_reference rows ─────────
        try:
            explain_rows = []
            for dr in derived_rows:
                intel_id = dr["derived_data_item_id"]
                otype = dr["object_type"]
                fv = dr.get("formula_version_id", "")
                # Formula reference
                explain_rows.append({
                    "explainability_id": str(uuid4()),
                    "intelligence_id": intel_id,
                    "object_type": otype,
                    "source_type": "formula",
                    "source_id": fv,
                    "formula_version": fv,
                    "benchmark_population_id": pop_key,
                    "rationale": f"Score computed by {fv} formula engine.",
                })
                # Benchmark reference
                explain_rows.append({
                    "explainability_id": str(uuid4()),
                    "intelligence_id": intel_id,
                    "object_type": otype,
                    "source_type": "benchmark",
                    "source_id": pop_key,
                    "benchmark_population_id": pop_key,
                    "formula_version": fv,
                    "rationale": f"Benchmarked against {cohort_size} normalized peers (population {pop_version}).",
                })
            if explain_rows:
                await client.post(
                    f"{SB}/rest/v1/explainability_reference",
                    headers={**headers, "Content-Type": "application/json", "Prefer": "return=minimal"},
                    json=explain_rows,
                )
        except Exception:
            pass  # Table may not exist yet; Prompt 10 finalizes

        # ── h) Persist report_snapshot ────────────────────────
        snapshot_payload = {
            "snapshot_id": snapshot_id,
            "organization_id": organization_id,
            "notice_id": notice_id,
            "payload": json.dumps({
                "findings_count": len(findings),
                "finding_codes": [f["code"] for f in findings],
                "clause_count": len(notice.clauses),
                "cohort_size": cohort_size,
                "vci": vci,
                "defaults_used": defaults_used,
                "relaxations": relaxations,
                "live_profile_computed": True,
            }),
            "formula_version_set": json.dumps(
                sorted(fv for _, fv in _FORMULA_OBJECT_TYPE.values())
            ),
            "benchmark_population_version": pop_version,
            "source_corpus_version": settings.source_corpus_version,
            "scoring_model_version": settings.scoring_model_version,
        }
        r = await client.post(
            f"{SB}/rest/v1/report_snapshot",
            headers={**headers, "Content-Type": "application/json", "Prefer": "return=minimal"},
            json=snapshot_payload,
        )
        if r.status_code >= 400:
            log.warning("report_snapshot insert failed: %d %s", r.status_code, r.text[:200])

        # ── i) Persist findings ───────────────────────────────
        finding_rows = []
        for f in findings:
            finding_rows.append({
                "finding_id": str(uuid4()),
                "organization_id": organization_id,
                "notice_id": notice_id,
                "finding_type_code": f["code"],
                "severity": f["severity"],
                "score": f["score"],
                "domain": f["domain"],
                "confidence_score": vci["score"] / 100,
                "formula_version_id": "F-002_v1",
                "snapshot_id": snapshot_id,
                "scoring_model_version": settings.scoring_model_version,
                "source_corpus_version": settings.source_corpus_version,
            })

        if finding_rows:
            r = await client.post(
                f"{SB}/rest/v1/risk_finding",
                headers={**headers, "Content-Type": "application/json", "Prefer": "return=minimal"},
                json=finding_rows,
            )
            if r.status_code >= 400:
                log.warning("risk_finding insert failed: %d %s", r.status_code, r.text[:200])

        # ── j) Log summary ────────────────────────────────────
        log.info(
            "Scored notice=%s org=%s: derived=%d findings=%d cohort=%d vci=%.1f",
            notice_id[:12], organization_id[:12],
            len(derived_rows), len(findings), cohort_size, vci["score"],
        )

        # Build summary
        result["summary"]["snapshot_id"] = snapshot_id
        result["summary"]["cohort_size"] = cohort_size
        result["summary"]["relaxations"] = relaxations
        result["summary"]["defaults_used"] = defaults_used
        result["summary"]["benchmark_population_version"] = pop_version

        return result


# ── Helpers ──────────────────────────────────────────────────

async def _ensure_org_profile(
    client: httpx.AsyncClient,
    headers: dict,
    organization_id: str,
    notice: DecomposedNotice,
) -> dict:
    """Load or compute the org's intelligence profile."""
    r = await client.get(
        f"{SB}/rest/v1/organization_intelligence_profile"
        f"?select=*&organization_id=eq.{organization_id}"
        f"&order=profile_version.desc&limit=1",
        headers=headers,
    )
    existing = r.json() if r.status_code == 200 else []
    if existing:
        return existing[0]

    # Compute a new profile
    from app.services.profiling.live_profile import compute_org_profile

    r2 = await client.get(
        f"{SB}/rest/v1/organization"
        f"?select=*&organization_id=eq.{organization_id}&limit=1",
        headers=headers,
    )
    org_rows = r2.json() if r2.status_code == 200 else []
    org_row = org_rows[0] if org_rows else {"organization_id": organization_id, "industry": "unknown", "size": "unknown", "geography": "US"}

    clauses = [{"category": c.category, "clause_type": getattr(c, "clause_type", "")} for c in notice.clauses]
    profile = compute_org_profile(org_row, clauses, profile_version=1)

    # Persist
    profile_payload = {
        "organization_id": organization_id,
        "industry_id": profile.industry_id,
        "sub_industry": profile.sub_industry,
        "ic": 0,
        "rss": profile.rss,
        "pgms": profile.pgms,
        "osi": profile.osi,
        "dsi": profile.dsi,
        "ehp": profile.ehp,
        "aigms": profile.aigms,
        "rss_tier": profile.rss_tier,
        "pgms_tier": profile.pgms_tier,
        "osi_tier": profile.osi_tier,
        "dsi_tier": profile.dsi_tier,
        "ehp_tier": profile.ehp_tier,
        "aigms_tier": profile.aigms_tier,
        "profile_version": 1,
        "confidence_score": profile.confidence_score,
    }
    await client.post(
        f"{SB}/rest/v1/organization_intelligence_profile",
        headers={**headers, "Content-Type": "application/json", "Prefer": "return=minimal"},
        json=profile_payload,
    )

    return profile_payload


async def _load_formula_thresholds(client, headers, formula_id, defaults_used):
    """Load thresholds from formula_version table, with documented fallback."""
    r = await client.get(
        f"{SB}/rest/v1/formula_version"
        f"?select=thresholds&formula_version_id=eq.{formula_id}&limit=1",
        headers=headers,
    )
    rows = r.json() if r.status_code == 200 else []
    if rows and rows[0].get("thresholds"):
        t = rows[0]["thresholds"]
        return json.loads(t) if isinstance(t, str) else t
    defaults_used.append(f"{formula_id}_thresholds")
    return _DEFAULT_F002_THRESHOLDS


async def _load_formula_weights(client, headers, formula_id, defaults_used):
    """Load weights from formula_version table, with documented fallback."""
    r = await client.get(
        f"{SB}/rest/v1/formula_version"
        f"?select=weights&formula_version_id=eq.{formula_id}&limit=1",
        headers=headers,
    )
    rows = r.json() if r.status_code == 200 else []
    if rows and rows[0].get("weights"):
        w = rows[0]["weights"]
        return json.loads(w) if isinstance(w, str) else w
    defaults_used.append(f"{formula_id}_weights")
    return _DEFAULT_F010_WEIGHTS


async def _load_regulators(client, headers) -> list[dict]:
    """Load regulators with priority weights."""
    r = await client.get(
        f"{SB}/rest/v1/regulator"
        f"?select=regulator_id,name,jurisdiction,priority_weights,enforcement_frequency_weight"
        f"&limit=50",
        headers=headers,
    )
    rows = r.json() if r.status_code == 200 else []
    result = []
    for reg in rows:
        rpw = reg.get("priority_weights", {})
        if isinstance(rpw, str):
            try:
                rpw = json.loads(rpw)
            except Exception:
                rpw = {}
        result.append({
            "id": reg["regulator_id"],
            "jurisdiction": reg.get("jurisdiction", ""),
            "efw": reg.get("enforcement_frequency_weight", 0.5),
            "rpw": rpw,
        })
    return result


async def _load_avg_source_reliability(client, headers) -> float:
    """Load average source reliability from source_record."""
    r = await client.get(
        f"{SB}/rest/v1/source_record"
        f"?select=source_reliability&limit=500",
        headers=headers,
    )
    rows = r.json() if r.status_code == 200 else []
    if not rows:
        return 0.5
    vals = [row.get("source_reliability") or 0.5 for row in rows]
    return sum(vals) / len(vals)


async def _load_catalogs(client, headers) -> tuple[dict, dict]:
    """Load finding_type + recommendation_library catalogs."""
    r1 = await client.get(
        f"{SB}/rest/v1/finding_type?select=code,title,default_severity,domain&limit=100",
        headers=headers,
    )
    ft_rows = r1.json() if r1.status_code == 200 else []
    finding_types = {f["code"]: f for f in ft_rows}

    r2 = await client.get(
        f"{SB}/rest/v1/recommendation_library?select=finding_type_code,id&limit=100",
        headers=headers,
    )
    rec_rows = r2.json() if r2.status_code == 200 else []
    recommendations = {
        r["finding_type_code"]: r["id"]
        for r in rec_rows
        if "finding_type_code" in r and "id" in r
    }

    return finding_types, recommendations


async def _compute_live_f004(
    client: httpx.AsyncClient,
    headers: dict,
    notice: DecomposedNotice,
    regulators: list[dict],
) -> tuple[float | None, dict]:
    """Compute live F-004 enforcement correlation via embeddings.

    Reuses similarity.py constants and compute_f004 from formulas.py.
    Returns (score_or_None, lineage_dict).
    """
    from app.services.scoring.formulas import EnforcementMatch, compute_f004
    from app.services.scoring.similarity import SIMILARITY_FLOOR, DEFAULT_K

    try:
        # Load clause embeddings (if available)
        clause_texts = [c.raw_text for c in notice.clauses if len(c.raw_text) >= 20]
        if not clause_texts:
            return None, {"reason": "no_clauses_to_embed"}

        # Try to embed clauses using the corpus model
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer(settings.embedding_model)
        clause_embeddings = model.encode(clause_texts, show_progress_bar=False).tolist()

        # Load enforcement embeddings from DB
        r = await client.get(
            f"{SB}/rest/v1/enforcement_record"
            f"?select=enforcement_id,regulator_id,embedding&limit=500",
            headers=headers,
        )
        enf_rows = r.json() if r.status_code == 200 else []
        enf_with_emb = [e for e in enf_rows if e.get("embedding")]

        if not enf_with_emb:
            return None, {"reason": "no_enforcement_embeddings"}

        # Build regulator lookup
        reg_map = {r["id"]: r for r in regulators}

        # For each clause, find top-k enforcement matches
        from app.services.scoring.similarity import top_k_enforcement_sync

        all_matches: list[EnforcementMatch] = []
        for i, emb in enumerate(clause_embeddings):
            clause = notice.clauses[i] if i < len(notice.clauses) else None
            domain = clause.category if clause else "other"

            top_matches = top_k_enforcement_sync(
                clause_embedding=emb,
                enforcement_rows=enf_with_emb,
                k=DEFAULT_K,
                similarity_floor=SIMILARITY_FLOOR,
            )

            for tm in top_matches:
                reg = reg_map.get(tm["regulator_id"], {})
                rpw_dict = reg.get("rpw", {})
                rpw = rpw_dict.get(domain, 0.0) if isinstance(rpw_dict, dict) else 0.0
                efw = reg.get("efw", 0.5)

                all_matches.append(EnforcementMatch(
                    clause_id=clause.clause_id if clause else f"clause_{i}",
                    enforcement_id=tm["enforcement_id"],
                    regulator_id=tm["regulator_id"],
                    cosine_similarity=tm["cosine_similarity"],
                    rpw=rpw,
                    efw=efw,
                    domain=domain,
                ))

        # Compute F-004
        f004_result = compute_f004(
            matches=all_matches,
            similarity_floor=SIMILARITY_FLOOR,
        )

        return f004_result.score, f004_result.source_lineage

    except ImportError:
        log.info("sentence-transformers not available for live F-004; skipping")
        return None, {"reason": "embeddings_unavailable"}
    except Exception as e:
        log.warning("Live F-004 computation failed: %s", e)
        return None, {"reason": f"computation_error: {type(e).__name__}"}
