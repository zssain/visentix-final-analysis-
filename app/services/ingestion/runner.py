"""Run a connector: ingestion_run bookkeeping, retries, politeness, per-item
error isolation. One item failing does NOT abort the run (partial outcome)."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

import httpx

from app.config import settings
from app.services.ingestion.base import (
    CHANGED, NEW, SKIPPED, Backend, Connector, process_item,
)

log = logging.getLogger(__name__)

# outcomes
OK = "ok"
PARTIAL = "partial"
FAILED = "failed"

_TRANSIENT = (httpx.TransportError, httpx.HTTPStatusError, httpx.TimeoutException)


@dataclass
class RunResult:
    outcome: str
    seen: int = 0
    new: int = 0
    changed: int = 0
    skipped: int = 0
    errors: list[dict] = field(default_factory=list)
    run_id: str | None = None


def _fetch_with_retries(connector: Connector, max_retries: int = 3):
    """Fetch, retrying transient HTTP errors with exponential backoff."""
    for attempt in range(max_retries):
        try:
            return connector.fetch()
        except _TRANSIENT as e:
            if attempt == max_retries - 1:
                raise
            wait = 2 ** attempt
            log.warning("fetch transient error (%s), retry %d/%d in %ds",
                        type(e).__name__, attempt + 1, max_retries, wait)
            time.sleep(wait)


def run(
    backend: Backend,
    connector: Connector,
    *,
    registry_id: str | None = None,
    dry_run: bool = False,
    politeness_seconds: float | None = None,
    max_retries: int = 3,
) -> RunResult:
    """Execute one ingestion run for `connector`."""
    politeness = (settings.ingestion_politeness_seconds
                  if politeness_seconds is None else politeness_seconds)

    # dry-run writes NOTHING: no parser_version registration, no ingestion_run row.
    parser_version_id = (None if dry_run else
                         backend.register_parser_version(
                             connector.family, connector.parser_version, connector.parser_description))
    run_id = (None if dry_run else
              backend.create_ingestion_run({
                  "registry_id": registry_id,
                  "source_name": connector.family,
                  "run_type": "manual",
                  "status": "running",
                  "started_at": datetime.now(timezone.utc).isoformat(),
              }))

    # Fetch (retried). A total fetch failure = failed run, recorded and returned.
    try:
        items = _fetch_with_retries(connector, max_retries)
    except Exception as e:  # noqa: BLE001 — surface as a failed run, never crash the caller
        err = [{"stage": "fetch", "error": f"{type(e).__name__}: {e}"}]
        log.error("fetch failed after retries: %s", type(e).__name__)
        if not dry_run:
            backend.finish_ingestion_run(run_id, {
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "outcome": FAILED, "status": FAILED,
                "records_seen": 0, "error_summary": _summarize(err),
            })
        return RunResult(outcome=FAILED, errors=err, run_id=run_id)

    seen = new = changed = skipped = 0
    errors: list[dict] = []
    for i, item in enumerate(items):
        if i > 0 and politeness > 0:
            time.sleep(politeness)
        seen += 1
        try:
            status = process_item(backend, connector, item, parser_version_id, dry_run)
            if status == NEW:
                new += 1
            elif status == CHANGED:
                changed += 1
            elif status == SKIPPED:
                skipped += 1
        except Exception as e:  # noqa: BLE001 — item failure is isolated (partial run)
            errors.append({"natural_key": item.natural_key, "error": f"{type(e).__name__}: {e}"})
            log.warning("item failed key=%s: %s", item.natural_key, type(e).__name__)

    outcome = OK if not errors else PARTIAL
    if not dry_run:
        backend.finish_ingestion_run(run_id, {
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "outcome": outcome, "status": outcome,
            "records_seen": seen, "records_new": new,
            "records_changed": changed, "records_skipped": skipped,
            "rows_inserted": new, "rows_updated": changed,
            "error_summary": _summarize(errors) if errors else None,
        })

    log.info("run done family=%s outcome=%s seen=%d new=%d changed=%d skipped=%d errors=%d",
             connector.family, outcome, seen, new, changed, skipped, len(errors))
    return RunResult(outcome=outcome, seen=seen, new=new, changed=changed,
                     skipped=skipped, errors=errors, run_id=run_id)


def _summarize(errors: list[dict]) -> str:
    """Compact, non-sensitive error summary (no document text)."""
    return "; ".join(f"{e.get('natural_key', e.get('stage', '?'))}: {e['error']}" for e in errors)[:1000]
