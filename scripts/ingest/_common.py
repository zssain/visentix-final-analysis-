"""Shared helpers for all ingest scripts.

Mirrors the Supabase access pattern in scripts/reclassify_other.py exactly:
dotenv_values → URL / KEY / H dict → httpx calls with service-role headers.

Usage (from any ingest script):
    from scripts.ingest._common import (
        URL, H, sha256_text, upsert, start_run, finish_run, clean_html,
    )
"""

import hashlib
import logging
import time
import uuid

import httpx
from dotenv import dotenv_values

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("ingest")

CONFIG = dotenv_values(".env")
URL = CONFIG["SUPABASE_URL"]
KEY = CONFIG["SUPABASE_SERVICE_ROLE_KEY"]
H = {"apikey": KEY, "Authorization": f"Bearer {KEY}"}

# External data-source API keys
GOVINFO_API_KEY = CONFIG.get("GOVINFO_API_KEY", "")
COURTLISTENER_TOKEN = CONFIG.get("COURTLISTENER_TOKEN", "")
OPENSTATES_API_KEY = CONFIG.get("OPENSTATES_API_KEY", "")


def sha256_text(s: str) -> str:
    """Return the hex SHA-256 digest of a string."""
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def upsert(table: str, rows: list[dict], on_conflict: str) -> int:
    """POST rows to a Supabase table with merge-duplicates upsert.

    Retries up to 3 times on 5xx. Logs and returns 0 on 4xx (never raises).
    Returns the number of rows sent on success.
    """
    headers = {
        **H,
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=minimal",
    }
    url = f"{URL}/rest/v1/{table}?on_conflict={on_conflict}"

    for attempt in range(3):
        try:
            r = httpx.post(url, headers=headers, json=rows, timeout=30)
            if r.status_code < 300:
                return len(rows)
            if 400 <= r.status_code < 500:
                log.warning(
                    "upsert %s → %d: %s", table, r.status_code, r.text[:200]
                )
                return 0
            # 5xx — retry
            log.warning(
                "upsert %s → %d (attempt %d/3): %s",
                table, r.status_code, attempt + 1, r.text[:200],
            )
        except (httpx.ReadTimeout, httpx.RemoteProtocolError) as exc:
            log.warning("upsert %s network error (attempt %d/3): %s", table, attempt + 1, exc)
        if attempt < 2:
            time.sleep(2 ** attempt)

    log.error("upsert %s failed after 3 attempts", table)
    return 0


def start_run(source_name: str, run_type: str = "full") -> str:
    """Insert an ingestion_run row with status='partial'. Returns the run_id."""
    run_id = str(uuid.uuid4())
    row = {
        "run_id": run_id,
        "source_name": source_name,
        "run_type": run_type,
        "status": "partial",
    }
    headers = {
        **H,
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }
    r = httpx.post(f"{URL}/rest/v1/ingestion_run", headers=headers, json=row, timeout=15)
    if r.status_code >= 300:
        log.error("start_run failed: %d %s", r.status_code, r.text[:200])
    log.info("ingestion run started: %s (%s / %s)", run_id[:12], source_name, run_type)
    return run_id


def finish_run(
    run_id: str,
    inserted: int = 0,
    updated: int = 0,
    status: str = "ok",
    notes: str = "",
) -> None:
    """PATCH the ingestion_run row with final counts and status."""
    headers = {
        **H,
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }
    payload = {
        "finished_at": "now()",
        "rows_inserted": inserted,
        "rows_updated": updated,
        "status": status,
        "notes": notes,
    }
    r = httpx.patch(
        f"{URL}/rest/v1/ingestion_run?run_id=eq.{run_id}",
        headers=headers,
        json=payload,
        timeout=15,
    )
    if r.status_code >= 300:
        log.error("finish_run failed: %d %s", r.status_code, r.text[:200])
    log.info(
        "ingestion run finished: %s → %s (ins=%d upd=%d)",
        run_id[:12], status, inserted, updated,
    )


def clean_html(html: str) -> str:
    """Convert HTML to plain text, stripping boilerplate tags.

    Tries to reuse app.services.intake.extract._html_to_text if importable;
    falls back to a minimal BeautifulSoup strip of script/style/nav.
    """
    try:
        from app.services.intake.extract import _html_to_text
        return _html_to_text(html)
    except Exception:
        pass

    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup.find_all(["script", "style", "nav", "header", "footer"]):
            tag.decompose()
        return soup.get_text(separator="\n", strip=True)
    except ImportError:
        import re
        text = re.sub(r"<(script|style|nav|header|footer)[^>]*>.*?</\1>", "", html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)
        return re.sub(r"\s+", " ", text).strip()
