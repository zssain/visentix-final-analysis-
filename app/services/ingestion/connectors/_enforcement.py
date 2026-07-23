"""Shared building blocks for regulator-enforcement connectors (CPPA, state AGs).

Provides:
- Enforcement/privacy keyword classification (deterministic, no fuzzy inference).
- A generic `LiveEnforcementWriter` port (ensure_regulator / store_pdf →
  source_record / resolve_org / upsert_enforcement) parameterized by family +
  regulator, plus a fake-friendly interface for tests.
- The verdict-language containment contract (RAW_SOURCE_FIELDS): FTC/CPPA/AG source
  text may contain "violation" etc., but only inside raw source fields — every
  derived field the connector writes must be banned-term-free.

Same rules as the FTC connector (verdict containment, additive org resolution,
idempotent enforcement upsert on enforcement_id).
"""
from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone

import httpx

from app.config import settings
from app.db import get_service_headers
from app.services.ingestion.entity_resolution import build_name_index

log = logging.getLogger(__name__)

# enforcement_record columns a connector may write (guards against stray keys).
ENFORCEMENT_COLUMNS = {
    "enforcement_id", "regulator_id", "source_id", "source_type", "jurisdiction",
    "target_company", "target_industry", "entity_name", "entity_industry",
    "issue_tags", "penalty_usd", "fine_amount_usd", "action_date", "summary",
    "remedy", "remedies", "official_url", "source_name", "content_hash", "verified",
    "matter_number", "civil_action_number", "retrieved_at",
    "organization_id", "resolution_status",
}
# Fields copied VERBATIM from regulator source text (verdict language allowed);
# every OTHER text field written must be banned-term-free.
RAW_SOURCE_FIELDS = {
    "target_company", "entity_name", "issue_tags", "summary", "remedy", "remedies",
    "official_url", "source_name",
}

# Deterministic classification vocabularies (word-boundary, case-insensitive).
ENFORCEMENT_TERMS = [
    "settlement", "settle", "settles", "settled", "settling", "fine", "fines", "fined",
    "penalty", "penalties", "civil penalty", "decision", "stipulated", "stipulation",
    "consent order", "consent decree", "subpoena", "subpoenas", "sweep", "sweeps",
    "enforcement action", "enforcement", "injunction", "judgment", "disgorge",
    "cease and desist", "assurance of discontinuance",
]
PRIVACY_TERMS = [
    "privacy", "ccpa", "cpra", "data broker", "personal information", "consumer privacy",
    "data security", "data breach", "biometric", "opt-out", "opt out", "right to delete",
    "deletion", "sensitive personal", "geolocation", "surveillance pricing",
]


def _has_any(text: str, terms: list[str]) -> list[str]:
    low = (text or "").lower()
    return [t for t in terms if re.search(r"\b" + re.escape(t) + r"\b", low)]


def enforcement_signals(text: str) -> list[str]:
    return _has_any(text, ENFORCEMENT_TERMS)


def is_enforcement(text: str) -> bool:
    """True if the text shows an enforcement action (CPPA context is already privacy)."""
    return bool(enforcement_signals(text))


def is_privacy_enforcement(text: str) -> bool:
    """True only if BOTH a privacy signal AND an enforcement signal are present
    (used for state AGs, whose feeds are mostly non-privacy)."""
    return bool(_has_any(text, PRIVACY_TERMS)) and bool(enforcement_signals(text))


def enforcement_id_for(prefix: str, url: str) -> str:
    """Deterministic enforcement_id (uuid5) → idempotent upserts."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{prefix}:{url}"))


class LiveEnforcementWriter:
    """Generic Supabase writer for a regulator family. Tests inject a fake with the
    same surface (ensure_regulator / store_pdf / resolve_org / upsert_enforcement)."""

    def __init__(self, family: str, regulator_id: str, regulator_name: str,
                 jurisdiction: str, *, raw_folder: str | None = None,
                 fetcher=None, backend=None, authority: str = ""):
        self._family = family
        self._raw_folder = raw_folder or family
        self._reg_id = regulator_id
        self._reg_name = regulator_name
        self._jur = jurisdiction
        self._authority = authority
        self._url = settings.supabase_url
        self._fetcher = fetcher
        self._backend = backend
        self._index = None

    def _h(self, **extra):
        return {**get_service_headers(), **extra}

    def _rest(self, p):
        return f"{self._url}/rest/v1/{p}"

    def ensure_regulator(self) -> None:
        """Create the regulator row if absent. NEVER writes priority/topic-weight
        fields (a versioned job owns those)."""
        r = httpx.get(self._rest(f"regulator?select=regulator_id&regulator_id=eq.{self._reg_id}&limit=1"),
                      headers=self._h(), timeout=20)
        if r.status_code < 300 and r.json():
            return
        httpx.post(self._rest("regulator"),
                   headers=self._h(**{"Content-Type": "application/json",
                                      "Prefer": "resolution=ignore-duplicates,return=minimal"}),
                   json={"regulator_id": self._reg_id, "name": self._reg_name,
                         "jurisdiction": self._jur, "authority": self._authority or None}, timeout=20)

    def ensure_regulator_for(self, reg_id: str, state: str | None) -> None:
        """Ensure a specific regulator row (e.g. 'CA-AG') exists. Weights untouched."""
        r = httpx.get(self._rest(f"regulator?select=regulator_id&regulator_id=eq.{reg_id}&limit=1"),
                      headers=self._h(), timeout=20)
        if r.status_code < 300 and r.json():
            return
        httpx.post(self._rest("regulator"),
                   headers=self._h(**{"Content-Type": "application/json",
                                      "Prefer": "resolution=ignore-duplicates,return=minimal"}),
                   json={"regulator_id": reg_id,
                         "name": f"{state} Attorney General" if state else "State Attorney General",
                         "jurisdiction": f"US-{state}" if state else "US",
                         "authority": "State privacy/consumer-protection law"}, timeout=20)

    def store_pdf(self, pdf_url: str) -> dict | None:
        """Download a PDF → raw-artifacts/{folder}/… + a tier-1 source_record
        (source_type='enforcement'). Idempotent by content hash."""
        from app.services.ingestion.base import (
            derive_source_id, ext_for_content_type, raw_artifact_path, sha256_bytes,
        )
        if self._backend is None:
            from app.services.ingestion.backend import SupabaseBackend
            self._backend = SupabaseBackend()
        be = self._backend
        try:
            data, ctype = self._fetcher.get_bytes(pdf_url)
        except Exception as e:  # noqa: BLE001 — a missing PDF must not sink the item
            log.warning("PDF fetch failed %s: %s", pdf_url, type(e).__name__)
            return None
        sha = sha256_bytes(data)
        source_id = derive_source_id(self._family, f"pdf:{pdf_url}")
        path = raw_artifact_path(self._raw_folder, sha, ext_for_content_type(ctype or "application/pdf"))
        be.store_raw(path, data, ctype or "application/pdf")
        if be.find_source_record(source_id) is None:
            now = datetime.now(timezone.utc).isoformat()
            be.create_source_record({
                "source_id": source_id, "family": self._family, "source_type": "enforcement",
                "url": pdf_url, "title": pdf_url.rsplit("/", 1)[-1], "jurisdiction": self._jur,
                "sha256": sha, "storage_path": path, "extraction_confidence": 1.0,
                "retrieval_ts": now, "version_id": 1,
            })
            be.create_source_version({"version_id": f"{source_id}#1", "source_id": source_id,
                                      "hash": sha, "captured_at": now, "diff_summary": "initial capture"})
        return {"source_id": source_id, "path": path, "sha256": sha}

    def _load_index(self):
        if self._index is not None:
            return self._index
        pairs = []
        for path in ("organization_alias?select=value,organization_id&alias_type=eq.legal_name",
                     "organization?select=name,organization_id"):
            rows, off = [], 0
            while True:
                r = httpx.get(self._rest(path), headers=self._h(**{"Range": f"{off}-{off+999}"}), timeout=60)
                b = r.json() if r.status_code < 300 else []
                rows.extend(b)
                if len(b) < 1000:
                    break
                off += 1000
            key = "value" if "alias" in path else "name"
            pairs += [(x[key], x["organization_id"]) for x in rows]
        self._index = build_name_index(pairs)
        return self._index

    def resolve_org(self, name: str) -> str | None:
        return self._load_index().lookup(name) if name else None

    def upsert_enforcement(self, row: dict) -> bool:
        payload = {k: v for k, v in row.items() if k in ENFORCEMENT_COLUMNS}
        r = httpx.post(self._rest("enforcement_record?on_conflict=enforcement_id"),
                       headers=self._h(**{"Content-Type": "application/json",
                                          "Prefer": "resolution=merge-duplicates,return=minimal"}),
                       json=[payload], timeout=30)
        if r.status_code >= 300:
            raise RuntimeError(f"enforcement_record upsert failed: HTTP {r.status_code}")
        return True
