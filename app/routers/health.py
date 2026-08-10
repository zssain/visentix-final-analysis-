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

    backend = cfg.effective_llm_backend  # "local" | "hosted_ollama" | "runpod_serverless"

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

        # CRITICAL (cost): /health MUST NOT run inference or wake a scale-to-zero
        # serverless worker. Only the LOCAL dev backend (localhost Ollama, no GPU
        # bill) is probed. Hosted/serverless report configuration presence WITHOUT
        # any network/inference call — a "cold" serverless endpoint is normal.
        if backend == "local":
            counts, model_status = await asyncio.gather(
                asyncio.gather(*(_count(t) for t in CORE_TABLES)),
                _probe_model(client, cfg.ollama_base_url),
            )
            llm = {"provider": "local", "configured": True,
                   "status": model_status, "probe": "ollama_version"}
        else:
            counts = await asyncio.gather(*(_count(t) for t in CORE_TABLES))
            if backend == "runpod_serverless":
                configured = bool(cfg.runpod_endpoint_id and cfg.runpod_api_key.get_secret_value())
            else:  # hosted_ollama (legacy Pod)
                configured = bool(cfg.hosted_qwen_base_url)
            model_status = "not_probed"
            llm = {"provider": backend, "configured": configured,
                   "status": "not_probed",
                   "probe": "not_invoked_to_avoid_cold_start"}

    row_counts = dict(counts)
    db_ok = not any(v == "error" for v in row_counts.values())

    # Liveness is DB-driven ONLY. The LLM provider is REPORTED, never gated — a
    # scale-to-zero endpoint sitting cold must not mark the app unhealthy (which
    # would 503 the edge / break login + reports).
    return {
        "status": "healthy" if db_ok else "degraded",
        "db": "ok" if db_ok else "degraded",
        "model_backend": backend,
        "model_status": model_status,           # "ok"/"down" (local) or "not_probed"
        "ollama": model_status,                 # back-compat alias
        "llm": llm,
        "row_counts": row_counts,
    }


async def _probe_model(client: httpx.AsyncClient, base_url: str) -> str:
    """Reachability of a LOCAL Ollama server (native /api/version) — dev only.

    NEVER used for the hosted Pod or the serverless endpoint (a probe there would
    either hit a Tailscale-only host or WAKE A SERVERLESS WORKER, defeating
    scale-to-zero). /health only *reports* model status; it does not gate liveness.
    """
    try:
        r = await client.get(f"{base_url}/api/version", timeout=2.0)
        return "ok" if r.status_code == 200 else "down"
    except Exception:
        return "down"
