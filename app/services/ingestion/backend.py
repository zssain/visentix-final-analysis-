"""SupabaseBackend — the production `Backend` (PostgREST + Storage, service-role).

Writes source_record / source_version / parser_version / ingestion_run and stores
raw bytes in the `raw-artifacts` bucket WITHOUT overwriting existing objects.
Never logs document text; never prints secrets.
"""
from __future__ import annotations

import logging
from uuid import uuid4

import httpx

from app.config import settings
from app.db import get_service_headers
from app.services.ingestion.base import Backend

log = logging.getLogger(__name__)


class SupabaseBackend(Backend):
    def __init__(self, timeout: float = 30.0):
        self._url = settings.supabase_url
        self._timeout = timeout

    def _h(self, **extra) -> dict:
        return {**get_service_headers(), **extra}

    def _rest(self, path: str) -> str:
        return f"{self._url}/rest/v1/{path}"

    # ── source_record / source_version ──────────────────────────────
    def find_source_record(self, source_id: str) -> dict | None:
        r = httpx.get(self._rest(f"source_record?select=*&source_id=eq.{source_id}&limit=1"),
                      headers=self._h(), timeout=self._timeout)
        rows = r.json() if r.status_code < 300 else []
        return rows[0] if rows else None

    def latest_version_hash(self, source_id: str) -> str | None:
        r = httpx.get(self._rest(
            f"source_version?select=hash&source_id=eq.{source_id}&order=captured_at.desc&limit=1"),
            headers=self._h(), timeout=self._timeout)
        rows = r.json() if r.status_code < 300 else []
        return rows[0]["hash"] if rows else None

    def version_count(self, source_id: str) -> int:
        r = httpx.get(self._rest(f"source_version?select=version_id&source_id=eq.{source_id}&limit=0"),
                      headers=self._h(Prefer="count=exact"), timeout=self._timeout)
        return int(r.headers.get("content-range", "*/0").split("/")[-1])

    def create_source_record(self, row: dict) -> None:
        r = httpx.post(self._rest("source_record"),
                       headers=self._h(**{"Content-Type": "application/json", "Prefer": "return=minimal"}),
                       json=row, timeout=self._timeout)
        if r.status_code >= 300:
            raise RuntimeError(f"source_record insert failed: HTTP {r.status_code}")

    def create_source_version(self, row: dict) -> None:
        r = httpx.post(self._rest("source_version"),
                       headers=self._h(**{"Content-Type": "application/json", "Prefer": "return=minimal"}),
                       json=row, timeout=self._timeout)
        if r.status_code >= 300:
            raise RuntimeError(f"source_version insert failed: HTTP {r.status_code}")

    # ── raw-artifacts storage (never overwrite) ─────────────────────
    def store_raw(self, path: str, data: bytes, content_type: str) -> str:
        bucket, _, obj = path.partition("/")           # path = "raw-artifacts/..."
        url = f"{self._url}/storage/v1/object/{bucket}/{obj}"
        # x-upsert defaults to false → an existing object is NOT overwritten.
        r = httpx.post(url, headers=self._h(**{"Content-Type": content_type or "application/octet-stream",
                                               "x-upsert": "false"}),
                       content=data, timeout=self._timeout)
        if r.status_code in (200, 201):
            return "created"
        body = r.text or ""
        if r.status_code == 409 or "Duplicate" in body or "already exists" in body:
            return "reused"          # object already present — reuse, never overwrite
        raise RuntimeError(f"raw store failed at {path}: HTTP {r.status_code}")

    # ── parser_version ──────────────────────────────────────────────
    def register_parser_version(self, family: str, version: str, description: str) -> str:
        r = httpx.post(
            self._rest("parser_version?on_conflict=family,version"),
            headers=self._h(**{"Content-Type": "application/json",
                               "Prefer": "resolution=merge-duplicates,return=representation"}),
            json={"parser_version_id": str(uuid4()), "family": family,
                  "version": version, "description": description},
            timeout=self._timeout)
        if r.status_code < 300 and r.json():
            return r.json()[0]["parser_version_id"]
        # fallback: read the existing row
        g = httpx.get(self._rest(
            f"parser_version?select=parser_version_id&family=eq.{family}&version=eq.{version}&limit=1"),
            headers=self._h(), timeout=self._timeout)
        rows = g.json() if g.status_code < 300 else []
        if not rows:
            raise RuntimeError("parser_version registration failed")
        return rows[0]["parser_version_id"]

    # ── ingestion_run ───────────────────────────────────────────────
    def create_ingestion_run(self, row: dict) -> str:
        run_id = str(uuid4())
        r = httpx.post(self._rest("ingestion_run"),
                       headers=self._h(**{"Content-Type": "application/json", "Prefer": "return=minimal"}),
                       json={"run_id": run_id, **row}, timeout=self._timeout)
        if r.status_code >= 300:
            raise RuntimeError(f"ingestion_run insert failed: HTTP {r.status_code}")
        return run_id

    def finish_ingestion_run(self, run_id: str, updates: dict) -> None:
        httpx.patch(self._rest(f"ingestion_run?run_id=eq.{run_id}"),
                    headers=self._h(**{"Content-Type": "application/json", "Prefer": "return=minimal"}),
                    json=updates, timeout=self._timeout)
