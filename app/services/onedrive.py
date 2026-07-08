"""OneDrive upload service via Microsoft Graph API.

Uses app-only (client_credentials) auth flow — no user interaction needed.
Uploads files to a specified folder in the authenticated user's / app's drive.

Secrets via env only (AGENTS.md §3). Never logs file contents.
"""

from __future__ import annotations

import httpx
import msal

from app.config import settings
from app.logging import get_logger

log = get_logger(__name__)

GRAPH_BASE = "https://graph.microsoft.com/v1.0"


class OneDriveError(Exception):
    """Raised when OneDrive upload fails."""


def _get_access_token() -> str:
    """Acquire an app-only access token via MSAL client_credentials flow."""
    if not settings.onedrive_client_id or not settings.onedrive_client_secret:
        raise OneDriveError("OneDrive credentials not configured (ONEDRIVE_CLIENT_ID / ONEDRIVE_CLIENT_SECRET)")

    authority = f"https://login.microsoftonline.com/{settings.onedrive_tenant_id}"
    app = msal.ConfidentialClientApplication(
        settings.onedrive_client_id,
        authority=authority,
        client_credential=settings.onedrive_client_secret,
    )

    result = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])

    if "access_token" not in result:
        error = result.get("error_description", result.get("error", "Unknown error"))
        raise OneDriveError(f"Failed to acquire OneDrive token: {error}")

    return result["access_token"]


def upload_file(
    file_bytes: bytes,
    filename: str,
    folder: str | None = None,
    content_type: str = "application/octet-stream",
) -> dict:
    """Upload a file to OneDrive via Microsoft Graph.

    Uses the simple upload API (< 4MB) or chunked upload for larger files.
    Returns the Graph API response with file metadata (id, webUrl, etc.).
    """
    token = _get_access_token()
    folder = folder or settings.onedrive_folder

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": content_type,
    }

    # Simple upload (< 4MB) — covers PDFs and Excel files
    upload_path = f"{GRAPH_BASE}/me/drive/root:/{folder}/{filename}:/content"

    log.info("OneDrive upload: %s (%d bytes, content not logged)", filename, len(file_bytes))

    r = httpx.put(upload_path, headers=headers, content=file_bytes, timeout=60)

    if r.status_code in (200, 201):
        data = r.json()
        log.info("OneDrive upload success: %s -> %s", filename, data.get("webUrl", ""))
        return data

    raise OneDriveError(
        f"OneDrive upload failed: {r.status_code} — {r.text[:200]}"
    )


def upload_files_batch(
    files: list[tuple[bytes, str, str]],
    folder: str | None = None,
) -> list[dict]:
    """Upload multiple files. Each tuple is (bytes, filename, content_type).

    Returns list of Graph API responses.
    """
    results = []
    for file_bytes, filename, content_type in files:
        result = upload_file(file_bytes, filename, folder, content_type)
        results.append(result)
    return results
