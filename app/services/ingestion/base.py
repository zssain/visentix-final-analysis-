"""Connector framework core — abstractions + the per-item lifecycle.

The lifecycle is deliberately backend-agnostic: it depends on the `Backend` port
(source_record/source_version/raw storage/parser_version), so it can run against
Supabase in production and an in-memory fake in tests. No source-specific logic
lives here — connectors subclass `Connector`.

Security posture (AGENTS.md §3):
- Never log document full text — only lengths and hashes.
- Fetched bytes are UNTRUSTED data: never eval/exec them; parse defensively.
"""
from __future__ import annotations

import abc
import hashlib
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timezone

log = logging.getLogger(__name__)


# ── Value types ─────────────────────────────────────────────────────

@dataclass
class RawItem:
    """One fetched source object: raw bytes + provenance."""
    data: bytes
    content_type: str          # e.g. "text/html", "application/pdf", "application/json"
    source_url: str            # the URL it came from (must be a source_registry config URL)
    natural_key: str           # stable identity for this source object within its family
    title: str = ""
    jurisdiction: str = ""


# Item outcomes
NEW = "new"
CHANGED = "changed"
SKIPPED = "skipped"

# content-type → file extension (for the raw-artifact path)
_EXT = {
    "text/html": "html",
    "application/pdf": "pdf",
    "application/json": "json",
    "text/plain": "txt",
    "text/csv": "csv",
    "application/xml": "xml",
    "text/xml": "xml",
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def ext_for_content_type(content_type: str) -> str:
    return _EXT.get((content_type or "").split(";")[0].strip().lower(), "bin")


def derive_source_id(family: str, natural_key: str) -> str:
    """Deterministic source_record id from (family, natural_key), so re-ingesting
    the same source object always resolves to the same row."""
    digest = hashlib.sha256(f"{family}::{natural_key}".encode("utf-8")).hexdigest()[:24]
    return f"{family}:{digest}"


def raw_artifact_path(family: str, sha256: str, ext: str, when: date | None = None) -> str:
    """raw-artifacts/{family}/{YYYY}/{MM}/{sha256}.{ext} — new objects only."""
    when = when or datetime.now(timezone.utc).date()
    return f"raw-artifacts/{family}/{when:%Y}/{when:%m}/{sha256}.{ext}"


# ── Ports ───────────────────────────────────────────────────────────

class Backend(abc.ABC):
    """Everything the lifecycle needs from the outside world. Implemented by
    SupabaseBackend (prod) and a fake (tests)."""

    @abc.abstractmethod
    def find_source_record(self, source_id: str) -> dict | None: ...

    @abc.abstractmethod
    def latest_version_hash(self, source_id: str) -> str | None: ...

    @abc.abstractmethod
    def version_count(self, source_id: str) -> int: ...

    @abc.abstractmethod
    def store_raw(self, path: str, data: bytes, content_type: str) -> str:
        """Store bytes at `path` WITHOUT overwriting. Returns 'created' or
        'reused' (object already present). Never mutates an existing object."""

    @abc.abstractmethod
    def create_source_record(self, row: dict) -> None: ...

    @abc.abstractmethod
    def create_source_version(self, row: dict) -> None: ...

    @abc.abstractmethod
    def register_parser_version(self, family: str, version: str, description: str) -> str:
        """Idempotently register (family, version); return parser_version_id."""

    @abc.abstractmethod
    def create_ingestion_run(self, row: dict) -> str: ...

    @abc.abstractmethod
    def finish_ingestion_run(self, run_id: str, updates: dict) -> None: ...


class Connector(abc.ABC):
    """A source family's adapter. Subclasses provide fetch/parse/upsert; the
    framework owns hashing, idempotency, versioning, raw storage, and lineage."""

    family: str = ""
    source_type: str = ""                       # source_record.source_type
    parser_version: str = "v1"
    parser_description: str = ""
    default_extraction_confidence: float = 0.5

    @abc.abstractmethod
    def fetch(self) -> list[RawItem]:
        """Return the source objects. Network calls (if any) go ONLY to URLs from
        the source_registry config. Raise on transient HTTP errors — the runner
        retries. Returned bytes are untrusted."""

    @abc.abstractmethod
    def parse(self, item: RawItem) -> list[dict]:
        """Parse one raw item into normalized record dicts. Parse DEFENSIVELY —
        never eval/exec fetched content. The framework attaches lineage fields."""

    @abc.abstractmethod
    def upsert(self, records: list[dict]) -> None:
        """Persist normalized records (connector-specific target)."""

    # ── Optional hooks (batch connectors override) ──────────────────
    def record_counts(self) -> dict | None:
        """Row-level counts a batch connector wants recorded on the
        ingestion_run (keys: seen/new/changed/skipped[/malformed]). One CSV item
        can carry many rows, so `records_seen` should reflect rows, not items.
        Return None to use the runner's per-item counts."""
        return None

    def run_warnings(self) -> list[str]:
        """Non-fatal warnings (e.g. malformed-row count) to fold into the run's
        error_summary and mark the outcome partial."""
        return []


# ── The per-item lifecycle ──────────────────────────────────────────

def process_item(
    backend: Backend,
    connector: Connector,
    item: RawItem,
    parser_version_id: str | None,
    dry_run: bool = False,
) -> str:
    """Run one item through the lifecycle. Returns NEW | CHANGED | SKIPPED.

    hash → look up source_record by natural key → decide skip/new/changed →
    (writes, unless dry_run) raw-store, source_record/version, parse+upsert.
    """
    content_hash = sha256_bytes(item.data)
    source_id = derive_source_id(connector.family, item.natural_key)

    existing = backend.find_source_record(source_id)
    if existing is None:
        status = NEW
    elif backend.latest_version_hash(source_id) == content_hash:
        status = SKIPPED
    else:
        status = CHANGED

    log.info("ingest item family=%s key=%s bytes=%d hash=%s -> %s",
             connector.family, item.natural_key, len(item.data), content_hash[:12], status)

    if status == SKIPPED:
        return SKIPPED
    if dry_run:
        # fetch + hash + diff only — write nothing.
        return status

    # Parse FIRST (defensively) so a parse failure leaves NO partial state — the
    # item stays un-recorded and is retried on the next run, never silently
    # stranded with a source_record but no parsed data.
    records = connector.parse(item)

    ext = ext_for_content_type(item.content_type)
    path = raw_artifact_path(connector.family, content_hash, ext)
    disp = backend.store_raw(path, item.data, item.content_type)
    log.info("raw %s at %s (%d bytes)", disp, path, len(item.data))

    now = datetime.now(timezone.utc).isoformat()
    if status == NEW:
        version_id = f"{source_id}#1"
        backend.create_source_record({
            "source_id": source_id,
            "family": connector.family,
            "source_type": connector.source_type,
            "url": item.source_url,
            "title": item.title,
            "jurisdiction": item.jurisdiction or None,
            "sha256": content_hash,
            "storage_path": path,
            "extraction_confidence": connector.default_extraction_confidence,
            "retrieval_ts": now,
            "version_id": version_id,
        })
        backend.create_source_version({
            "version_id": version_id, "source_id": source_id,
            "hash": content_hash, "captured_at": now, "diff_summary": "initial capture",
        })
    else:  # CHANGED
        version_id = f"{source_id}#{backend.version_count(source_id) + 1}"
        backend.create_source_version({
            "version_id": version_id, "source_id": source_id,
            "hash": content_hash, "captured_at": now, "diff_summary": "content hash changed",
        })

    capture_date = date.today().isoformat()
    for r in records:
        # Lineage every normalized record must carry (F02 §Run logging / schema §4).
        r["source_record_id"] = source_id
        r["capture_date"] = capture_date
        r.setdefault("extraction_confidence", connector.default_extraction_confidence)
        r["parser_version_id"] = parser_version_id
    connector.upsert(records)

    return status
