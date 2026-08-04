"""Report PDF renderer — env-driven backend selection.

Renderer selection via RENDERER env var:
  - "weasyprint" (default, active): weasyprint HTML→PDF
  - "playwright": headless Chromium via Playwright (requires install)

NOTE (2026-06-29): Playwright install blocked by network egress restrictions
(pypi.org unreachable). weasyprint is the active renderer. When Playwright
becomes available, set RENDERER=playwright and run:
    pip install playwright && playwright install chromium

The renderer renders ONLY our own report HTML (set_content, not goto) —
never an arbitrary URL. No SSRF via the renderer.
"""

from __future__ import annotations

import io
import re
from datetime import datetime

from app.services.report.assembly import ReportPayload, ReportSection

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
    logo_html = f'<img src="{_esc(logo)}" alt="" style="max-height:44px;">' if logo else ""
    return (
        f'<div class="brand-band" style="border-top:6px solid {color};'
        f'display:flex;align-items:center;gap:14px;padding:12px 0 8px;margin-bottom:8px;">'
        f'{logo_html}<span style="font-weight:700;color:{color};font-size:1.1em;">{name}</span>'
        f'<span style="margin-left:auto;font-size:0.75em;color:#9ca3af;">Delivered via Visentix</span>'
        f'</div>'
    )


def render_html(report: ReportPayload, branding: dict | None = None) -> str:
    """Render the 12-section report payload to HTML.

    `branding` (optional) adds a partner header band ONLY — the report body is
    identical to the unbranded render.
    """
    sections_html = "\n".join(_render_section(s) for s in report.sections)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Privacy Intelligence Report — {_esc(report.organization_name)}</title>
<style>
  body {{ font-family: 'Segoe UI', system-ui, sans-serif; margin: 40px; color: #1a1a2e; line-height: 1.6; }}
  h1 {{ color: #16213e; border-bottom: 3px solid #0f3460; padding-bottom: 8px; }}
  h2 {{ color: #0f3460; margin-top: 32px; border-bottom: 1px solid #e0e0e0; padding-bottom: 4px; }}
  .section {{ margin-bottom: 28px; page-break-inside: avoid; }}
  .score {{ font-size: 2em; font-weight: bold; color: #0f3460; }}
  .tier {{ display: inline-block; padding: 2px 10px; border-radius: 4px; font-weight: 600; }}
  .tier-high {{ background: #fee2e2; color: #991b1b; }}
  .tier-elevated {{ background: #fef3c7; color: #92400e; }}
  .tier-moderate {{ background: #dbeafe; color: #1e40af; }}
  .tier-low {{ background: #d1fae5; color: #065f46; }}
  table {{ border-collapse: collapse; width: 100%; margin: 12px 0; }}
  th, td {{ border: 1px solid #d1d5db; padding: 8px 12px; text-align: left; }}
  th {{ background: #f3f4f6; font-weight: 600; }}
  .cohort-note {{ font-size: 0.85em; color: #6b7280; font-style: italic; }}
  .placeholder {{ background: #fefce8; border: 1px dashed #ca8a04; padding: 12px; border-radius: 4px; }}
  .footer {{ margin-top: 40px; border-top: 1px solid #e0e0e0; padding-top: 8px; font-size: 0.8em; color: #9ca3af; }}
</style>
</head>
<body>
{_branding_band(branding)}
{sections_html}
<div class="footer">
  Generated by Visentix Privacy Intelligence Platform · {report.generated_date} ·
  Snapshot: {report.assessment_id[:12] if report.assessment_id else 'N/A'}
</div>
</body>
</html>"""


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
        return render_pdf_weasyprint(report)


def _render_section(section: ReportSection) -> str:
    """Render a single section to HTML."""
    c = section.content
    html = f'<div class="section" id="section-{section.number}">'
    html += f"<h2>{section.number}. {_esc(section.title)}</h2>"

    if section.number == 1:  # Cover
        html += f"<h1>{_esc(c.get('organization', ''))}</h1>"
        html += f"<p>{_esc(c.get('report_title', ''))}</p>"
        html += f'<p class="score">{c.get("overall_score", 0):.1f}</p>'
        html += f"<p>Overall Privacy Intelligence Score</p>"
        html += f'<p>Confidence: <span class="tier tier-{c.get("vci_label", "")}">{c.get("vci_label", "")}</span></p>'

    elif section.number == 2:  # Executive Summary
        html += f"<p>{_esc(c.get('summary', ''))}</p>"
        takeaways = c.get("takeaways", [])
        if takeaways:
            html += "<h3>Key Takeaways</h3><ul>"
            for t in takeaways:
                html += f"<li>{_esc(t)}</li>"
            html += "</ul>"
        html += f'<p class="cohort-note">Benchmarked against {c.get("cohort_size", 0)} peers as of {c.get("cohort_date", "")}.</p>'

    elif section.number == 3:  # Risk Dashboard
        html += "<table><tr><th>Metric</th><th>Score</th><th>Level</th></tr>"
        metrics = [
            ("Overall Intelligence", c.get("overall_intelligence", 0), ""),
            ("Regulatory Exposure", c.get("regulatory_exposure", 0), c.get("regulatory_tier", "")),
            ("Disclosure Maturity", c.get("disclosure_maturity", 0), ""),
            ("Transparency", c.get("transparency", 0), ""),
            ("AI Transparency", c.get("ai_transparency", 0), ""),
            ("Compound Risk", c.get("compound_risk", 0), ""),
        ]
        for name, score, tier in metrics:
            tier_cls = f"tier-{tier}" if tier else ""
            tier_html = f'<span class="tier {tier_cls}">{tier}</span>' if tier else "—"
            html += f"<tr><td>{name}</td><td>{score:.1f}</td><td>{tier_html}</td></tr>"
        html += "</table>"
        html += f'<p>VCI: {c.get("vci_score", 0):.1f} ({c.get("vci_label", "")})</p>'

    elif section.number == 4:  # Benchmark Intelligence
        html += f'<p>Organization score: <span class="score">{c.get("org_score", 0):.1f}</span></p>'
        html += f"<p>Percentile rank: {c.get('percentile', 0):.1f}th</p>"
        html += f'<p class="cohort-note">{_esc(c.get("cohort_label", ""))}</p>'

    elif section.number == 5:  # Regulator Exposure
        html += f"<p>Regulatory exposure score: {c.get('regulatory_score', 0):.1f} ({c.get('tier', '')})</p>"

    elif section.number == 6:  # Findings Table
        findings = c.get("findings", [])
        html += f"<p>Total findings: {c.get('total', 0)}</p>"
        if findings:
            html += "<table><tr><th>ID</th><th>Domain</th><th>Severity</th><th>Score</th><th>Confidence</th></tr>"
            for f in findings:
                sev_cls = "tier-high" if f["severity"] == "high" else "tier-moderate"
                html += (f'<tr><td>{f["id"]}</td><td>{f["domain"]}</td>'
                         f'<td><span class="tier {sev_cls}">{f["severity"]}</span></td>'
                         f'<td>{f["score"]:.1f}</td><td>{f["confidence"]}</td></tr>')
            html += "</table>"

    elif section.number == 7:  # Compound Risk
        html += f"<p>Compound risk score: {c.get('compound_score', 0):.1f}</p>"

    elif section.number == 8:  # Benchmark Language Comparison
        if not c.get("sme_cleaned_available"):
            html += '<div class="placeholder">Pending SME-cleaned exemplar — this section will be populated once subject-matter expert review is complete.</div>'
        else:
            for entry in c.get("entries", []):
                html += f"<h3>{_esc(entry['domain'])}</h3>"
                html += f"<blockquote>{_esc(entry['exemplar_text'])}</blockquote>"
                html += f"<p><em>{_esc(entry.get('maturity_note', ''))}</em></p>"

    elif section.number == 9:  # Recommendations
        recs = c.get("recommendations", [])
        for r in recs:
            sev = r.get("severity", "medium")
            html += f'<div><span class="tier tier-{"high" if sev == "high" else "moderate"}">{sev}</span> '
            html += f'{_esc(r.get("prose", ""))}</div>'

    elif section.number == 10:  # Risk Reduction
        html += f"<p>High severity: {c.get('high_count', 0)} findings</p>"
        html += f"<p>Medium severity: {c.get('medium_count', 0)} findings</p>"

    elif section.number == 11:  # Source Traceability
        html += f"<p>{_esc(c.get('note', ''))}</p>"

    elif section.number == 12:  # Trend
        html += f"<p>{_esc(c.get('note', ''))}</p>"

    html += "</div>"
    return html


def _esc(text: str) -> str:
    """HTML-escape text."""
    return (text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))
