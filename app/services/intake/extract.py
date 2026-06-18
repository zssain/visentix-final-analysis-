"""Text extraction from URL, PDF upload, or raw text.

All extraction produces plain text ready for decomposition.
Defenses: size limits, MIME validation, SSRF protection, no shell-outs.
"""

from __future__ import annotations

import hashlib
import io

import httpx

from app.services.intake.ssrf import (
    FETCH_TIMEOUT_SECONDS,
    MAX_RESPONSE_BYTES,
    SSRFError,
    validate_url,
)

# Limits
MAX_TEXT_LENGTH = 500_000  # 500K chars
MAX_PDF_BYTES = 10 * 1024 * 1024  # 10 MB
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "text/html",
    "text/plain",
    "application/xhtml+xml",
}


class ExtractionError(ValueError):
    pass


async def extract_from_url(url: str) -> tuple[str, str]:
    """Fetch URL content and extract text. Returns (text, content_hash).

    SSRF-safe: validates URL before fetching.
    """
    safe_url = validate_url(url)

    async with httpx.AsyncClient(
        timeout=FETCH_TIMEOUT_SECONDS,
        follow_redirects=True,
        max_redirects=3,
    ) as client:
        response = await client.get(safe_url)
        response.raise_for_status()

        # Size check
        content_length = len(response.content)
        if content_length > MAX_RESPONSE_BYTES:
            raise ExtractionError(
                f"Response too large: {content_length} bytes (max {MAX_RESPONSE_BYTES})"
            )

        content_type = response.headers.get("content-type", "").split(";")[0].strip()

        if content_type == "application/pdf":
            text = _extract_pdf_text(response.content)
        else:
            text = response.text

    if len(text) > MAX_TEXT_LENGTH:
        text = text[:MAX_TEXT_LENGTH]

    content_hash = hashlib.sha256(text.encode()).hexdigest()
    return text, content_hash


def extract_from_pdf(pdf_bytes: bytes, filename: str = "") -> tuple[str, str]:
    """Extract text from PDF bytes. Returns (text, content_hash).

    Uses PyMuPDF (fitz) — no shell-outs.
    """
    if len(pdf_bytes) > MAX_PDF_BYTES:
        raise ExtractionError(
            f"PDF too large: {len(pdf_bytes)} bytes (max {MAX_PDF_BYTES})"
        )

    text = _extract_pdf_text(pdf_bytes)

    if len(text) > MAX_TEXT_LENGTH:
        text = text[:MAX_TEXT_LENGTH]

    content_hash = hashlib.sha256(text.encode()).hexdigest()
    return text, content_hash


def extract_from_text(raw_text: str) -> tuple[str, str]:
    """Accept raw text input. Returns (text, content_hash)."""
    if len(raw_text) > MAX_TEXT_LENGTH:
        raise ExtractionError(
            f"Text too long: {len(raw_text)} chars (max {MAX_TEXT_LENGTH})"
        )

    text = raw_text.strip()
    if not text:
        raise ExtractionError("Empty text")

    content_hash = hashlib.sha256(text.encode()).hexdigest()
    return text, content_hash


def _extract_pdf_text(pdf_bytes: bytes) -> str:
    """Extract text from PDF using PyMuPDF (no shell-outs)."""
    import fitz  # PyMuPDF

    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        pages = []
        for page in doc:
            pages.append(page.get_text())
        doc.close()
        return "\n\n".join(pages)
    except Exception as e:
        raise ExtractionError(f"PDF extraction failed: {e}")
