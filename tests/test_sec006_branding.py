"""SEC-006: partner branding must not enable CSS injection or unsafe logo URLs.

`_branding_band` interpolates partner `brand_color` into a CSS `style="..."` and
`logo_url` into `<img src="...">`. Both render paths (WeasyPrint and the live
Playwright/Chromium `set_content` path) consume this same HTML, so sanitizing at
the source must:

  1. Reject any `brand_color` that isn't a strict hex / rgb()/rgba() color
     (blocking `}`-breakout and CSS-property/at-rule injection) and fall back to
     the default color.
  2. Reject any `logo_url` that isn't https + SSRF-safe (dropping javascript:,
     data:, http:, file:, relative, and private/loopback/link-local hosts).
"""

from unittest import mock

from app.services.report.renderer import (
    _DEFAULT_BRAND_COLOR,
    _branding_band,
    _safe_brand_color,
    _safe_logo_url,
)


def _band(**overrides) -> str:
    branding = {"partner_id": "p1", "partner_name": "Acme"}
    branding.update(overrides)
    return _branding_band(branding)


# --------------------------------------------------------------------------- #
# brand_color                                                                  #
# --------------------------------------------------------------------------- #

def test_css_breakout_color_is_not_emitted():
    payload = "red;} body{display:none}"
    band = _band(brand_color=payload)
    assert payload not in band
    assert "display:none" not in band
    assert "body{" not in band
    # Falls back to the default color.
    assert _DEFAULT_BRAND_COLOR in band


def test_import_breakout_color_is_not_emitted():
    payload = "#fff;}@import url(x)"
    band = _band(brand_color=payload)
    assert "@import" not in band
    assert payload not in band
    assert _DEFAULT_BRAND_COLOR in band


def test_angle_bracket_color_is_not_emitted():
    payload = "#fff<script>alert(1)</script>"
    band = _band(brand_color=payload)
    assert "<script>" not in band
    assert _DEFAULT_BRAND_COLOR in band


def test_valid_hex_color_is_used():
    band = _band(brand_color="#1a2b3c")
    assert "#1a2b3c" in band
    assert _DEFAULT_BRAND_COLOR not in band


def test_valid_short_hex_color_is_used():
    assert _safe_brand_color("#abc") == "#abc"


def test_valid_hex8_color_is_used():
    assert _safe_brand_color("#1a2b3c4d") == "#1a2b3c4d"


def test_valid_rgb_color_is_used():
    band = _band(brand_color="rgb(10,20,30)")
    assert "rgb(10,20,30)" in band


def test_valid_rgba_color_is_used():
    assert _safe_brand_color("rgba(10, 20, 30, 0.5)") == "rgba(10, 20, 30, 0.5)"


def test_rgb_with_expression_is_rejected():
    # numeric args only — no expression()/var()/calc() smuggling
    assert _safe_brand_color("rgb(expression(alert(1)),0,0)") == _DEFAULT_BRAND_COLOR


def test_non_string_color_falls_back():
    assert _safe_brand_color(None) == _DEFAULT_BRAND_COLOR
    assert _safe_brand_color(123) == _DEFAULT_BRAND_COLOR


# --------------------------------------------------------------------------- #
# logo_url                                                                     #
# --------------------------------------------------------------------------- #

def test_javascript_logo_dropped():
    band = _band(logo_url="javascript:alert(1)")
    assert "javascript:" not in band
    assert "<img" not in band


def test_data_logo_dropped():
    band = _band(logo_url="data:text/html,<script>alert(1)</script>")
    assert "data:" not in band
    assert "<img" not in band


def test_http_logo_dropped():
    band = _band(logo_url="http://cdn.example.com/logo.png")
    assert "<img" not in band
    assert "http://" not in band


def test_file_logo_dropped():
    band = _band(logo_url="file:///etc/passwd")
    assert "<img" not in band
    assert "file:" not in band


def test_relative_logo_dropped():
    band = _band(logo_url="/logo.png")
    assert "<img" not in band


def test_metadata_host_logo_dropped():
    # 169.254.169.254 is https-schemed but resolves to a link-local/metadata IP.
    band = _band(logo_url="https://169.254.169.254/logo.png")
    assert "<img" not in band
    assert "169.254.169.254" not in band


def test_ssrf_validation_error_drops_logo_not_crash():
    # If the SSRF validator raises for ANY reason (block OR network failure),
    # the logo is dropped and the render does not crash.
    with mock.patch(
        "app.services.intake.ssrf.resolve_and_validate",
        side_effect=RuntimeError("network down"),
    ):
        assert _safe_logo_url("https://cdn.example.com/logo.png") is None
        band = _band(logo_url="https://cdn.example.com/logo.png")
    assert "<img" not in band


def test_valid_https_logo_emitted():
    # Bypass the network check to assert the emit path for a valid https URL.
    with mock.patch(
        "app.services.intake.ssrf.resolve_and_validate",
        return_value=("https://cdn.example.com/logo.png", "93.184.216.34", 443),
    ):
        url = _safe_logo_url("https://cdn.example.com/logo.png")
        band = _band(logo_url="https://cdn.example.com/logo.png")
    assert url == "https://cdn.example.com/logo.png"
    assert '<img src="https://cdn.example.com/logo.png"' in band


def test_non_string_logo_dropped():
    assert _safe_logo_url(None) is None
    assert _safe_logo_url(1234) is None
