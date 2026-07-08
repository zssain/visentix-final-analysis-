"""White-label data feed — VICBNF-009.

GET /feed/white-label returns aggregate intelligence metrics with confidence +
versioning + permitted-use metadata. Never exposes raw source clause text.
"""

import json
from datetime import date
from uuid import uuid4

import httpx
from fastapi import APIRouter, HTTPException, status

from app.auth import AuthenticatedUser, require_role
from app.config import settings
from app.db import get_service_headers
from app.services.products.mapping import objects_for_product

router = APIRouter(prefix="/feed", tags=["feed"])

SB = settings.supabase_url


def _sb_get(path: str) -> list[dict]:
    r = httpx.get(f"{SB}/rest/v1/{path}", headers=get_service_headers(), timeout=15)
    return r.json() if r.status_code == 200 else []


@router.get("/white-label")
async def white_label_feed(
    user: AuthenticatedUser = require_role("admin"),
):
    """White-label data feed — aggregate intelligence with confidence + versioning.

    Never includes raw clause text. Every record carries VCI + formula_version +
    benchmark_population_version + permitted_use restriction.
    """
    # Get allowed object types for white-label
    allowed_objects = objects_for_product("white_label")
    allowed_types = {o["object_type"] for o in allowed_objects}
    visibility_map = {o["object_type"]: o["visibility"] for o in allowed_objects}

    # Load all derived data items (latest per org × object_type)
    derived = _sb_get(
        "derived_data_item?select=derived_data_item_id,object_type,organization_id,"
        "score,value_label,confidence_score,formula_version_id,"
        "scoring_model_version,source_corpus_version,benchmark_population_version,"
        "generated_at"
        "&order=generated_at.desc&limit=2000"
    )

    # Dedupe: latest per org × object_type
    seen: set[str] = set()
    records: list[dict] = []

    for d in derived:
        otype = d.get("object_type", "")
        org_id = d.get("organization_id", "")
        key = f"{org_id}:{otype}"

        if otype not in allowed_types or key in seen:
            continue
        seen.add(key)

        vci_score = (d.get("confidence_score") or 0) * 100

        records.append({
            "record_id": d.get("derived_data_item_id", ""),
            "organization_id": org_id,
            "object_type": otype,
            "score": d.get("score"),
            "value_label": d.get("value_label") or "",
            "vci": {
                "score": round(vci_score, 1),
                "band": _vci_band_label(vci_score),
            },
            "formula_version": d.get("formula_version_id", ""),
            "scoring_model_version": d.get("scoring_model_version") or settings.scoring_model_version,
            "source_corpus_version": d.get("source_corpus_version") or settings.source_corpus_version,
            "benchmark_population_version": d.get("benchmark_population_version") or "",
            "generated_at": d.get("generated_at") or "",
            "visibility_note": visibility_map.get(otype, ""),
            "permitted_use": (
                "Aggregate intelligence metrics only. Raw source clause text is "
                "not included. Redistribution requires data license agreement."
            ),
            "data_dictionary_reference": "config/glossary.json",
        })

    return {
        "dataset_id": str(uuid4()),
        "schema_version": "vicbnf-2.0.0",
        "refresh_date": str(date.today()),
        "record_count": len(records),
        "permitted_use": (
            "This feed contains aggregate privacy intelligence metrics. "
            "Raw source clause text is excluded. Each record includes "
            "confidence metadata (VCI score + band) and versioning. "
            "Redistribution requires a data license agreement."
        ),
        "confidence_metadata": {
            "vci_formula": "NLP 30% + Benchmark 25% + Regulatory 15% + Enforcement 15% + Source 15%",
            "bands": ["Very High (90-100)", "High (75-89)", "Moderate (60-74)", "Low (40-59)", "Very Low (0-39)"],
            "suppression_threshold": 40,
        },
        "records": records,
    }


def _vci_band_label(score: float) -> str:
    if score >= 90: return "Very High"
    if score >= 75: return "High"
    if score >= 60: return "Moderate"
    if score >= 40: return "Low"
    return "Very Low"
