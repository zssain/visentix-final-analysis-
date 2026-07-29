"""Health check endpoint — live row counts + model-backend status.

Reports reachability of the ACTIVE model backend: the hosted Ollama on the
private RunPod pod (over the tailnet) when HOSTED_QWEN_BASE_URL is set, else the
local Ollama. Row-count probes run concurrently so /health stays fast (~1s) and
does not trip container healthcheck timeouts. See deploy topology + spec 1D.
"""

import asyncio

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
    # count=estimated → planner estimate (near-instant) instead of a full-scan
    # exact count; a health probe must stay fast on 500k+ row tables.
    headers = {**get_service_headers(), "Prefer": "count=estimated"}

    # Active model backend: hosted (private pod over tailnet) if configured, else local.
    backend = "hosted" if cfg.hosted_qwen_base_url else "local"
    model_base_url = cfg.hosted_qwen_base_url or cfg.ollama_base_url

    async with httpx.AsyncClient(timeout=8) as client:

        async def _count(table: str) -> tuple[str, int | str]:
            try:
                r = await client.get(
                    f"{cfg.supabase_url}/rest/v1/{table}?select=*&limit=0",
                    headers=headers,
                )
                total = r.headers.get("content-range", "*/0").split("/")[-1]
                return table, (int(total) if total.isdigit() else 0)
            except Exception:
                return table, "error"

        # Row counts + backend probe run concurrently → ~1s instead of ~10s.
        counts, model_status = await asyncio.gather(
            asyncio.gather(*(_count(t) for t in CORE_TABLES)),
            _probe_model(client, model_base_url),
        )

    row_counts = dict(counts)
    db_ok = not any(v == "error" for v in row_counts.values())

    return {
        "status": "healthy" if db_ok and model_status == "ok" else "degraded",
        "db": "ok" if db_ok else "degraded",
        "model_backend": backend,
        "model_status": model_status,
        # Back-compat alias for existing consumers (admin status, frontend):
        "ollama": model_status,
        "row_counts": row_counts,
    }


async def _probe_model(client: httpx.AsyncClient, base_url: str) -> str:
    """Reachability of the model backend's Ollama server (native /api/version).

    Short timeout on purpose: /health must stay fast (and return HTTP 200) even
    when the model backend is unreachable, so a transient pod outage NEVER 503s
    the edge / takes down login + reports. Classification fails fast elsewhere
    (spec 1D); /health only *reports* model_status, it does not gate liveness.
    """
    try:
        r = await client.get(f"{base_url}/api/version", timeout=2.0)
        return "ok" if r.status_code == 200 else "down"
    except Exception:
        return "down"
