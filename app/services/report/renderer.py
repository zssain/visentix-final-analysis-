"""Report PDF renderer — executive design over honest data.

Renderer selection via RENDERER env var:
  - "weasyprint" (default, active): weasyprint HTML→PDF
  - "playwright": headless Chromium via Playwright (requires install)

NOTE (2026-06-29): Playwright install blocked by network egress restrictions
(pypi.org unreachable). weasyprint is the active renderer. When Playwright
becomes available, set RENDERER=playwright and run:
    pip install playwright && playwright install chromium

The renderer renders ONLY our own report HTML (set_content, not goto) —
never an arbitrary URL. No SSRF via the renderer.

PHASE 6 (report design): `render_html()` is the SINGLE render seam. It turns the
12-section payload into the executive artefact — cover, running page chrome, KPI
cards, inline-SVG gauges, comparison bars, the regulator heat grid, callouts, and
a back cover. Constraints honoured:
  * Byte-identical determinism — no datetime.now()/random/remote fetch; the CSS
    and the brand wordmark are read from disk at import and base64-inlined, so a
    frozen snapshot re-renders identically (test_pdf_determinism).
  * Honest absence — every missing value renders "Not recorded" / "Insufficient
    data" / "Not yet measured", NEVER a 0 or a fabricated bar (Rule / DATA thesis).
  * Guardrail stays upstream — prose is enforced in reports._assemble_from_live
    before it ever reaches here; restyling does not route around it.
  * Partner branding is header-only (F20): the body bytes are identical branded
    vs unbranded apart from the injected band; SEC-006 colour/logo validation kept.
  * Placeholder leak fixed — any un-substituted `{token}` in generated prose (the
    recommendation_library `{ai_use_cases}` bug) is stripped before render.
"""

from __future__ import annotations

import base64
import math
import re
from pathlib import Path

from app.services.report.assembly import ReportPayload, ReportSection

# ── Design assets (read once at import → deterministic) ─────────────────────
_HERE = Path(__file__).resolve().parent
_ASSETS = _HERE / "assets"


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _data_uri(name: str, mime: str) -> str:
    """Base64 data URI for a committed asset. base64-inline (not file://) keeps
    the render byte-identical with no filesystem-timing dependency (Rule 4)."""
    try:
        raw = (_ASSETS / name).read_bytes()
    except OSError:
        return ""
    return f"data:{mime};base64," + base64.b64encode(raw).decode("ascii")


_CSS = _read_text(_HERE / "report.css")
# Reversed/white wordmark for the dark cover + back panels. If the asset is
# missing the cover falls back to a text wordmark (documented owner-asset gap).
_WORDMARK_DARK = _data_uri("wordmark-dark.png", "image/png")

# ── Risk ramp (one ramp, used everywhere) ───────────────────────────────────
_RAMP = {
    "low": "#2E9E6B",
    "moderate": "#E9A23B",
    "high": "#D9534F",
    "elevated": "#C0392B",
}

_DOMAIN_LABELS = {
    "ai_automated_decisions": "AI &amp; Automated Decisions",
    "children_teens": "Children &amp; Teens",
    "consumer_rights": "Consumer Rights",
    "cross_border": "Cross-Border Transfers",
    "data_sharing": "Data Sharing",
    "retention": "Retention",
    "sensitive_data": "Sensitive Data",
    "tracking_cookies": "Tracking &amp; Cookies",
}

# One polarity registry drives dashboard colour and direction copy. ``inverted``
# is the existing renderer convention: higher values are better when true.
_DASHBOARD_METRICS = (
    {"key": "overall_intelligence", "label": "Overall Intelligence", "inverted": True},
    {"key": "disclosure_maturity", "label": "Disclosure Maturity", "inverted": True},
    {"key": "transparency", "label": "Transparency", "inverted": True},
    {"key": "ai_transparency", "label": "AI Governance", "inverted": True},
    {"key": "regulatory_exposure", "label": "Regulatory Exposure", "inverted": False},
    {"key": "compound_risk", "label": "Compound Risk", "inverted": False},
)


def _direction(inverted: bool) -> str:
    return "Maturity — higher is better" if inverted else "Exposure — lower is better"

def _domain_html(dom) -> str:
    """Safe, human display name for a taxonomy domain. _DOMAIN_LABELS values are
    already entity-escaped; unknown domains are escaped without guessing a label."""
    lbl = _DOMAIN_LABELS.get(dom)
    if lbl:
        return lbl
    return _esc(dom or "")


_SECTION_KICKERS = {
    2: "Executive Summary",
    3: "Risk Posture",
    4: "Peer Benchmarking",
    5: "Regulatory Landscape",
    6: "Disclosure Findings",
    7: "Compound Exposure",
    8: "Language Benchmarking",
    9: "Action Plan",
    10: "Prioritisation",
    11: "Evidence &amp; Lineage",
    12: "Forward View",
}

# ── Presentation grouping (mirrors web/src/report/sectionGroups.ts) ──────────
# The report is PRESENTED as six reader-facing parts + an appendix. The frozen
# payload still carries its original twelve blocks with their original numbers —
# grouping is presentation only, so every stored snapshot still regenerates
# identically (Hard Rule 6) and the per-block `id="section-N"` anchors survive.
# Keep this list in step with sectionGroups.ts or the PDF stops matching the
# interactive report (F05 PDF parity).
_REPORT_PARTS: list[tuple[int | None, str, str, list[int]]] = [
    (2, "Executive Summary", "", [2]),
    (3, "Where You Stand",
     "Every score in this assessment, what each one measures, and how it compares "
     "with the peer cohort.", [3, 4, 5, 7]),
    (4, "What We Found",
     "The specific disclosure gaps identified in this notice, each with the "
     "evidence behind it.", [6]),
    (5, "What Peers Do, What We Recommend",
     "How comparable organizations word the areas where this notice differs, and "
     "what we suggest &mdash; in priority order.", [8, 9, 10]),
    (6, "What&rsquo;s Changing",
     "Movement since the last assessment, and the regulatory developments worth "
     "watching.", [12]),
    (None, "Appendix &middot; Traceability &amp; Method",
     "The machinery behind every figure above: snapshot, formula versions, cohort "
     "construction, and sources.", [11]),
]


# SEC-006: default brand color used whenever the partner-supplied value fails
# strict validation. Must NEVER be replaced by an unvalidated raw value.
_DEFAULT_BRAND_COLOR = "#0f3460"

# SEC-006: strict CSS color allowlist. Only hex (#rgb / #rrggbb / #rrggbbaa)
# and rgb()/rgba() with numeric args. Anchored to the whole string so a payload
# like "red;} body{display:none}" or "#fff;}@import url(x)" cannot match — the
# raw value is dropped and the default is used instead. This blocks `}`-breakout
# and any CSS-property/at-rule injection.
_HEX_COLOR_RE = re.compile(r"\A#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})\Z")
_RGB_COLOR_RE = re.compile(
    r"\Argba?\(\s*"
    r"[0-9]{1,3}(?:\.[0-9]+)?%?\s*,\s*"
    r"[0-9]{1,3}(?:\.[0-9]+)?%?\s*,\s*"
    r"[0-9]{1,3}(?:\.[0-9]+)?%?"
    r"(?:\s*,\s*(?:0|1|0?\.[0-9]+|[0-9]{1,3}%))?"
    r"\s*\)\Z"
)

# Any un-substituted template token, e.g. `{ai_use_cases}`, that leaked from a
# body_template into generated prose. Braces + lowercase identifier only, so it
# never touches real customer text (which has no `{word}` tokens).
_PLACEHOLDER_TOKEN = r"\{[a-z][a-z0-9_]*\}"
_PLACEHOLDER_RE = re.compile(_PLACEHOLDER_TOKEN)
# Drop a governing connector together with its leaked token ("use of {x}," →
# "use,") so removing the clause reads cleanly rather than leaving a dangling
# preposition (Part C §10 — "drop the clause cleanly").
_PLACEHOLDER_CLAUSE_RE = re.compile(
    r"\s*\b(?:of|for|to|with|in|on|including|affecting|regarding|around|and|or)\s+"
    + _PLACEHOLDER_TOKEN,
    re.IGNORECASE,
)


def _safe_brand_color(value) -> str:
    """Return a strictly-validated CSS color, or the safe default.

    SEC-006: only #rgb/#rrggbb/#rrggbbaa hex and rgb()/rgba() with numeric args
    are accepted. Anything else (including any string containing CSS-breakout
    characters like `}`, `;`, `@`, or `<`) is rejected and the default is used.
    The returned value is safe to interpolate directly into a CSS context.
    """
    if not isinstance(value, str):
        return _DEFAULT_BRAND_COLOR
    candidate = value.strip()
    if _HEX_COLOR_RE.match(candidate) or _RGB_COLOR_RE.match(candidate):
        return candidate
    return _DEFAULT_BRAND_COLOR


def _safe_logo_url(value) -> str | None:
    """Return an https-only, SSRF-safe logo URL, or None to drop the logo.

    SEC-006: allowlist the scheme to `https:` ONLY (rejecting javascript:,
    data:, http:, file:, and relative URLs) and reject any host that resolves to
    a private/loopback/link-local/metadata address (reusing the intake SSRF
    validator). On ANY rejection — including a network/resolution failure during
    validation — the logo is dropped rather than crashing the render.
    """
    if not isinstance(value, str):
        return None
    candidate = value.strip()
    if not candidate:
        return None

    from urllib.parse import urlparse

    try:
        scheme = urlparse(candidate).scheme.lower()
    except ValueError:
        return None
    if scheme != "https":
        return None

    # Host must not resolve to a private/loopback/link-local/metadata address.
    # Never let a validation failure (SSRF block OR network error) crash render.
    try:
        from app.services.intake.ssrf import resolve_and_validate

        resolve_and_validate(candidate)
    except Exception:
        return None

    return candidate


def _branding_band(branding: dict | None) -> str:
    """Partner branding header band — render-only, added ABOVE the report body.

    Injects the partner name + logo + a brand-color stripe. It NEVER touches any
    section content — no number or wording in the report body changes (F20
    MUST NOT). Deterministic given the (frozen) branding dict, so the branded
    PDF is byte-identical per snapshot.

    SEC-006: `brand_color` is strictly validated (CSS-injection safe) and
    `logo_url` is https-only + SSRF-checked; unsafe values are dropped rather
    than emitted, so both the WeasyPrint and Playwright/Chromium render paths
    (which consume this same assembled HTML) are safe.
    """
    if not branding or not branding.get("partner_id"):
        return ""
    color = _safe_brand_color(branding.get("brand_color") or _DEFAULT_BRAND_COLOR)
    name = _esc(branding.get("partner_name") or "")
    logo = _safe_logo_url(branding.get("logo_url"))
    logo_html = (
        f'<span class="bb-logo"><img src="{_esc(logo)}" alt="" style="max-height:34px;"></span>'
        if logo else ""
    )
    return (
        f'<div class="brand-band" style="border-top:4px solid {color};">'
        f'{logo_html}'
        f'<span class="bb-name" style="color:{color};">{name}</span>'
        f'<span class="bb-via">Delivered via Visentix</span>'
        f'</div>'
    )


# ── Value helpers (honest absence is the default) ───────────────────────────

def _num(value):
    """Return value as float if it is a real number, else None.

    bool is rejected (True/False are not scores). None / missing / non-numeric
    all collapse to None so the caller renders an honest-absence state instead of
    a fabricated 0."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _fmt(value, absent: str = "Not recorded", decimals: int = 1) -> str:
    v = _num(value)
    if v is None:
        return absent
    return f"{v:.{decimals}f}"


def _pct(value, maxv: float = 100.0) -> float:
    v = _num(value)
    if v is None or maxv <= 0:
        return 0.0
    return round(max(0.0, min(v / maxv, 1.0)) * 100.0, 2)


def _ramp_key(value, invert: bool = False) -> str:
    """Map a 0–100 value to a risk-ramp band. `invert=True` for metrics where
    HIGHER is BETTER (maturity, transparency) so a high score reads green."""
    v = _num(value)
    if v is None:
        return "na"
    if invert:
        v = 100.0 - v
    if v < 25:
        return "low"
    if v < 50:
        return "moderate"
    if v < 75:
        return "high"
    return "elevated"


def _ramp_hex(value, invert: bool = False) -> str:
    return _RAMP.get(_ramp_key(value, invert), "#AEBBC9")


def _ordinal(value) -> str:
    """Percentile with an ordinal suffix, e.g. 88.1 → '88.1th', 91.0 → '91st'."""
    v = _num(value)
    if v is None:
        return "Not recorded"
    n = int(v)
    if 10 <= n % 100 <= 20:
        suf = "th"
    else:
        suf = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    body = f"{v:.1f}" if abs(v - n) > 1e-9 else f"{n}"
    return f"{body}{suf}"


def _strip_placeholders(text: str) -> str:
    """Remove any un-substituted `{token}` (the recommendation_library
    `{ai_use_cases}`/`{sensitive_data_types}` leak) and tidy the seams so a
    literal template brace never reaches a customer (Part C §10 / Part E)."""
    if not isinstance(text, str):
        return ""
    out = _PLACEHOLDER_CLAUSE_RE.sub("", text)  # "use of {x}," → "use,"
    out = _PLACEHOLDER_RE.sub("", out)          # any remaining bare {token}
    out = re.sub(r"\s*(?:\(\s*\)|\[\s*\])", "", out)  # emptied () / []
    out = re.sub(r"\s+([,.;:)])", r"\1", out)   # " ," → ","
    out = re.sub(r"([(])\s+", r"\1", out)       # "( " → "("
    out = re.sub(r"\s{2,}", " ", out)           # collapse doubled spaces
    return out.strip()


def find_unresolved_template_tokens(text: str) -> list[str]:
    """Return unresolved authored-template tokens without mutating the prose."""
    if not isinstance(text, str):
        return []
    return sorted(set(_PLACEHOLDER_RE.findall(text)))


def _esc(text) -> str:
    """HTML-escape text."""
    return (str(text)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))


def _prose(text) -> str:
    """Escape + placeholder-strip a customer-facing free-text field."""
    return _esc(_strip_placeholders(text if isinstance(text, str) else ""))


# ── SVG components ──────────────────────────────────────────────────────────

def _polar(cx: float, cy: float, r: float, deg: float) -> tuple[float, float]:
    a = math.radians(deg)
    return round(cx + r * math.cos(a), 2), round(cy - r * math.sin(a), 2)


def _arc(cx: float, cy: float, r: float, start_deg: float, end_deg: float) -> str:
    """SVG arc path from start_deg to end_deg. 0°=right, 90°=top, 180°=left;
    sweeps clockwise over the top (decreasing angle)."""
    x0, y0 = _polar(cx, cy, r, start_deg)
    x1, y1 = _polar(cx, cy, r, end_deg)
    large = 1 if abs(start_deg - end_deg) > 180 else 0
    return f"M{x0},{y0} A{r},{r} 0 {large} 1 {x1},{y1}"


def _gauge(value, caption: str, invert: bool = False) -> str:
    """A 180° gauge dial as inline SVG (WeasyPrint renders SVG; JS charts won't).
    Missing value → a muted empty dial reading 'Not recorded' — never a 0 arc."""
    cap = caption  # caption is pre-escaped by callers
    v = _num(value)
    bg = _arc(50, 48, 40, 180, 0)
    if v is None:
        return (
            f'<svg class="gauge" viewBox="0 0 100 60" preserveAspectRatio="xMidYMid meet">'
            f'<path d="{bg}" fill="none" stroke="#E3E9EF" stroke-width="9" stroke-linecap="round"/>'
            f'<text x="50" y="44" text-anchor="middle" font-size="7.5" fill="#5B6B7F" '
            f'font-style="italic">Not recorded</text></svg>'
            f'<div class="gauge-cap">{cap}</div>'
        )
    f = max(0.0, min(v / 100.0, 1.0))
    end = 180 - f * 180
    val = _arc(50, 48, 40, 180, end)
    color = _ramp_hex(v, invert)
    return (
        f'<svg class="gauge" viewBox="0 0 100 60" preserveAspectRatio="xMidYMid meet">'
        f'<path d="{bg}" fill="none" stroke="#E3E9EF" stroke-width="9" stroke-linecap="round"/>'
        f'<path d="{val}" fill="none" stroke="{color}" stroke-width="9" stroke-linecap="round"/>'
        f'<text x="50" y="42" text-anchor="middle" font-size="17" font-weight="bold" '
        f'fill="#12365B">{v:.1f}</text></svg>'
        f'<div class="gauge-cap">{cap}</div>'
    )


def _glyph(kind: str = "diamond", color: str = "#2FB3A0") -> str:
    if kind == "alert":
        inner = (f'<path d="M8 1.5 L15 14 L1 14 Z" fill="none" stroke="{color}" stroke-width="1.4" '
                 f'stroke-linejoin="round"/><line x1="8" y1="6" x2="8" y2="10" stroke="{color}" '
                 f'stroke-width="1.4" stroke-linecap="round"/><circle cx="8" cy="12" r="0.9" fill="{color}"/>')
    elif kind == "check":
        inner = (f'<path d="M2.5 8.5 L6.5 12.5 L13.5 3.5" fill="none" stroke="{color}" '
                 f'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>')
    elif kind == "arrow":
        inner = (f'<path d="M2.5 8 H12 M8 4 L12.5 8 L8 12" fill="none" stroke="{color}" '
                 f'stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>')
    else:  # diamond
        inner = f'<path d="M8 1 L15 8 L8 15 L1 8 Z" fill="{color}"/>'
    return f'<svg class="ico" viewBox="0 0 16 16">{inner}</svg>'


def _bar(label: str, value, fill: str, *, maxv: float = 100.0, suffix: str = "",
         absent: str = "Insufficient data") -> str:
    """A single labelled comparison/risk bar. `label` pre-escaped. Missing value
    → an honest-absence caption, NOT a zero-width bar."""
    v = _num(value)
    if v is None:
        return (f'<div class="bar-compare"><div class="bl">{label}</div>'
                f'<div class="bar-val absent">{absent}</div></div>')
    w = _pct(v, maxv)
    val_txt = f"{v:.1f}{suffix}"
    return (
        f'<div class="bar-compare"><div class="bl">{label}</div>'
        f'<div class="bar-track"><div class="bar-fill {fill}" style="width:{w}%;"></div></div>'
        f'<div class="bar-val">{val_txt}</div></div>'
    )


def _kpi(label: str, value_html: str, sub_html: str, *, accent: str = "navy",
         value_absent: bool = False) -> str:
    cls = "kpi-card accent-teal" if accent == "teal" else "kpi-card"
    vcls = "kpi-value absent" if value_absent else "kpi-value"
    return (
        f'<td><div class="{cls}"><div class="kpi-label">{label}</div>'
        f'<div class="{vcls}">{value_html}</div>'
        f'<div class="kpi-sub">{sub_html}</div></div></td>'
    )


def _empty_state(title: str, body: str) -> str:
    return (f'<div class="empty-state"><div class="es-title">{title}</div>'
            f'<div class="es-body">{body}</div></div>')


# ── HTML entrypoint ─────────────────────────────────────────────────────────

def render_html(report: ReportPayload, branding: dict | None = None) -> str:
    """Render the 12-section report payload to the executive HTML document.

    `branding` (optional) adds a partner header band ONLY — the report body is
    byte-identical to the unbranded render apart from that band (F20).
    """
    cover = ""
    for s in report.sections:
        if s.number == 1:
            cover = _render_cover(s)
    body = _render_parts([s for s in report.sections if s.number != 1])
    # F20: the band is prepended DIRECTLY to the body with no surrounding
    # whitespace, so unbranded vs branded differ by exactly the band substring
    # and nothing else (byte-identical body).
    band = _branding_band(branding)
    body_html = band + body
    # Closing bookend before the back cover (revised DDR-007) — kept in the same
    # order as the web report so PDF parity holds.
    body_html += _render_disclosure(report)
    back = _render_back_cover(report)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Privacy Intelligence Report — {_esc(report.organization_name)}</title>
<style>
{_CSS}
</style>
</head>
<body>
{cover}
{body_html}
{back}
</body>
</html>"""


# ── Cover / back cover ──────────────────────────────────────────────────────

def _render_cover(section: ReportSection) -> str:
    c = section.content
    org = _esc(c.get("organization", "")) or "Organization"
    date = _esc(c.get("date", "")) or "Not recorded"
    atype = _esc(c.get("report_title", "")) or "Privacy Intelligence Assessment"
    if _WORDMARK_DARK:
        logo = f'<img class="cover-logo" src="{_WORDMARK_DARK}" alt="Visentix">'
    else:
        logo = ('<div class="cover-logo" style="font-size:24pt;font-weight:bold;'
                'letter-spacing:2px;color:#fff;">VISENTIX</div>')
    scope = c.get("assessment_scope") or {}
    scope_html = ""
    if scope:
        rows = ""
        labels = {
            "source": "Assessed source", "notice_version": "Notice version",
            "capture_date": "Capture date", "effective_date": "Effective date",
            "intake_method": "Intake method", "organization_name": "Organization",
            "organization_size": "Organization size", "public_private": "Ownership type",
            "geography": "Geography", "industry": "Industry",
            "cohort_definition": "Peer cohort", "state_footprint": "State footprint",
            "selected_laws": "Selected legal scope", "data_categories": "Data categories",
            "business_practices": "Business practices",
        }
        for key, label in labels.items():
            item = scope.get(key)
            if isinstance(item, dict):
                value, provenance = item.get("value"), item.get("provenance")
            else:
                value, provenance = item, None
            if isinstance(value, list):
                value = ", ".join(str(v) for v in value)
            display = _esc(value) if value not in (None, "", []) else "Not recorded"
            prov = _esc(provenance or "not recorded").replace("_", " ")
            rows += (f'<tr><th>{_esc(label)}</th><td>{display}</td>'
                     f'<td><span class="caption">{prov}</span></td></tr>')
        scope_html = (
            '<section class="scope-front"><div class="sec-kicker">Assessment configuration</div>'
            '<h1>Assessment Scope</h1>'
            '<table class="data-table"><tr><th>Input</th><th>Value</th><th>Source</th></tr>'
            f'{rows}</table><div class="caption">Unconfirmed values are shown as assumptions; '
            'legacy assessments are not back-filled.</div></section>'
        )
    return f"""<section class="cover">
  <div class="cover-panel"></div>
  <div class="cover-accent"></div>
  {logo}
  <div class="cover-kicker">Privacy Intelligence Report</div>
  <div class="cover-org">{org}</div>
  <div class="cover-title">Executive Benchmark &amp; Regulatory Risk Analysis</div>
  <div class="cover-meta"><table>
    <tr><td><div class="ml">Prepared For</div><div class="mv">{org}</div></td>
        <td><div class="ml">Report Date</div><div class="mv">{date}</div></td>
        <td><div class="ml">Assessment Type</div><div class="mv">{atype}</div></td></tr>
  </table></div>
  <div class="cover-badge"><b>CONFIDENTIAL</b> &middot; This report contains proprietary
    Visentix intelligence and is intended solely for the use of the named recipient.</div>
</section>{scope_html}"""


def _render_disclosure(report: ReportPayload) -> str:
    """Closing bookend of the revised DDR-007 — PDF parity with the web report.

    The per-surface "Intelligence, not legal advice" mark is replaced by a scope
    statement at the front and this single Disclosure at the end. Authored static
    copy, frozen like every other page, and it passes the banned-term filter.
    It relaxes nothing: the verdict ban, VCI suppression, and exposure-only
    vocabulary are unchanged.
    """
    n = report.cohort_size
    as_of = _esc(str(report.cohort_date)) if report.cohort_date else ""
    cohort_clause = (
        f" (n={n}{f' as of {as_of}' if as_of else ''})"
        if isinstance(n, int) and n > 0 else ""
    )
    return f"""<section class="report-section" id="section-disclosure">
  <div class="sec-head"><div class="sec-num">&nbsp;</div>
  <div class="sec-title-wrap"><div class="sec-title">Disclosure</div></div></div>
  <p><strong>What this report is.</strong> It compares this organization's public privacy
  notice against the notices of comparable organizations and against published regulatory and
  enforcement signals, and reports where it stands, how that compares with its peer group, and
  how much confidence each figure carries. Every number traces to a stored, frozen record and
  can be reproduced from this snapshot.</p>
  <p><strong>What it is not.</strong> It is not legal advice and does not state whether any
  practice meets a legal requirement &mdash; that judgement belongs to qualified counsel who can
  see the whole picture, including everything a public notice does not show. Visentix reads the
  published notice, not the systems, contracts, or internal controls behind it, so a strong
  notice is evidence of strong disclosure rather than proof of strong practice.</p>
  <p><strong>How to use it.</strong> Treat the comparisons as a prioritization aid: they show
  where this organization's disclosure differs from its peers and where regulators have been
  active, which is a good guide to what to look at first. Confidence labels are part of the
  finding &mdash; a figure marked lower-confidence carries a wider margin and should be weighed
  accordingly.</p>
  <p><strong>Limits that apply to every figure here.</strong> Comparisons are drawn from the peer
  cohort recorded on each section{cohort_clause}; small cohorts are labelled and interpreted with
  caution. Regulatory sources reflect what was published as of the frozen date on this snapshot
  and change over time. Where evidence is absent, this report says so rather than estimating.</p>
</section>"""


def _render_back_cover(report: ReportPayload) -> str:
    if _WORDMARK_DARK:
        logo = f'<img src="{_WORDMARK_DARK}" alt="Visentix">'
    else:
        logo = '<div style="font-size:26pt;font-weight:bold;letter-spacing:2px;color:#fff;">VISENTIX</div>'
    return f"""<section class="back">
  <div class="back-accent"></div>
  <div class="back-logo">{logo}</div>
  <div class="back-thanks">Thank you for your trust.</div>
  <div class="back-contact">
    Visentix &middot; Privacy Intelligence Platform
  </div>
  <div class="back-conf">This report contains proprietary Visentix intelligence and is
    intended solely for the use of the named recipient. &copy; Visentix.</div>
</section>"""


# ── Section frame ───────────────────────────────────────────────────────────

def _section_open(section: ReportSection, heading: str = "own") -> str:
    """Open a block. `heading`: "own" (block titles itself, legacy standalone),
    "sub" (one of several blocks in a part), or "hidden" (sole block in a part —
    the part heading already named it, so repeating it adds nothing)."""
    if heading == "hidden":
        return f'<section class="report-section sec-nested" id="section-{section.number}">'
    if heading == "sub":
        return (
            f'<section class="report-section sec-nested" id="section-{section.number}">'
            f'<h3 class="sec-subhead">{_esc(section.title)}</h3>'
        )
    kicker = _SECTION_KICKERS.get(section.number, "")
    kick_html = f'<div class="sec-kicker">{kicker}</div>' if kicker else ""
    return (
        f'<section class="report-section" id="section-{section.number}">'
        f'<div class="sec-head"><div class="sec-num">{section.number:02d}</div>'
        f'<div class="sec-title-wrap">{kick_html}'
        f'<div class="sec-title">{_esc(section.title)}</div></div></div>'
    )


def _render_section(section: ReportSection, heading: str = "own") -> str:
    n = section.number
    renderer = _SECTION_RENDERERS.get(n)
    inner = renderer(section.content) if renderer else _render_generic(section.content)
    return _section_open(section, heading) + inner + "</section>"


def _render_parts(sections: list[ReportSection]) -> str:
    """Render the body as six grouped parts + appendix (see _REPORT_PARTS).

    A part whose blocks are all absent from the payload is skipped entirely, so a
    legacy snapshot never produces an empty heading.
    """
    by_number = {s.number: s for s in sections}
    out: list[str] = []
    for number, title, lede, block_numbers in _REPORT_PARTS:
        blocks = [by_number[n] for n in block_numbers if n in by_number]
        if not blocks:
            continue
        label = f"{number}. {title}" if number is not None else title
        lede_html = f'<p class="part-lede">{lede}</p>' if lede else ""
        out.append(f'<div class="report-part"><div class="part-head">'
                   f'<h2 class="part-title">{label}</h2>{lede_html}</div>')
        mode = "sub" if len(blocks) > 1 else "hidden"
        out.extend(_render_section(s, mode) for s in blocks)
        out.append("</div>")
    return "".join(out)


# ── Section 2: Executive Summary ────────────────────────────────────────────

def _sec_exec(c: dict) -> str:
    overall = c.get("overall_score")
    band = _esc(c.get("overall_band", "") or "")
    percentile = c.get("percentile")
    reg = c.get("regulatory_exposure")
    reg_tier = (c.get("regulatory_tier") or "").strip()

    # KPI 1 — Overall score
    if _num(overall) is None:
        k1 = _kpi("Overall Score", "Not recorded", "Awaiting scoring", value_absent=True)
    else:
        sub = f"{band} band" if band else "of 100"
        k1 = _kpi("Overall Score",
                  f'{overall:.1f}<span class="unit">/100</span>', _esc(sub))

    # KPI 2 — Benchmark percentile
    if _num(percentile) is None:
        k2 = _kpi("Benchmark Percentile", "Not recorded", "No peer ranking yet",
                  accent="teal", value_absent=True)
    else:
        k2 = _kpi("Benchmark Percentile", _esc(_ordinal(percentile)),
                  "within peer cohort", accent="teal")

    # KPI 3 — Regulatory exposure level (risk colour). The F-002 formula ALWAYS
    # emits a tier when it runs, so an empty tier means "not computed" — render
    # honest absence rather than the 0.0 that assembly defaults a missing score to.
    if not reg_tier:
        k3 = _kpi("Regulatory Exposure", "Not recorded", "Not yet measured", value_absent=True)
    else:
        color = _ramp_hex(reg) if _num(reg) is not None else _RAMP.get(reg_tier, "#5B6B7F")
        sub = f"exposure score {reg:.1f}" if _num(reg) is not None else "level assessed"
        k3 = _kpi("Regulatory Exposure",
                  f'<span style="color:{color};">{_esc(reg_tier).title()}</span>', _esc(sub))

    kpis = f'<table class="strip"><tr>{k1}{k2}{k3}</tr></table>'

    summary = _prose(c.get("summary", ""))
    summary_html = f'<p style="margin-top:10pt;">{summary}</p>' if summary else ""

    takeaways = c.get("takeaways", []) or []
    if takeaways:
        rows = "".join(
            f'<div class="takeaway"><div class="ic">{_glyph("diamond")}</div>'
            f'<div class="tx">{_prose(t)}</div></div>'
            for t in takeaways if _prose(t)
        )
        tk_html = (f'<h3 style="margin-top:12pt;color:#12365B;font-size:10pt;">'
                   f'Key Intelligence Takeaways</h3><div class="takeaways">{rows}</div>')
    else:
        tk_html = _empty_state("Key takeaways not recorded",
                               "Takeaways are generated once the assessment narrative completes.")

    cohort = c.get("cohort_size")
    cd = _esc(c.get("cohort_date", ""))
    if _num(cohort) is not None:
        cn = f'<div class="snapline">Benchmarked against n={int(cohort)} peers as of {cd}.</div>'
    else:
        cn = ""
    return kpis + summary_html + tk_html + cn


# ── Section 3: Risk Dashboard ───────────────────────────────────────────────

def _sec_dashboard(c: dict) -> str:
    overall = c.get("overall_intelligence")
    # percentile isn't on section 3; the gauge trio uses what IS here + exposure
    exposure = c.get("regulatory_exposure")
    vci = c.get("vci_score")

    metric_by_key = {m["key"]: m for m in _DASHBOARD_METRICS}
    gauges = (
        f'<table class="gauge-row"><tr>'
        f'<td>{_gauge(overall, "Overall Intelligence · higher is better", invert=metric_by_key["overall_intelligence"]["inverted"])}</td>'
        f'<td>{_gauge(exposure, "Regulatory Exposure · lower is better", invert=metric_by_key["regulatory_exposure"]["inverted"])}</td>'
        f'<td>{_gauge(vci, "Confidence (VCI) · higher is stronger", invert=True)}</td>'
        f'</tr></table>'
    )

    # Metric strip (4 cards)
    quality = c.get("extraction_quality") or {}
    quality_notice = ""
    if quality.get("status") in {"mismatch", "insufficient"}:
        detail = (
            "The stored scoring record and the clauses available to this report do not agree."
            if quality.get("status") == "mismatch"
            else "No substantive notice clauses are available to support parse-dependent measures."
        )
        quality_notice = (
            '<div class="callout callout--alert"><div class="co-title">Extraction review needed</div>'
            f'<div>{detail} '
            'Parse-dependent maturity and benchmark values are withheld pending review.</div></div>'
        )

    strip_defs = [metric_by_key[key] for key in (
        "disclosure_maturity", "ai_transparency", "transparency", "regulatory_exposure"
    )]
    cards = ""
    for metric in strip_defs:
        label, val, inv = metric["label"], c.get(metric["key"]), metric["inverted"]
        direction = _direction(inv)
        if _num(val) is None:
            cards += (f'<td><div class="metric-card"><div class="metric-label">{label}</div>'
                      f'<div class="metric-value absent">Not recorded</div>'
                      f'<div class="caption">{direction}</div></div></td>')
        else:
            color = _ramp_hex(val, inv)
            cards += (f'<td><div class="metric-card" style="border-top:3pt solid {color};">'
                      f'<div class="metric-label">{label}</div>'
                      f'<div class="metric-value">{val:.1f}</div>'
                      f'<div class="caption">{direction}</div></div></td>')
    strip = f'<table class="strip" style="margin-top:12pt;"><tr>{cards}</tr></table>'

    # Risk dimension summary bars
    bars = ""
    for metric in _DASHBOARD_METRICS:
        label, val, inv = metric["label"], c.get(metric["key"]), metric["inverted"]
        fill = f"f-{_ramp_key(val, inv)}" if _num(val) is not None else "f-muted"
        direction = _direction(inv)
        bars += _bar(f"{_esc(label)} <span class=\"caption\">{direction}</span>", val, fill)
    bars_html = (f'<h3 style="margin-top:14pt;color:#12365B;font-size:10pt;">'
                 f'Risk Dimension Summary</h3>{bars}')

    return quality_notice + gauges + strip + bars_html


# ── Section 4: Benchmark Intelligence ───────────────────────────────────────

def _sec_benchmark(c: dict) -> str:
    percentile = c.get("percentile")
    org_score = c.get("org_score")
    tq = c.get("top_quartile_score")
    peer_n = c.get("peer_n")
    measure = _esc(c.get("measure_label") or "Governance Maturity (PGMS)")
    methodology = c.get("methodology") or {}

    # Percentile marker bar
    if _num(percentile) is None:
        pbar = _empty_state("Percentile not recorded",
                            "Percentile ranking requires a scored peer cohort.")
    else:
        left = _pct(percentile)
        pbar = (
            f'<div class="bar-compare"><div class="bl">{measure} percentile ranking '
            f'({_esc(_ordinal(percentile))})</div>'
            f'<div class="pmark-track"><div class="pmark" style="left:{left}%;"></div>'
            f'<div class="pmark-lbl" style="left:{left}%;">{percentile:.1f}</div></div>'
            f'<div class="caption" style="margin-top:2pt;">0 &rarr; 100 across the peer cohort</div></div>'
        )

    # Overall vs top-quartile (real: F-003 lineage)
    head = ('<h3 style="margin-top:14pt;color:#12365B;font-size:10pt;">'
            f'{measure} Comparison</h3>')
    if _num(org_score) is not None and _num(tq) is not None:
        legend = ('<div class="legend"><span class="sw" style="background:#12365B;"></span>Your score'
                  '<span class="sw" style="background:#2FB3A0;"></span>Top quartile</div>')
        cmp_bars = (
            _bar(f"Your {measure} score · higher is better", org_score, "f-navy")
            + _bar(f"Peer top-quartile {measure} threshold", tq, "f-teal")
        )
        peer_note = (f'<div class="caption">Top-quartile threshold computed over '
                     f'{int(peer_n)} weighted peers (F-003).</div>'
                     if _num(peer_n) is not None else "")
        dims = legend + cmp_bars + peer_note
    else:
        dims = _empty_state(
            "Insufficient peer data",
            "Per-dimension peer averages are not available for this cohort. Visentix "
            "reports only the benchmarks it can substantiate — no industry average is "
            "estimated where peer data is absent.")

    method_html = ""
    if methodology:
        dimensions = methodology.get("dimensions") or []
        if isinstance(dimensions, dict):
            dimensions = [f"{k}: {v}" for k, v in dimensions.items() if v not in (None, "")]
        dim_text = ", ".join(str(d) for d in dimensions) if dimensions else "Not recorded"
        version = methodology.get("benchmark_population_version") or "Not recorded"
        as_of = methodology.get("as_of_date") or c.get("cohort_date") or "Not recorded"
        relaxations = methodology.get("relaxations") or []
        relax_text = ""
        if relaxations:
            readable = ", ".join(str(x).replace("_", " ") for x in relaxations)
            relax_text = (f'<p><b>Cohort widening:</b> {_esc(readable)}. '
                          'Confidence is reduced to reflect the broader comparison.</p>')
        low = ('<span class="chip chip-moderate">LOW-CONFIDENCE COHORT</span>'
               if methodology.get("low_confidence") else "")
        method_html = (
            '<div class="callout callout--insight"><div class="co-title">Peer-cohort methodology</div>'
            f'<p><b>Dimensions:</b> {_esc(dim_text)}.</p><p><b>Population version:</b> '
            f'{_esc(version)} · <b>as of:</b> {_esc(as_of)}. {low}</p>{relax_text}</div>'
        )
    else:
        method_html = _empty_state("Cohort methodology not recorded",
                                   "No stored peer-population definition is available for this assessment.")

    cohort = _esc(c.get("cohort_label", ""))
    cn = f'<div class="snapline">{cohort}</div>' if cohort else ""
    formula_ids = c.get("formula_ids") or {}
    lineage = (f'<div class="caption">Comparison: {_esc(formula_ids.get("comparison", "F-003"))} · '
               f'percentile: {_esc(formula_ids.get("percentile", "F-011"))}.</div>')
    return pbar + head + dims + method_html + lineage + cn


# ── Section 5: Regulator Exposure ───────────────────────────────────────────

def _heat_band(intensity, evidenced: bool) -> str:
    v = _num(intensity)
    if not evidenced or v is None:
        return "heat-na"
    if v < 25:
        return "heat-l1"
    if v < 50:
        return "heat-l2"
    if v < 75:
        return "heat-l3"
    return "heat-l4"


def _sec_regulator(c: dict) -> str:
    reg_score = c.get("regulatory_score")
    tier = _esc((c.get("tier") or "").title())
    heatmap = c.get("heatmap", []) or []

    head_line = (f'<p>Overall regulatory exposure: <b>{_fmt(reg_score)}</b>'
                 f'{f" ({tier})" if tier else ""}.</p>')

    if not heatmap:
        return head_line + _empty_state(
            "Regulator heatmap not available",
            "The regulator sensitivity grid populates from resolved enforcement records "
            "mapped to this notice. None are resolved for this assessment yet.")

    # Regulator overview cards
    cards = ""
    for row in heatmap[:8]:
        cells = row.get("cells", []) or []
        peak = max((_num(x.get("intensity")) or 0.0 for x in cells), default=0.0)
        color = _ramp_hex(peak, invert=False)
        name = _esc(row.get("regulator_name", row.get("regulator_id", "")))
        juris = _esc(row.get("jurisdiction", ""))
        cards += (
            f'<td><div class="reg-card" style="border-left-color:{color};">'
            f'<div class="reg-name">{name}</div>'
            f'<div class="reg-juris">{juris or "&mdash;"}</div>'
            f'<div class="caption" style="margin-top:3pt;">Peak exposure '
            f'<b style="color:{color};">{peak:.1f}</b></div></div></td>'
        )
    # chunk cards into rows of 4
    card_cells = re.findall(r"<td>.*?</td>", cards, re.S)
    card_rows = ""
    for i in range(0, len(card_cells), 4):
        card_rows += "<tr>" + "".join(card_cells[i:i + 4]) + "</tr>"
    cards_html = f'<table class="strip">{card_rows}</table>'

    # Heat grid: domains (rows) × regulators (cols)
    domains = [
        "ai_automated_decisions", "children_teens", "consumer_rights", "cross_border",
        "data_sharing", "retention", "sensitive_data", "tracking_cookies",
    ]
    regs = heatmap[:9]
    colh = "".join(
        f'<th class="colh">{_esc(r.get("regulator_id", ""))}</th>' for r in regs
    )
    total_cells = 0
    evidenced_cells = 0
    body_rows = ""
    top_drivers: list[tuple[float, str, str]] = []
    for dom in domains:
        row_html = f'<th class="rowh">{_domain_html(dom)}</th>'
        for r in regs:
            cell = next((x for x in r.get("cells", []) if x.get("domain") == dom), None)
            total_cells += 1
            if cell is None:
                row_html += '<td class="heat-na">&middot;</td>'
                continue
            intensity = _num(cell.get("intensity"))
            # New snapshots carry the explicit flag. Density fallback preserves
            # deterministic rendering of older frozen snapshots.
            evidenced = cell.get("evidenced")
            if not isinstance(evidenced, bool):
                evidenced = (_num(cell.get("clause_density")) or 0.0) > 0.0
            band = _heat_band(intensity, evidenced)
            if evidenced and intensity is not None:
                evidenced_cells += 1
                top_drivers.append((intensity, r.get("regulator_name", r.get("regulator_id", "")),
                                    _domain_html(dom)))
                row_html += f'<td class="{band}">{intensity:.0f}</td>'
            else:
                row_html += f'<td class="{band}">&middot;</td>'
        body_rows += f"<tr>{row_html}</tr>"
    grid = (
        f'<h3 style="margin-top:12pt;color:#12365B;font-size:10pt;">Regulator Sensitivity Heatmap</h3>'
        f'<table class="heat-grid"><tr><th class="rowh">Domain</th>{colh}</tr>{body_rows}</table>'
        f'<div class="heat-legend">'
        f'<span class="sw heat-l1"></span>Low<span class="sw heat-l2"></span>Moderate'
        f'<span class="sw heat-l3"></span>High<span class="sw heat-l4"></span>Elevated'
        f'<span class="sw heat-na"></span>Regulator baseline — no clause from your notice maps to this domain</div>'
        f'<div class="caption" style="margin-top:3pt;">Coverage: {evidenced_cells} of {total_cells} '
        f'domain&times;regulator cells backed by clause evidence in this notice; hatched cells carry '
        f'no evidence and are left uncoloured.</div>'
    )

    # Top regulator risk drivers (only evidenced)
    top_drivers.sort(key=lambda t: t[0], reverse=True)
    if top_drivers:
        items = "".join(
            f'<li><b>{_esc(name)}</b> &middot; {dom} — exposure {score:.1f}</li>'
            for score, name, dom in top_drivers[:5]
        )
        drivers = (f'<h3 style="margin-top:12pt;color:#12365B;font-size:10pt;">'
                   f'Top Regulator Risk Drivers</h3><ol class="numbered-driver">{items}</ol>')
    else:
        drivers = _empty_state(
            "No evidenced regulator drivers",
            "No domain×regulator cell has clause evidence in this notice, so no driver is asserted.")

    return head_line + cards_html + grid + drivers


# ── Section 6: Disclosure Findings ──────────────────────────────────────────

def _sec_findings(c: dict) -> str:
    findings = c.get("findings", []) or []
    total = c.get("total")
    head = f'<p>Total findings: <b>{_fmt(total, "Not recorded", 0)}</b>.</p>'
    if not findings:
        return head + _empty_state(
            "No disclosure findings recorded",
            "No elevated-exposure findings were produced for this assessment.")
    rows = ""
    for f in findings:
        sev = (f.get("severity") or "").lower()
        sev_cls = f"sev-{sev}" if sev in {"high", "medium", "low"} else ""
        chip_cls = {"high": "chip-high", "medium": "chip-moderate", "low": "chip-low"}.get(sev, "chip-na")
        conf = _esc(f.get("confidence", "") or "Not recorded")
        evidence = f.get("evidence") or []
        if evidence:
            evidence_html = "".join(
                '<div class="caption" style="margin-top:4pt;">'
                f'<b>Clause {_esc(item.get("clause_id") or "Not recorded")}</b>'
                f'{" · " + _esc(item.get("section_reference")) if item.get("section_reference") else ""}'
                f'<div class="quote you">{_esc(item.get("excerpt") or "")}</div></div>'
                for item in evidence
            )
        else:
            evidence_html = ('<div class="caption" style="margin-top:4pt;">'
                             'No triggering clause reference is stored for this finding.</div>')
        rows += (
            f'<div class="finding-row {sev_cls}">'
            f'<div class="fr-main"><span class="fr-id">{_esc(f.get("id", ""))}</span> '
            f'<span class="fr-domain">&middot; {_domain_html(f.get("domain", ""))}</span>'
            f'<div class="fr-meta"><span class="chip {chip_cls}">{_esc(sev or "n/a").upper()}</span> '
            f'&nbsp; Confidence: {conf}</div></div>'
            f'<div class="fr-side"><div class="fr-score">{_fmt(f.get("score"))}</div>'
            f'<div class="caption">exposure</div></div>'
            f'</div>{evidence_html}</div>'
        )
    return head + rows


# ── Section 7: Compound Risk ────────────────────────────────────────────────

def _sec_compound(c: dict) -> str:
    score = c.get("compound_score")
    lineage = c.get("lineage", {}) or {}
    if _num(score) is None:
        return _empty_state("Compound risk not recorded",
                            "The compound-risk formula (F-008) did not produce a score for this assessment.")
    level = _ramp_key(score).title()
    color = _ramp_hex(score)
    alert = (
        f'<div class="callout callout--risk"><div class="co-title">'
        f'Compound Risk Level: {level} &middot; {score:.1f}/100</div>'
        f'<div>Compound risk reflects how individual exposures reinforce one another. '
        f'A higher score means findings cluster into a larger combined regulatory surface.</div></div>'
    )
    # Drivers from both the current F-008 shape (risk_scores dict) and older
    # snapshot producer shapes (contributors/drivers list).
    contributors = lineage.get("contributors") or lineage.get("drivers") or []
    risk_scores = lineage.get("risk_scores") or {}
    if isinstance(risk_scores, dict) and risk_scores:
        contributors = [
            {"domain": name, "score": value}
            for name, value in sorted(
                risk_scores.items(),
                key=lambda item: (-(float(item[1]) if isinstance(item[1], (int, float)) else -1.0), str(item[0])),
            )
        ]
    driver_labels = {
        "regulatory": "Regulatory Exposure", "benchmark": "Benchmark Deviation",
        "disclosure": "Disclosure Maturity Gap", "ai": "AI Transparency Gap",
    }
    if isinstance(contributors, list) and contributors:
        items = ""
        for d in contributors[:5]:
            if isinstance(d, dict):
                raw_label = d.get("code") or d.get("domain") or ""
                label = _esc(driver_labels.get(raw_label, raw_label))
                extra = _fmt(d.get("score"), "", 1)
                items += f'<li><b>{label}</b>{f" — {extra}" if extra else ""}</li>'
            else:
                items += f'<li>{_esc(d)}</li>'
        drivers = (f'<h3 style="margin-top:6pt;color:#12365B;font-size:10pt;">'
                   f'Top Compound Risk Drivers</h3><ol class="numbered-driver">{items}</ol>')
    else:
        drivers = _empty_state("Driver breakdown not recorded",
                               "The compound-risk lineage did not enumerate contributing findings.")
    multiplier = lineage.get("cm")
    multiplier_html = ""
    if _num(multiplier) is not None:
        multiplier_html = (
            f'<div class="caption">Correlation multiplier: {float(multiplier):.2f}. '
            'The multiplier reflects how related exposure signals can reinforce one another.</div>'
        )
    impact = (
        f'<div class="callout callout--alert"><div class="co-title">Compound Risk Impact</div>'
        f'<div>At a {level.lower()} compound level, remediating the highest-severity findings '
        f'first yields the largest reduction in combined exposure.</div></div>'
    )
    return alert + drivers + multiplier_html + impact


# ── Section 8: Benchmark Language Comparison ────────────────────────────────

def _sec_language(c: dict) -> str:
    entries = c.get("entries", []) or []
    if not entries:
        return _empty_state(
            "Language benchmarking pending",
            "No substantive notice clause is available for a domain comparison.")
    rows = ""
    for e in entries:
        dom = _domain_html(e.get("domain", ""))
        your_text = _prose(e.get("your_text", ""))
        peer_text = _prose(e.get("exemplar_text", ""))
        note = _prose(e.get("maturity_note", ""))
        your_cell = (f'<div class="quote you"><div class="qh">Your notice language</div>'
                     f'{your_text}</div>' if your_text else
                     '<div class="quote you"><div class="qh">Your notice language</div>'
                     '<span class="absent">No clause captured for this domain.</span></div>')
        if peer_text:
            peer_cell = (f'<div class="quote peer"><div class="qh">Approved peer comparator</div>'
                         f'{peer_text}{f"<div class=\"caption\" style=\"margin-top:4pt;\">{note}</div>" if note else ""}</div>')
        else:
            peer_cell = ('<div class="quote peer"><div class="qh">Approved peer comparator</div>'
                         '<span class="absent">No comparable approved peer language is available for this domain.</span></div>')
        rows += (f'<div class="lang-domain">{dom}</div>'
                 f'<table class="lang-cmp"><tr><td>{your_cell}</td><td>{peer_cell}</td></tr></table>')
    return rows


# ── Section 9: Strategic Recommendations ────────────────────────────────────

def _sec_recommendations(c: dict) -> str:
    recs = c.get("recommendations", []) or []
    if not recs:
        return _empty_state("No recommendations recorded",
                            "Strategic recommendations are generated from the assessment's findings.")
    rows = ""
    for r in recs:
        sev = (r.get("severity") or "medium").lower()
        chip_cls = {"high": "chip-high", "medium": "chip-moderate", "low": "chip-low"}.get(sev, "chip-na")
        gcolor = _RAMP.get({"high": "high", "medium": "moderate", "low": "low"}.get(sev, "moderate"))
        title = _prose(r.get("title", "")) or _prose(r.get("prose", ""))[:80]
        body = _prose(r.get("prose", ""))
        basis = _esc(r.get("basis_label") or "Basis not recorded")
        citation = _esc(r.get("source_note") or "")
        evidence = r.get("evidence") or []
        evidence_html = ""
        if evidence:
            first = evidence[0]
            evidence_html = (
                '<div class="caption"><b>Notice evidence:</b> '
                f'{_esc(first.get("section_reference") or first.get("clause_id") or "Stored clause")}'
                f' — {_esc(first.get("excerpt") or "")}</div>'
            )
        citation_html = (f'<div class="caption"><b>Authored source note:</b> {citation}</div>'
                         if citation else '<div class="caption">No authored source citation is recorded.</div>')
        rows += (
            f'<div class="rec-row"><div class="rec-ic">{_glyph("arrow", gcolor)}</div>'
            f'<div class="rec-bd"><div class="rec-title">{title} '
            f'<span class="chip {chip_cls}">{_esc(sev).upper()}</span></div>'
            f'<div class="rec-body">{body}</div>'
            f'<div class="caption"><b>Basis:</b> {basis}</div>{evidence_html}{citation_html}'
            f'</div></div>'
        )
    return rows


# ── Section 10: Risk Reduction by Severity ──────────────────────────────────

def _sec_reduction(c: dict) -> str:
    high = c.get("high_severity", []) or []
    medium = c.get("medium_severity", []) or []
    low = c.get("low_severity", []) or []

    def col(title: str, cls: str, items: list) -> str:
        if items:
            lis = "".join(
                f'<li>Strengthen {_domain_html(it.get("domain", ""))} '
                f'disclosure <span class="caption">({_esc(it.get("code", ""))})</span></li>'
                for it in items
            )
            body = f'<ol class="numbered-driver">{lis}</ol>'
        else:
            body = '<div class="absent" style="font-size:8pt;">No actions at this level.</div>'
        return (f'<td><div class="sev-col {cls}"><div class="hd">{title}</div>'
                f'<div class="bd">{body}</div></div></td>')

    intro = (f'<p>{len(high)} high-severity and {len(medium)} moderate-severity '
             f'findings drive the prioritisation below.</p>')
    table = (f'<table class="sev-cols"><tr>'
             f'{col("High", "high", high)}{col("Moderate", "moderate", medium)}'
             f'{col("Low", "low", low)}</tr></table>')
    return intro + table


# ── Section 11: Source Traceability ─────────────────────────────────────────

def _sec_traceability(c: dict) -> str:
    snap = _esc(c.get("snapshot_id", "") or "N/A")
    versions = c.get("formula_versions_used", []) or []
    guardrail = c.get("guardrail", {}) or {}
    g_status = _esc(str(guardrail.get("status", "not_recorded")))
    g_chip = "chip-low" if g_status == "passed" else "chip-na"

    ver_rows = "".join(
        f'<tr><td>{_esc(v)}</td><td>Contributed to the scored snapshot</td></tr>'
        for v in versions
    ) or '<tr><td colspan="2"><span class="absent">No formula versions recorded.</span></td></tr>'

    table = (
        '<table class="data-table"><tr><th>Formula version</th><th>Role</th></tr>'
        f'{ver_rows}</table>'
    )
    receipt = (
        f'<p style="margin-top:8pt;">Phrasing guardrail: '
        f'<span class="chip {g_chip}">{g_status.upper()}</span> '
        f'<span class="caption">(GRD-001/002 — the real outcome recorded for this snapshot, '
        f'never a default).</span></p>'
    )
    token_result = c.get("template_tokens") or {}
    token_status = _esc(token_result.get("status") or "not_recorded")
    token_receipt = (
        f'<p>Template-token gate: <span class="chip {"chip-low" if token_status == "passed" else "chip-na"}">'
        f'{token_status.upper()}</span></p>'
    )
    quality = c.get("extraction_quality") or {}
    quality_status = _esc(quality.get("status") or "not_recorded")
    quality_receipt = f'<p>Clause read agreement: <b>{quality_status.replace("_", " ")}</b>.</p>'

    evidence_rows = ""
    for finding in c.get("finding_evidence") or []:
        evidence = finding.get("evidence") or []
        if not evidence:
            evidence_rows += (
                f'<tr><td>{_esc(finding.get("id") or "")}</td>'
                '<td colspan="6"><span class="absent">No stored clause reference for this finding.</span></td></tr>'
            )
            continue
        for item in evidence:
            evidence_rows += (
                f'<tr><td>{_esc(finding.get("id") or "")}</td>'
                f'<td>{_esc(item.get("clause_id") or "")}</td>'
                f'<td>{_esc(item.get("section_reference") or "Not recorded")}</td>'
                f'<td>{_esc(item.get("excerpt") or "")}</td>'
                f'<td>{_esc(item.get("source_reference") or "Not recorded")}</td>'
                f'<td>{_esc(finding.get("formula_version") or "Not recorded")}</td>'
                f'<td>{_esc(finding.get("confidence") or "Not recorded")}</td></tr>'
            )
    evidence_body = evidence_rows or (
        '<tr><td colspan="7"><span class="absent">No finding evidence is recorded.</span></td></tr>'
    )
    finding_table = (
        '<h3 style="margin-top:10pt;color:#12365B;font-size:10pt;">Finding evidence lineage</h3>'
        '<table class="data-table"><tr><th>Finding</th><th>Clause</th><th>Section</th>'
        '<th>Excerpt</th><th>Source</th><th>Formula</th><th>Confidence</th></tr>'
        f'{evidence_body}'
        '</table>'
    )
    note = _prose(c.get("note", ""))
    snapline = f'<div class="snapline">{note}</div>' if note else (
        f'<div class="snapline">Snapshot {snap}.</div>')
    return table + receipt + token_receipt + quality_receipt + finding_table + snapline


# ── Section 12: Trend & Emerging Risk ───────────────────────────────────────

def _sec_trend(c: dict) -> str:
    landscape = c.get("regulatory_landscape", {}) or {}
    active = landscape.get("active_regulators")
    empty = _empty_state(
        "Trend begins after your next monitored capture",
        "Per-company trend requires monitoring history. Your first capture establishes the "
        "baseline; the trend line appears once a second monitored capture exists. Visentix does "
        "not draw a trend from a single point.")
    note = _prose(c.get("note", ""))
    landscape_html = ""
    if _num(active) is not None:
        landscape_html = (
            f'<div class="callout callout--insight"><div class="co-title">Regulatory Landscape</div>'
            f'<div>{int(active)} regulators are actively weighted in the current enforcement model. '
            f'{note}</div></div>'
        )
    elif note:
        landscape_html = f'<p>{note}</p>'
    return empty + landscape_html


def _render_generic(c: dict) -> str:
    """Fallback for any unexpected section shape (keeps render total)."""
    text = _prose(c.get("note", "") or c.get("summary", "") or c.get("text", ""))
    return f"<p>{text}</p>" if text else ""


_SECTION_RENDERERS = {
    2: _sec_exec,
    3: _sec_dashboard,
    4: _sec_benchmark,
    5: _sec_regulator,
    6: _sec_findings,
    7: _sec_compound,
    8: _sec_language,
    9: _sec_recommendations,
    10: _sec_reduction,
    11: _sec_traceability,
    12: _sec_trend,
}


# ── PDF backends ────────────────────────────────────────────────────────────

async def render_pdf(report: ReportPayload, renderer: str = "weasyprint",
                     branding: dict | None = None) -> bytes:
    """Dispatch to the configured renderer. Never accepts arbitrary URLs.

    WeasyPrint is SYNCHRONOUS and CPU-bound; calling it directly on the event
    loop blocks every other request (including /health) for the render duration,
    which on a small VM makes the edge proxy 503 concurrent traffic. Run it in a
    worker thread so the loop stays responsive. (Playwright is already async.)
    """
    if renderer == "playwright":
        return await render_pdf_playwright(report, branding)
    import asyncio
    return await asyncio.to_thread(render_pdf_weasyprint, report, branding)


def render_pdf_weasyprint(report: ReportPayload, branding: dict | None = None) -> bytes:
    """Render report to PDF using weasyprint."""
    import weasyprint

    html = render_html(report, branding)
    pdf_bytes = weasyprint.HTML(string=html).write_pdf()
    return pdf_bytes


async def render_pdf_playwright(report: ReportPayload, branding: dict | None = None) -> bytes:
    """Render report to PDF using Playwright (headless Chromium).

    This matches the React portal rendering exactly.
    Falls back to weasyprint if Playwright is not available.
    """
    try:
        from playwright.async_api import async_playwright

        html = render_html(report, branding)
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.set_content(html, wait_until="networkidle")
            pdf_bytes = await page.pdf(
                format="A4",
                margin={"top": "20mm", "bottom": "20mm", "left": "15mm", "right": "15mm"},
                print_background=True,
            )
            await browser.close()
            return pdf_bytes
    except ImportError:
        # Playwright not installed — fall back to weasyprint
        return render_pdf_weasyprint(report, branding)
