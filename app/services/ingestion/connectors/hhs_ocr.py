"""HHS OCR breach-portal connector (family `hhs_ocr`).

The portal has NO static CSV URL — its "Export as CSV" button is a public JSF
form POST. `fetch()` drives that public export end-to-end:
  1. GET the report front page → ViewState + the "View HIPAA Breach Reports" command.
  2. POST it → the results page (ViewState + the CSV-export command).
  3. POST the CSV-export command → the CSV attachment.
Every dynamic token (ViewState, command ids) is extracted fresh each run. This is
the portal's own public export function, not an access-control bypass.

FRAGILITY IS LOUD, NOT CLEVER: if HHS changes the form and any token/command is
missing, or the final response isn't CSV, fetch() raises → the run ends
`outcome=failed` with a precise, non-secret error_summary. There is NO fallback
that scrapes the HTML data table.

Guardrails:
- NEVER writes enforcement_record — breach reports are org-risk signals, not
  enforcement actions (OD-06 / schema §2.9). organization_id NULL,
  resolution_status='unresolved' (Prompt 5 builds entity resolution).
- Row-level idempotency: deterministic event_id (uuid5 of the natural key).
- Malformed rows NEVER dropped: extraction_confidence < 1.0, raw row preserved in
  `description`, counted in the run summary.
- Never logs row text (counts only). Fetched bytes are untrusted (CSV-parsed
  defensively; never eval'd).
"""
from __future__ import annotations

import csv
import io
import json
import logging
import re
import uuid
from datetime import datetime
from urllib.parse import urljoin

import httpx

from app.config import settings
from app.db import get_service_headers
from app.services.ingestion.base import Connector, RawItem

log = logging.getLogger(__name__)

_NS = uuid.UUID("a7f3e2c0-1b4d-5e6f-8a90-0b1c2d3e4f50")
_UA = "Visentix-ingest/1.0 (HHS OCR public breach export)"
_DEFAULT_FRONT = "https://ocrportal.hhs.gov/ocr/breach/breach_report.jsf"

SECURITY_EVENT_COLUMNS = {
    "event_id", "source_record_id", "organization_id", "entity_name_raw",
    "entity_type", "state", "breach_date", "submission_date", "individuals_affected",
    "breach_type", "information_location", "description", "source_url",
    "capture_date", "extraction_confidence", "resolution_status",
}

# Named columns the CSV export must contain (the Name-of-Covered-Entity and the
# Business-Associate columns render broken PrimeFaces headers, so Name is taken
# positionally as the first column).
_REQUIRED_NAMED = {
    "state": "State",
    "entity_type": "Covered Entity Type",
    "individuals": "Individuals Affected",
    "submission_date": "Breach Submission Date",
    "breach_type": "Type of Breach",
    "location": "Location of Breached Information",
}
_KNOWN_NAMED = set(_REQUIRED_NAMED.values()) | {"Web Description"}


# ── JSF token/command extraction (module-level = unit-testable) ──────

def jsf_viewstate(html: str) -> str | None:
    m = re.search(r'name="javax\.faces\.ViewState"[^>]*value="([^"]+)"', html)
    return m.group(1) if m else None


def jsf_form_action(html: str, form_id: str) -> str | None:
    m = re.search(r'<form[^>]*id="' + re.escape(form_id) + r'"[^>]*?action="([^"]+)"', html)
    return m.group(1) if m else None


def jsf_command_by_label(html: str, label: str) -> str | None:
    """The jsfcljs command source of the anchor whose visible text contains `label`."""
    for m in re.finditer(r"<a\b([^>]*)>(.*?)</a>", html, re.S):
        text = re.sub(r"<[^>]+>", "", m.group(2)).strip()
        if label.lower() in text.lower():
            pm = re.search(r"\{'([A-Za-z0-9_:]+)'\s*:", m.group(1))
            if pm:
                return pm.group(1)
    return None


def jsf_csv_export_command(html: str) -> str | None:
    """The command source of the anchor wrapping the CSV export icon."""
    for m in re.finditer(r'<a\b([^>]*)>\s*<img\b[^>]*?(?:alt="CSV"|title="Export as CSV")', html, re.I):
        pm = re.search(r"\{'([A-Za-z0-9_:]+)'\s*:", m.group(1))
        if pm:
            return pm.group(1)
    return None


def _parse_date(s: str) -> str | None:
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m/%d/%y", "%m-%d-%Y"):
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def live_event_writer(rows: list[dict]) -> int:
    """Upsert security_event with ON CONFLICT (event_id) DO NOTHING; returns the
    number ACTUALLY inserted (duplicates ignored, not returned)."""
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
    parser_version = "hhs-ocr-jsf-csv-v1"
    parser_description = "HHS OCR breach portal JSF CSV export → security_event"
    default_extraction_confidence = 1.0

    def __init__(self, registry_row: dict | None = None, event_writer=None):
        cfg = (registry_row or {}).get("config") or {}
        self._front_url = cfg.get("report_url") or (registry_row or {}).get("base_url") or _DEFAULT_FRONT
        self._event_writer = event_writer or live_event_writer
        self._parsed = 0
        self._inserted = 0
        self._malformed = 0

    # ── fetch: drive the public JSF CSV export ──────────────────────
    def fetch(self) -> list[RawItem]:
        data = self._jsf_export(self._front_url)
        head = data[:2000].decode("utf-8", "ignore")
        # header row's named columns confirm this is the breach CSV
        if "Breach Submission Date" not in head or "Type of Breach" not in head:
            raise ValueError("hhs_ocr JSF: export response is not the expected breach CSV "
                             "(missing known headers) — portal export changed")
        log.info("hhs_ocr JSF export ok: %d bytes", len(data))
        return [RawItem(data=data, content_type="text/csv", source_url=self._front_url,
                        natural_key="hhs_ocr_breach_export_500plus",
                        title="HHS OCR Breaches Affecting 500+ Individuals")]

    def _jsf_export(self, front_url: str) -> bytes:
        def fail(msg: str):
            raise ValueError(f"hhs_ocr JSF: {msg}")

        with httpx.Client(timeout=90, follow_redirects=True, headers={"User-Agent": _UA}) as client:
            # 1. front page
            r1 = client.get(front_url)
            r1.raise_for_status()
            h1 = r1.text
            act1 = jsf_form_action(h1, "ocrForm") or fail("ocrForm/action not found on front page")
            vs1 = jsf_viewstate(h1) or fail("ViewState not found on front page")
            view_cmd = jsf_command_by_label(h1, "View HIPAA Breach Reports") \
                or fail("'View HIPAA Breach Reports' command not found (form changed)")

            # 2. navigate to the results page
            r2 = client.post(urljoin(front_url, act1), data={
                "ocrForm": "ocrForm", "javax.faces.ViewState": vs1, view_cmd: view_cmd})
            r2.raise_for_status()
            h2 = r2.text
            act2 = jsf_form_action(h2, "ocrForm") or fail("ocrForm/action not found on report page")
            vs2 = jsf_viewstate(h2) or fail("ViewState not found on report page")
            csv_cmd = jsf_csv_export_command(h2) \
                or fail("CSV export control not found on report page (form changed)")

            # 3. trigger the CSV export
            r3 = client.post(urljoin(front_url, act2), data={
                "ocrForm": "ocrForm", "javax.faces.ViewState": vs2, csv_cmd: csv_cmd})
            r3.raise_for_status()
            ct = r3.headers.get("content-type", "")
            cd = r3.headers.get("content-disposition", "")
            if "csv" not in ct.lower() and "csv" not in cd.lower():
                fail(f"export did not return CSV (content-type '{ct[:40]}', "
                     f"disposition '{cd[:40]}') — portal export changed")
            return r3.content

    # ── parse: real export structure ────────────────────────────────
    def parse(self, item: RawItem) -> list[dict]:
        text = item.data.decode("utf-8-sig", "replace")
        rows = list(csv.reader(io.StringIO(text)))
        if not rows:
            raise ValueError("hhs_ocr: empty CSV export")
        cols = self._resolve_columns([h.strip() for h in rows[0]])
        records = []
        for raw in rows[1:]:
            if not any((c or "").strip() for c in raw):
                continue
            rec, malformed = self._map_row(raw, cols, item.source_url)
            self._parsed += 1
            if malformed:
                self._malformed += 1
            records.append(rec)
        log.info("hhs_ocr parsed %d rows (%d malformed)", self._parsed, self._malformed)
        return records

    def _resolve_columns(self, header: list[str]) -> dict:
        """Map logical fields → column index. Name is positional (col 0, whose
        header renders as a broken PrimeFaces component string); the rest by name.
        Raises loudly if the structure changed."""
        idx: dict[str, int] = {}
        for i, h in enumerate(header):
            idx.setdefault(h, i)
        if not header or header[0] in _KNOWN_NAMED:
            raise ValueError("hhs_ocr: first CSV column is a named field — column order "
                             "changed (loud fail; refusing to guess)")
        cols = {"name": 0}
        for field, hdr in _REQUIRED_NAMED.items():
            if hdr not in idx:
                raise ValueError(f"hhs_ocr: CSV export missing required column '{hdr}' — "
                                 f"structure changed (loud fail)")
            cols[field] = idx[hdr]
        cols["web_description"] = idx.get("Web Description")
        return cols

    def _map_row(self, raw: list[str], cols: dict, source_url: str) -> tuple[dict, bool]:
        def g(field: str) -> str:
            i = cols.get(field)
            return (raw[i].strip() if i is not None and i < len(raw) else "")

        entity = g("name")
        ia_raw = g("individuals")
        sd_raw = g("submission_date")
        breach_type = g("breach_type")

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

        description = g("web_description") or None
        confidence = 1.0
        if malformed:
            confidence = 0.5
            description = "[MALFORMED ROW] " + json.dumps(raw, ensure_ascii=False)[:4000]

        key = f"{entity}|{submission_date or sd_raw}|{breach_type}|" \
              f"{individuals if individuals is not None else ia_raw}"
        rec = {
            "event_id": str(uuid.uuid5(_NS, key)),
            "organization_id": None,                # entity resolution is Prompt 5
            "entity_name_raw": entity or None,
            "entity_type": g("entity_type") or None,
            "state": g("state") or None,
            "breach_date": None,
            "submission_date": submission_date,
            "individuals_affected": individuals,
            "breach_type": breach_type or None,
            "information_location": g("location") or None,
            "description": description,
            "source_url": source_url,
            "extraction_confidence": confidence,
            "resolution_status": "unresolved",
        }
        return rec, malformed

    # ── upsert (security_event only) ────────────────────────────────
    def upsert(self, records: list[dict]) -> None:
        rows = [{k: v for k, v in r.items() if k in SECURITY_EVENT_COLUMNS} for r in records]
        self._inserted += self._event_writer(rows)

    def record_counts(self) -> dict:
        return {"seen": self._parsed, "new": self._inserted, "changed": 0,
                "skipped": max(0, self._parsed - self._inserted), "malformed": self._malformed}

    def run_warnings(self) -> list[str]:
        if self._malformed:
            return [f"{self._malformed} malformed CSV rows stored with extraction_confidence<1.0"]
        return []
