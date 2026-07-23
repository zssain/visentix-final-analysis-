"""Source registry dispatch — map a source_registry `family` to its Connector,
load enabled sources, and run one family for manual triggering.

No source-specific connectors are registered yet (they arrive per-family in later
tasks). CONNECTORS is the single dispatch table; a family with no connector raises
a clear error rather than guessing.
"""
from __future__ import annotations

import logging

import httpx

from app.config import settings
from app.db import get_service_headers
from app.services.ingestion.backend import SupabaseBackend
from app.services.ingestion.base import Backend, Connector
from app.services.ingestion.connectors.edgar import EdgarBulkConnector
from app.services.ingestion.connectors.ftc import FTCConnector
from app.services.ingestion.connectors.hhs_ocr import HHSOCRConnector
from app.services.ingestion.runner import RunResult, run

log = logging.getLogger(__name__)

# family -> Connector subclass.
CONNECTORS: dict[str, type[Connector]] = {
    "hhs_ocr": HHSOCRConnector,
    "sec_edgar": EdgarBulkConnector,
    "ftc": FTCConnector,
}


def load_enabled_sources() -> list[dict]:
    """All enabled source_registry rows."""
    r = httpx.get(
        f"{settings.supabase_url}/rest/v1/source_registry?select=*&enabled=eq.true",
        headers=get_service_headers(), timeout=15)
    return r.json() if r.status_code < 300 else []


def _registry_row(family: str) -> dict | None:
    r = httpx.get(
        f"{settings.supabase_url}/rest/v1/source_registry?select=*&family=eq.{family}&limit=1",
        headers=get_service_headers(), timeout=15)
    rows = r.json() if r.status_code < 300 else []
    return rows[0] if rows else None


def run_one_by_family(family: str, *, dry_run: bool = False,
                      backend: Backend | None = None,
                      connector_kwargs: dict | None = None,
                      return_connector: bool = False):
    """Run the connector for `family` (manual trigger).

    `connector_kwargs` are passed to the connector constructor (e.g. sec_edgar's
    `limit` / `industries`). With `return_connector=True` the constructed connector
    is returned alongside the RunResult so a driver can read post-run metrics."""
    connector_cls = CONNECTORS.get(family)
    if connector_cls is None:
        raise ValueError(
            f"No connector registered for family '{family}'. "
            f"Registered: {sorted(CONNECTORS)}")

    row = _registry_row(family)
    if row is None:
        raise ValueError(f"No source_registry row for family '{family}'.")
    if not row.get("enabled"):
        log.warning("family '%s' is disabled in source_registry; running anyway (manual)", family)

    connector = connector_cls(row, **(connector_kwargs or {}))   # connectors take their registry row
    backend = backend or SupabaseBackend()
    result = run(backend, connector, registry_id=row.get("registry_id"), dry_run=dry_run)
    return (result, connector) if return_connector else result
