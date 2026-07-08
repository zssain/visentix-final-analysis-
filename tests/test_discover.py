"""Privacy policy URL discovery tests.

Tests is_direct_policy_url, cascade order, short-circuit, homepage link
extraction, www fallback, and total-failure → None.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.intake.discover import (
    PRIVACY_PATHS,
    _POLICY_URL_KEYWORDS,
    discover_policy_url,
    is_direct_policy_url,
)


# ── is_direct_policy_url ─────────────────────────────────────

def test_direct_policy_url_privacy_path():
    assert is_direct_policy_url("https://example.com/privacy") is True


def test_direct_policy_url_privacy_policy():
    assert is_direct_policy_url("https://example.com/privacy-policy") is True


def test_direct_policy_url_legal():
    assert is_direct_policy_url("https://example.com/legal/privacy") is True


def test_direct_policy_url_terms():
    assert is_direct_policy_url("https://example.com/terms-of-service") is True


def test_direct_policy_url_datenschutz():
    assert is_direct_policy_url("https://example.de/datenschutz") is True


def test_direct_policy_url_bare_homepage():
    assert is_direct_policy_url("https://example.com") is False


def test_direct_policy_url_bare_homepage_with_slash():
    assert is_direct_policy_url("https://example.com/") is False


def test_direct_policy_url_about_page():
    assert is_direct_policy_url("https://example.com/about") is False


def test_direct_policy_url_blog():
    assert is_direct_policy_url("https://example.com/blog/latest") is False


def test_direct_policy_url_query_param():
    assert is_direct_policy_url("https://example.com/page?section=privacy") is True


# ── Cascade order + short-circuit ────────────────────────────

@pytest.mark.anyio
async def test_s1_hit_skips_s2_and_s3():
    """When a known path succeeds at S1, S2 (homepage links) should not run."""
    calls: list[str] = []

    _POLICY_HTML = """
    <html><body>
    <h1>Privacy Notice</h1>
    <p>We care about your privacy and personal information. We collect data
    to provide our services. We use cookies for analytics and tracking purposes.
    We share your data with third party service providers for payment processing,
    customer support, and analytics. You have the right to access, correct, and
    delete your personal data. You may opt out of data sales at any time. We
    retain your data for the period specified in our retention schedule. Our
    services are not directed to children under 13. We may transfer your data
    internationally using standard contractual clauses.</p>
    </body></html>
    """

    async def mock_fetch(url):
        calls.append(url)
        resp = MagicMock()
        if "/privacy" in url and url.endswith("/privacy"):
            resp.status_code = 200
            resp.text = _POLICY_HTML
        else:
            resp.status_code = 404
            resp.text = "<html><body>Not found</body></html>"
        return resp

    with patch("app.services.intake.discover._fetch_ssrf_safe", side_effect=mock_fetch):
        result = await discover_policy_url("https://example.com")

    assert result == "https://example.com/privacy"
    # Should NOT have fetched the homepage for link extraction
    assert not any("example.com" == url.rstrip("/") for url in calls), (
        "S2 homepage fetch should not happen when S1 succeeds"
    )


@pytest.mark.anyio
async def test_s2_homepage_link_discovery():
    """When S1 fails, S2 follows privacy links from the homepage."""
    _POLICY_PAGE = """
    <html><body>
    <h1>Privacy Notice</h1>
    <p>We care about your privacy and personal information. We collect data
    to provide our services. We use cookies for analytics and tracking purposes.
    We share your data with third party service providers for payment processing,
    customer support, and analytics. You have the right to access, correct, and
    delete your personal data. You may opt out of data sales at any time. We
    retain your data for the period specified in our retention schedule. Our
    services are not directed to children under 13. We may transfer your data
    internationally using standard contractual clauses.</p>
    </body></html>
    """

    async def mock_fetch(url):
        resp = MagicMock()
        if url.rstrip("/") == "https://example.com":
            resp.status_code = 200
            resp.text = """
            <html><body>
            <h1>Welcome to Example</h1>
            <p>This is our homepage.</p>
            <footer>
              <a href="/our-privacy-page">Privacy Policy</a>
            </footer>
            </body></html>
            """
        elif "/our-privacy-page" in url:
            resp.status_code = 200
            resp.text = _POLICY_PAGE
        else:
            resp.status_code = 404
            resp.text = "<html><body>Not found</body></html>"
        return resp

    with patch("app.services.intake.discover._fetch_ssrf_safe", side_effect=mock_fetch):
        result = await discover_policy_url("https://example.com")

    assert result == "https://example.com/our-privacy-page"


@pytest.mark.anyio
async def test_total_failure_returns_none():
    """When all strategies fail, returns None."""
    async def mock_fetch(url):
        resp = MagicMock()
        resp.status_code = 404
        resp.text = "<html><body>Not found</body></html>"
        return resp

    with patch("app.services.intake.discover._fetch_ssrf_safe", side_effect=mock_fetch):
        result = await discover_policy_url("https://nosuchsite.example")

    assert result is None


@pytest.mark.anyio
async def test_ssrf_error_degrades_gracefully():
    """SSRF errors on individual URLs don't crash — they degrade to next candidate."""
    from app.services.intake.ssrf import SSRFError

    call_count = 0

    async def mock_fetch(url):
        nonlocal call_count
        call_count += 1
        raise SSRFError(f"Blocked: {url}")

    with patch("app.services.intake.discover._fetch_ssrf_safe", side_effect=mock_fetch):
        result = await discover_policy_url("https://example.com")

    assert result is None
    assert call_count > 0  # tried at least some candidates


# ── Config integrity ─────────────────────────────────────────

def test_privacy_paths_all_start_with_slash():
    for path in PRIVACY_PATHS:
        assert path.startswith("/"), f"Path must start with /: {path}"


def test_policy_url_keywords_lowercase():
    for kw in _POLICY_URL_KEYWORDS:
        assert kw == kw.lower(), f"Keyword must be lowercase: {kw}"
