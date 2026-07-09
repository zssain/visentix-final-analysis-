"""Privacy policy URL discovery — finds the policy page from a bare company URL.

Used ONLY when the submitted URL isn't already a policy link. All fetches go
through the SSRF-safe fetcher from extract.py (never raw httpx).

Discovery cascade (short-circuit on first hit, total cap 20s):
  S1: Known paths (/privacy, /privacy-policy, etc.)
  S2: Homepage link extraction (<a> containing "privacy" in href or text)
  S3: www. fallback (retry S1+S2 with www. prefix)

NOTE: This is httpx-based, so JS-only-rendered footers (e.g. React SPAs that
load the footer via client-side JS) won't be found. Playwright can be added
later behind a flag WITHOUT changing this interface.
"""

from __future__ import annotations

import asyncio
import logging
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from app.services.intake.extract import (
    _fetch_ssrf_safe,
    _html_to_text,
    looks_like_privacy_policy,
)
from app.services.intake.ssrf import SSRFError

log = logging.getLogger(__name__)

# URL path keywords that indicate a privacy policy page
_POLICY_URL_KEYWORDS = (
    "privacy", "legal", "policy", "terms", "tos", "agreement",
    "datenschutz", "confidentialite",
)

# Known privacy policy paths to try (most common first for fast short-circuit)
PRIVACY_PATHS = [
    "/privacy",
    "/privacy-policy",
    "/legal/privacy",
    "/privacy-notice",
    "/policies/privacy",
    "/about/privacy",
    "/en/privacy",
    "/us/privacy",
    "/privacy.html",
    "/legal/privacy-policy",
]

# Total time cap for the entire discovery cascade
_DISCOVERY_TIMEOUT_SECONDS = 20

# Minimum text length to consider a page a real policy
_MIN_POLICY_LENGTH = 500

# Max homepage links to follow in S2
_MAX_HOMEPAGE_LINKS = 5


def is_direct_policy_url(url: str) -> bool:
    """Check if a URL already points at a privacy policy page.

    Looks at the path + query for any policy-related keyword.
    """
    parsed = urlparse(url)
    path_and_query = (parsed.path + "?" + parsed.query).lower()
    return any(kw in path_and_query for kw in _POLICY_URL_KEYWORDS)


async def discover_policy_url(base_url: str) -> str | None:
    """Discover the privacy policy URL from a base company URL.

    Cascade: known paths → homepage links → www. fallback.
    Returns the discovered URL or None if not found.
    Caps total time at 20s. Every per-page failure degrades gracefully.
    """
    parsed = urlparse(base_url)
    scheme = parsed.scheme or "https"
    netloc = parsed.netloc or parsed.path.split("/")[0]
    base = f"{scheme}://{netloc}"

    reasons: list[str] = []

    try:
        async with asyncio.timeout(_DISCOVERY_TIMEOUT_SECONDS):
            # S1: Known paths
            result = await _try_known_paths(base, reasons)
            if result:
                log.info("Discovery S1 hit: %s (tried %d paths)", result, len(reasons))
                return result

            # S2: Homepage link extraction
            result = await _try_homepage_links(base, reasons)
            if result:
                log.info("Discovery S2 hit: %s (tried %d links)", result, len(reasons))
                return result

            # S3: www. fallback
            if not netloc.startswith("www."):
                www_base = f"{scheme}://www.{netloc}"
                result = await _try_known_paths(www_base, reasons)
                if result:
                    log.info("Discovery S3 path hit: %s", result)
                    return result

                result = await _try_homepage_links(www_base, reasons)
                if result:
                    log.info("Discovery S3 link hit: %s", result)
                    return result

    except TimeoutError:
        log.info("Discovery timed out after %ds (tried %d candidates)",
                 _DISCOVERY_TIMEOUT_SECONDS, len(reasons))
    except Exception as e:
        log.info("Discovery failed: %s (tried %d candidates)",
                 type(e).__name__, len(reasons))

    log.info("Discovery found no policy page for %s (tried %d candidates)",
             netloc, len(reasons))
    return None


async def _try_known_paths(base: str, reasons: list[str]) -> str | None:
    """S1/S3: Try known privacy paths. Returns first hit or None."""
    for path in PRIVACY_PATHS:
        candidate = base + path
        reasons.append(f"path:{candidate}")
        if await _is_policy_page(candidate):
            return candidate
    return None


async def _try_homepage_links(base: str, reasons: list[str]) -> str | None:
    """S2: Fetch homepage, extract <a> links containing 'privacy'. Returns first hit."""
    try:
        response = await _fetch_ssrf_safe(base)
        if response.status_code != 200:
            reasons.append(f"homepage:{base}:status={response.status_code}")
            return None

        soup = BeautifulSoup(response.text, "lxml")
        candidates: list[str] = []
        seen: set[str] = set()

        for a in soup.find_all("a", href=True):
            href = a["href"]
            link_text = a.get_text(strip=True).lower()

            # Check if href or link text mentions privacy
            href_lower = href.lower()
            is_privacy_link = (
                "privacy" in href_lower
                or link_text in ("privacy policy", "privacy notice", "privacy", "privacy statement")
            )

            if not is_privacy_link:
                continue

            full_url = urljoin(base, href)
            if full_url in seen:
                continue
            seen.add(full_url)

            # Validate for SSRF before adding
            try:
                from app.services.intake.ssrf import validate_url
                validate_url(full_url)
                candidates.append(full_url)
            except SSRFError:
                continue

        # Visit up to _MAX_HOMEPAGE_LINKS candidates
        for candidate in candidates[:_MAX_HOMEPAGE_LINKS]:
            reasons.append(f"link:{candidate}")
            if await _is_policy_page(candidate):
                return candidate

    except SSRFError:
        reasons.append(f"homepage:{base}:ssrf_blocked")
    except Exception as e:
        reasons.append(f"homepage:{base}:{type(e).__name__}")

    return None


async def _is_policy_page(url: str) -> bool:
    """Fetch a URL and check if it looks like a privacy policy page."""
    try:
        response = await _fetch_ssrf_safe(url)
        if response.status_code != 200:
            return False

        text = _html_to_text(response.text)
        if len(text) < _MIN_POLICY_LENGTH:
            return False

        return looks_like_privacy_policy(text)

    except (SSRFError, Exception):
        return False
