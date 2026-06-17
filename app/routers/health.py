"""Health check endpoint — live row counts + Ollama status."""

import httpx
from fastapi import APIRouter, Depends

from app.config import Settings
from app.db import get_service_headers
from app.deps import get_settings

router = APIRouter(tags=["health"])

CORE_TABLES = [
    "organization",
    "source_record",
    "privacy_notice",
    "notice_section",
    "disclosure_clause",
    "obligation",
    "enforcement_record",
    "regulator",
    "litigation_event",
    "monitoring_event",
    "formula_version",
    "benchmark_membership",
    "derived_data_item",
    "finding_type",
    "recommendation_library",
    "exemplar",
    "risk_finding",
    "organization_intelligence_profile",
    "report_snapshot",
]


@router.get("/health")
async def health(cfg: Settings = Depends(get_settings)):
    headers = {**get_service_headers(), "Prefer": "count=exact"}

    row_counts: dict[str, int | str] = {}
    async with httpx.AsyncClient(timeout=10) as client:
        for table in CORE_TABLES:
            try:
                r = await client.get(
                    f"{cfg.supabase_url}/rest/v1/{table}?select=*&limit=0",
                    headers=headers,
                )
                content_range = r.headers.get("content-range", "*/0")
                total = content_range.split("/")[-1]
                row_counts[table] = int(total) if total.isdigit() else 0
            except Exception:
                row_counts[table] = "error"

        ollama_status = "down"
        try:
            r = await client.get(f"{cfg.ollama_base_url}/api/version")
            if r.status_code == 200:
                ollama_status = "ok"
        except Exception:
            pass

    return {
        "status": "healthy",
        "row_counts": row_counts,
        "ollama": ollama_status,
    }
