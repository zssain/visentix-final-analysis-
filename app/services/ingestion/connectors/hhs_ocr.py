"""HHS OCR breach-portal connector (family `hhs_ocr`).

Downloads the official OCR "breaches affecting 500+ individuals" CSV export
(URL from source_registry config, no API key), stores it as ONE raw artifact +
source_record (source_type='security', tier 1 per registry), and parses each row
into a `security_event`.

Guardrails:
- NEVER writes to enforcement_record — breach reports are org-risk signals, not
  enforcement actions (OD-06 / schema §2.9). organization_id is left NULL and
  resolution_status='unresolved' (Prompt 5 builds entity resolution).
- Row-level idempotency via a deterministic event_id (uuid5 of the natural key:
  entity_name_raw | submission_date | breach_type | individuals_affected).
- Malformed rows are NEVER dropped: stored with extraction_confidence < 1.0 and
  the raw row preserved in `description`, and counted in the run's summary.
- Never logs row text — counts only. Fetched bytes are untrusted (CSV-parsed
  defensively; never eval'd).
"""
from __future__ import annotations

import csv
import io
import json
import logging
import uuid
from datetime import datetime

import httpx

from app.config import settings
from app.db import get_service_headers
from app.services.ingestion.base import Connector, RawItem

log = logging.getLogger(__name__)

# Deterministic namespace for hhs_ocr event ids (stable across runs).
_NS = uuid.UUID("a7f3e2c0-1b4d-5e6f-8a90-0b1c2d3e4f50")

# Only these keys are written to security_event (the framework also attaches
# parser_version_id for lineage, which security_event does not store).
SECURITY_EVENT_COLUMNS = {
    "event_id", "source_record_id", "organization_id", "entity_name_raw",
    "entity_type", "state", "breach_date", "submission_date", "individuals_affected",
    "breach_type", "information_location", "description", "source_url",
    "capture_date", "extraction_confidence", "resolution_status",
}


def _parse_date(s: str) -> str | None:
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m/%d/%y", "%m-%d-%Y"):
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def live_event_writer(rows: list[dict]) -> int:
    """Upsert security_event rows with ON CONFLICT (event_id) DO NOTHING; returns
    the number ACTUALLY inserted (duplicates are ignored, not returned)."""
    if not rows:
        return 0
    headers = {**get_service_headers(), "Content-Type": "application/json",
               "Prefer": "resolution=ignore-duplicates,return=representation"}
    r = httpx.post(f"{settings.supabase_url}/rest/v1/security_event?on_conflict=event_id",
                   headers=headers, json=rows, timeout=60)
    if r.status_code >= 300:
        raise RuntimeError(f"security_event upsert failed: HTTP {r.status_code}")
    inserted = r.json() if r.headers.get("content-type", "").startswith("application/json") else []
    return len(inserted)


class HHSOCRConnector(Connector):
    family = "hhs_ocr"
    source_type = "security"
    parser_version = "hhs-ocr-csv-v1"
    parser_description = "HHS OCR breach portal CSV → security_event"
    default_extraction_confidence = 1.0

    def __init__(self, registry_row: dict | None = None, event_writer=None):
        cfg = (registry_row or {}).get("config") or {}
        self._csv_url = cfg.get("csv_url") or (registry_row or {}).get("base_url")
        self._event_writer = event_writer or live_event_writer
        self._parsed = 0
        self._inserted = 0
        self._malformed = 0

    # ── fetch ───────────────────────────────────────────────────────
    def fetch(self) -> list[RawItem]:
        if not self._csv_url:
            raise ValueError("hhs_ocr: no csv_url in source_registry config")
        r = httpx.get(self._csv_url, timeout=60, follow_redirects=True)
        r.raise_for_status()
        data = r.content
        ct = r.headers.get("content-type", "")
        head = data[:2000].decode("utf-8", "ignore")
        if "csv" not in ct.lower() and "Name of Covered Entity" not in head:
            raise ValueError(
                f"hhs_ocr: expected a CSV export, got content-type '{ct[:40]}'. The OCR "
                f"portal serves an HTML/JSF page on GET — config.csv_url must point at a "
                f"direct GET-able CSV.")
        log.info("hhs_ocr fetch ok: %d bytes, content-type=%s", len(data), ct[:40])
        return [RawItem(data=data, content_type="text/csv", source_url=self._csv_url,
                        natural_key="hhs_ocr_breach_export_500plus",
                        title="HHS OCR Breaches Affecting 500+ Individuals")]

    # ── parse ───────────────────────────────────────────────────────
    def parse(self, item: RawItem) -> list[dict]:
        text = item.data.decode("utf-8-sig", "replace")
        reader = csv.DictReader(io.StringIO(text))
        records = []
        for raw in reader:
            rec, malformed = self._map_row(raw, item.source_url)
            self._parsed += 1
            if malformed:
                self._malformed += 1
            records.append(rec)
        log.info("hhs_ocr parsed %d rows (%d malformed)", self._parsed, self._malformed)
        return records

    def _map_row(self, raw: dict, source_url: str) -> tuple[dict, bool]:
        raw = {(k or "").strip(): (v or "").strip() for k, v in raw.items() if k is not None}
        entity = raw.get("Name of Covered Entity", "")
        ia_raw = raw.get("Individuals Affected", "")
        sd_raw = raw.get("Breach Submission Date", "")
        breach_type = raw.get("Type of Breach", "")

        malformed = False

        individuals = None
        if ia_raw:
            try:
                individuals = int(float(ia_raw.replace(",", "")))
            except ValueError:
                malformed = True

        submission_date = None
        if sd_raw:
            submission_date = _parse_date(sd_raw)
            if submission_date is None:
                malformed = True

        if not entity:
            malformed = True

        description = raw.get("Web Description", "") or None
        confidence = 1.0
        if malformed:
            confidence = 0.5
            # preserve the raw row so nothing is silently dropped
            description = "[MALFORMED ROW] " + json.dumps(raw, ensure_ascii=False)[:4000]

        key = f"{entity}|{submission_date or sd_raw}|{breach_type}|" \
              f"{individuals if individuals is not None else ia_raw}"
        rec = {
            "event_id": str(uuid.uuid5(_NS, key)),
            "organization_id": None,                # entity resolution is Prompt 5
            "entity_name_raw": entity or None,
            "entity_type": raw.get("Covered Entity Type") or None,
            "state": raw.get("State") or None,
            "breach_date": None,
            "submission_date": submission_date,
            "individuals_affected": individuals,
            "breach_type": breach_type or None,
            "information_location": raw.get("Location of Breached Information") or None,
            "description": description,
            "source_url": source_url,
            "extraction_confidence": confidence,
            "resolution_status": "unresolved",
        }
        return rec, malformed

    # ── upsert ──────────────────────────────────────────────────────
    def upsert(self, records: list[dict]) -> None:
        rows = [{k: v for k, v in r.items() if k in SECURITY_EVENT_COLUMNS} for r in records]
        self._inserted += self._event_writer(rows)

    # ── row-level counts + warnings for the ingestion_run ──────────
    def record_counts(self) -> dict:
        return {"seen": self._parsed, "new": self._inserted, "changed": 0,
                "skipped": max(0, self._parsed - self._inserted), "malformed": self._malformed}

    def run_warnings(self) -> list[str]:
        if self._malformed:
            return [f"{self._malformed} malformed CSV rows stored with extraction_confidence<1.0"]
        return []
