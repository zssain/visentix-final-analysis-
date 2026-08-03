"""F21 — Quarterly report endpoints.

Public routes (`/quarterly/*`) serve ONLY approved, anonymized, suppression-safe
snapshots — never drafts, never suppressed metrics. Admin routes
(`/admin/quarterly/*`) build, preview (watermarked draft), inspect the
anonymization gate, and approve through the expert-review permission.
"""

import html as _html
import json

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import Response

from app.auth import AuthenticatedUser, require_role
from app.logging import get_logger
from app.services import quarterly as Q

log = get_logger(__name__)

# Public reader surface (no auth — approved + suppression-safe only).
public_router = APIRouter(prefix="/quarterly", tags=["quarterly"])
# Admin/expert surface.
admin_router = APIRouter(prefix="/admin/quarterly", tags=["quarterly-admin"])


# ── Public ───────────────────────────────────────────────────

@public_router.get("/latest")
async def latest():
    payload = await Q.get_latest_approved()
    if not payload:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No approved quarterly report yet.")
    return payload


# NB: the `.pdf` route MUST be declared before the bare `/{quarter}` route.
# FastAPI matches in registration order and `{quarter}` captures any non-slash
# text (including a trailing ".pdf"), so a bare route declared first would
# swallow "/2026-Q3.pdf" as quarter="2026-Q3.pdf" and 404.
@public_router.get("/{quarter}.pdf")
async def public_pdf(quarter: str):
    """Approved editorial PDF (public). Drafts are NEVER served here — the
    watermarked draft preview lives on the admin route."""
    payload = await Q.get_by_quarter(quarter)
    if not payload:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No approved report for that quarter.")
    pdf = _render_pdf(payload, watermark=False)
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="quarterly-{quarter}.pdf"'})


@public_router.get("/{quarter}")
async def by_quarter(quarter: str):
    if quarter == "latest":  # defensive: /quarterly/latest handled above
        return await latest()
    payload = await Q.get_by_quarter(quarter)
    if not payload:  # not approved (or nonexistent) → never leak a draft
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No approved report for that quarter.")
    return payload


# ── Admin / expert ───────────────────────────────────────────

@admin_router.post("/build", status_code=status.HTTP_201_CREATED)
async def build(body: dict, user: AuthenticatedUser = require_role("admin")):
    quarter = (body.get("quarter") or "").strip()
    try:
        out = await Q.build_quarterly(quarter)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    return out  # {snapshot_id, quarter, gate_result, metric_count}


@admin_router.get("")
async def list_snapshots(user: AuthenticatedUser = require_role("admin")):
    return await Q.list_all_snapshots()


# NB: the `.pdf` route MUST be declared before the bare `/{snapshot_id}` route —
# `{snapshot_id}` captures a trailing ".pdf", so a bare route declared first
# would swallow "/<id>.pdf" as snapshot_id="<id>.pdf" and 404 (this is exactly
# the bug the authenticated Preview PDF request exposed).
@admin_router.get("/{snapshot_id}.pdf")
async def admin_pdf(snapshot_id: str, user: AuthenticatedUser = require_role("admin")):
    """Draft (gold watermark) or approved preview for the expert."""
    out = await Q.get_admin_snapshot(snapshot_id)
    if not out:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Snapshot not found.")
    snap = out["snapshot"]
    approved = snap["status"] == "approved"
    payload = {
        "quarter": snap["quarter"], "status": snap["status"],
        "metrics": [m for m in out["metrics"] if not m["suppressed"]],
        "methodology": out["methodology"],
    }
    pdf = _render_pdf(payload, watermark=not approved)
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="quarterly-{snap["quarter"]}-{snap["status"]}.pdf"'})


@admin_router.get("/{snapshot_id}")
async def admin_detail(snapshot_id: str, user: AuthenticatedUser = require_role("admin")):
    out = await Q.get_admin_snapshot(snapshot_id)
    if not out:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Snapshot not found.")
    return out


@admin_router.post("/{snapshot_id}/approve")
async def approve(snapshot_id: str, user: AuthenticatedUser = require_role("sme", "admin")):
    """Expert approval — reuses the SAME review-permission gate as assessment
    approval (sme|admin). Records approver identity; requires the gate passed."""
    try:
        out = await Q.approve_quarterly(snapshot_id, user.user_id)
    except ValueError as e:
        code = status.HTTP_404_NOT_FOUND if str(e) == "snapshot_not_found" else status.HTTP_400_BAD_REQUEST
        raise HTTPException(code, str(e))
    return out


# ── Editorial PDF render (weasyprint) ────────────────────────

def _render_pdf(payload: dict, watermark: bool) -> bytes:
    html = _render_html(payload, watermark)
    try:
        import weasyprint
        return weasyprint.HTML(string=html).write_pdf()
    except Exception as e:  # pragma: no cover — surfaced honestly, never a fake PDF
        log.error("quarterly PDF render failed: %s", e)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "PDF render unavailable.")


def _esc(s) -> str:
    return _html.escape(str(s if s is not None else ""))


def _render_html(payload: dict, watermark: bool) -> str:
    m = payload.get("methodology", {})
    corpus = m.get("corpus", {})
    by_id = {x["metric_id"]: x for x in payload.get("metrics", [])}

    def _v(mid):
        return by_id.get(mid, {}).get("value")

    # indicator cards
    dmi, ai = _v("S4-005"), _v("S4-006")
    cards = ""
    if dmi is not None:
        cards += f'<div class="card"><div class="cv">{dmi}</div><div class="cl">Disclosure Maturity Index</div></div>'
    if ai is not None:
        cards += f'<div class="card"><div class="cv">{ai}</div><div class="cl">AI Transparency Index</div></div>'

    # gaps + themes
    def _list(mid, key, fmt):
        row = by_id.get(mid, {})
        try:
            items = json.loads(row.get("value_label") or "[]")
        except (ValueError, TypeError):
            items = []
        return "".join(fmt(i) for i in items) if items else "<li>—</li>"

    gaps = _list("GAPS", "code", lambda i: f'<li>{_esc(i.get("code"))} · {_esc(i.get("prevalence_pct"))}% of corpus</li>')
    themes = _list("S4-018", "theme", lambda i: f'<li>{_esc(i.get("theme"))} · {_esc(i.get("share_pct"))}%</li>')

    wm = ('<div style="position:fixed;top:40%;left:15%;font-size:80px;color:#f0c96b;'
          'opacity:.25;transform:rotate(-30deg);">DRAFT</div>') if watermark else ""

    meth_rows = "".join(
        f"<tr><td>{_esc(k)}</td><td>{_esc(v)}</td></tr>"
        for k, v in [
            ("Quarter", m.get("quarter")),
            ("Data window", " to ".join(m.get("quarter_window") or [])),
            ("Organizations analyzed", corpus.get("organizations")),
            ("Clauses analyzed", corpus.get("clauses_analyzed")),
            ("Industries benchmarked", corpus.get("industries_benchmarked")),
            ("Jurisdictions covered", corpus.get("jurisdictions_covered")),
            ("Population criteria", m.get("population_criteria")),
            ("Formula versions", json.dumps(m.get("formula_versions"))),
            ("Suppression rule", m.get("suppression_rule")),
            ("S4-002 note", m.get("s4_002_note")),
            ("S4-018 note", m.get("s4_018_note")),
            ("Weighting", m.get("weighting")),
        ] if v is not None)

    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>Quarterly Privacy Intelligence — {_esc(payload.get("quarter"))}</title>
<style>
 body{{font-family:'Segoe UI',system-ui,sans-serif;margin:40px;color:#1a1a2e;}}
 h1{{color:#0f3460;border-bottom:3px solid #0f3460;padding-bottom:8px;}}
 .baseline{{background:#fef9e7;border:1px solid #f0c96b;padding:8px 12px;border-radius:6px;font-size:.85em;margin:12px 0;}}
 .cards{{display:flex;gap:16px;margin:18px 0;}}
 .card{{border:1px solid #d1d5db;border-radius:8px;padding:16px 22px;}}
 .cv{{font-size:2em;font-weight:bold;color:#0f3460;}} .cl{{font-size:.8em;color:#6b7280;}}
 h2{{color:#0f3460;margin-top:28px;}} ul{{line-height:1.7;}}
 table{{border-collapse:collapse;width:100%;margin-top:10px;font-size:.85em;}}
 td{{border:1px solid #e0e0e0;padding:6px 10px;}} td:first-child{{font-weight:600;width:32%;}}
</style></head><body>
{wm}
<h1>Quarterly Global Privacy Intelligence Report — {_esc(payload.get("quarter"))}</h1>
<div class="baseline">{_esc(m.get("baseline_note"))}</div>
<div class="cards">{cards or '<div class="cl">Indicators suppressed for this edition.</div>'}</div>
<h2>Top disclosure gaps</h2><ul>{gaps}</ul>
<h2>Enforcement theme shares (resolved records only)</h2><ul>{themes}</ul>
<h2>Methodology</h2><p>{_esc(m.get("intro"))}</p><table>{meth_rows}</table>
</body></html>"""
