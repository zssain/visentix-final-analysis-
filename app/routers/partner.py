"""F20 — Partner Portal endpoints.

Tenancy through the workspace bridge (partner → workspace → one client org);
reused intake+score path; API-key management; branded PDF that reads frozen
branding from the snapshot. Role: partner_admin (our admin allowed for
oversight). No forked review — partners cannot approve or flip the gate.
"""

import hashlib
import json
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.auth import AuthenticatedUser, require_role
from app.config import settings
from app.db import get_service_headers, supabase_rest_patch
from app.logging import get_logger
from app.services import partner as P
from app.services.intake.extract import extract_from_upload

log = get_logger(__name__)

router = APIRouter(prefix="/partner", tags=["partner"])

_INDUSTRY_CFG = None
MAX_LOGO_BYTES = 2 * 1024 * 1024  # 2 MB image cap (F20 branding)


def _partner_ctx(user: AuthenticatedUser) -> tuple[Optional[str], bool]:
    """Return (partner_id, is_admin). partner_admin uses its claim; admin is oversight."""
    is_admin = user.role == "admin"
    return (user.partner_id, is_admin)


def _require_partner_id(user: AuthenticatedUser) -> str:
    if not user.partner_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "No partner on your account — a partner_id is required.")
    return user.partner_id


# ── Typed request bodies (SEC-010) ───────────────────────────

class ClientOrgIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=300)
    industry: Optional[str] = Field(default=None, max_length=100)


class CreateWorkspaceIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=300)
    client_org: ClientOrgIn


class CreateApiKeyIn(BaseModel):
    label: Optional[str] = Field(default="", max_length=200)


# ── Workspaces ───────────────────────────────────────────────

@router.post("/workspaces", status_code=status.HTTP_201_CREATED)
async def create_workspace(body: CreateWorkspaceIn,
                           user: AuthenticatedUser = require_role("partner_admin", "admin")):
    partner_id = _require_partner_id(user)
    name = body.name.strip()
    client_org = body.client_org.model_dump()
    if not name or not client_org["name"].strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "name and client_org.name are required.")
    industry = client_org.get("industry")
    if industry and industry not in _industry_ids():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unknown industry: {industry}")
    return await P.create_workspace(partner_id, name, client_org)


@router.get("/workspaces")
async def list_workspaces(user: AuthenticatedUser = require_role("partner_admin", "admin")):
    partner_id, is_admin = _partner_ctx(user)
    if not is_admin and not partner_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No partner on your account.")
    return await P.list_workspaces(partner_id, is_admin)


@router.post("/workspaces/{workspace_id}/assessments", status_code=status.HTTP_201_CREATED)
async def create_workspace_assessment(
    workspace_id: str,
    user: AuthenticatedUser = require_role("partner_admin", "admin"),
    url: Optional[str] = Form(None),
    text: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
):
    """Run the SAME intake+score path under the workspace's client org.

    The org is resolved from the workspace (never client-supplied) and the
    assessment is created draft + enqueued to the SAME SME workbench. There is
    no partner gate bypass — gate mode applies identically.
    """
    partner_id, is_admin = _partner_ctx(user)
    ws = await P.resolve_workspace(workspace_id, partner_id, is_admin)
    if ws is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Workspace not found.")

    # Reuse the extended /assessments/ core (single path, no fork). Role is not
    # 'customer', so organization_id is honored → the workspace's client org.
    from app.routers.assessments import run_assessment_intake
    return await run_assessment_intake(
        user=user, url=url, text=text, file=file,
        organization_id=ws["client_org_id"],
    )


# ── Branded report PDF ───────────────────────────────────────

@router.get("/reports/{snapshot_id}.pdf")
async def branded_report_pdf(snapshot_id: str, user: AuthenticatedUser = require_role("partner_admin", "admin")):
    """Branded PDF for a snapshot the caller's partner owns. Body numbers are
    identical to our render; only the header band differs. Byte-identical per
    snapshot (branding frozen at approval)."""
    partner_id, is_admin = _partner_ctx(user)

    snap = _load_snapshot(snapshot_id)
    if not snap:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Snapshot not found.")
    org_id = snap.get("organization_id")

    # Tenancy: the snapshot's org must belong to one of the caller's workspaces.
    owner = await P.get_partner_for_org(org_id)
    if not is_admin and (not owner or owner["id"] != partner_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Snapshot not found.")

    branding = await _resolve_branding(snap, snapshot_id)
    report = _report_from_snapshot(snap)

    from app.services.report.renderer import render_pdf
    pdf_bytes = await render_pdf(report, renderer=settings.renderer, branding=branding)
    return Response(
        content=pdf_bytes, media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="report-{snapshot_id[:12]}.pdf"'},
    )


def _load_snapshot(snapshot_id: str) -> dict | None:
    import httpx
    with httpx.Client(timeout=15) as client:
        r = client.get(
            f"{settings.supabase_url}/rest/v1/report_snapshot"
            f"?select=snapshot_id,organization_id,notice_id,rendered_report,branding_applied"
            f"&snapshot_id=eq.{snapshot_id}&limit=1",
            headers=get_service_headers(),
        )
    rows = r.json() if r.status_code == 200 else []
    return rows[0] if rows else None


def _report_from_snapshot(snap: dict):
    from app.services.report.assembly import ReportPayload, ReportSection
    rendered = snap.get("rendered_report")
    stored = json.loads(rendered) if isinstance(rendered, str) else (rendered or {})
    sections = [
        ReportSection(number=s["number"], title=s["title"], content=s.get("content", {}))
        for s in stored.get("sections", [])
    ]
    return ReportPayload(
        assessment_id=stored.get("assessment_id", snap.get("notice_id", "")),
        organization_name=stored.get("organization_name", ""),
        generated_date=stored.get("generated_date", ""),
        sections=sections,
        cohort_size=stored.get("cohort_size", 0),
        cohort_date=stored.get("cohort_date", ""),
        vci_label=stored.get("vci_label", ""),
    )


async def _resolve_branding(snap: dict, snapshot_id: str) -> dict | None:
    """Branding dict for the render. Prefers the frozen branding_applied; for
    pre-F20 snapshots (NULL) it freezes at first render (frozen_at='first_render')."""
    applied = snap.get("branding_applied")
    if isinstance(applied, str):
        applied = json.loads(applied) if applied else None

    partner = await P.get_partner_for_org(snap.get("organization_id"))
    if not partner:
        return None

    if not applied:
        # Fallback freeze at first branded render (recorded honestly).
        applied = {"partner_id": partner["id"], "logo_hash": partner.get("logo_hash"),
                   "brand_color": partner.get("brand_color"), "frozen_at": "first_render"}
        await supabase_rest_patch("report_snapshot", f"snapshot_id=eq.{snapshot_id}",
                                  {"branding_applied": applied})

    # Enrich the frozen record with display fields (name/logo) for the header band.
    return {
        "partner_id": applied.get("partner_id"),
        "partner_name": partner.get("name", ""),
        "logo_url": partner.get("logo_url"),
        "brand_color": applied.get("brand_color") or partner.get("brand_color"),
        "frozen_at": applied.get("frozen_at"),
    }


# ── API keys ─────────────────────────────────────────────────

@router.post("/api-keys", status_code=status.HTTP_201_CREATED)
async def create_api_key(body: CreateApiKeyIn,
                         user: AuthenticatedUser = require_role("partner_admin", "admin")):
    """Returns the plaintext key ONCE. Only its hash is stored."""
    partner_id = _require_partner_id(user)
    return await P.create_api_key(partner_id, (body.label or "").strip())


@router.get("/api-keys")
async def list_api_keys(user: AuthenticatedUser = require_role("partner_admin", "admin")):
    partner_id = _require_partner_id(user)
    return await P.list_api_keys(partner_id)


@router.delete("/api-keys/{key_id}")
async def revoke_api_key(key_id: str, user: AuthenticatedUser = require_role("partner_admin", "admin")):
    partner_id = _require_partner_id(user)
    if not await P.revoke_api_key(partner_id, key_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Key not found.")
    return {"revoked": True, "api_key_id": key_id}


# ── Branding settings ────────────────────────────────────────

@router.put("/branding")
async def set_branding(
    user: AuthenticatedUser = require_role("partner_admin", "admin"),
    brand_color: Optional[str] = Form(None),
    logo: Optional[UploadFile] = File(None),
):
    """Set brand color + logo (magic-byte image validation, 2 MB cap). Changing
    branding NEVER mutates an already-frozen snapshot's PDF."""
    partner_id = _require_partner_id(user)
    updates: dict = {}
    if brand_color:
        updates["brand_color"] = brand_color[:32]
    if logo is not None:
        raw = await logo.read()
        if len(raw) > MAX_LOGO_BYTES:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Logo exceeds the 2 MB cap.")
        # Reuse F01 upload validation (magic bytes) — reject non-image content.
        try:
            _text, _hash, _kind, mime = extract_from_upload(raw, logo.filename or "logo")
        except Exception:
            mime = ""
        if not (mime or "").startswith("image/"):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Logo must be an image (png/jpeg/gif/webp).")
        updates["logo_hash"] = hashlib.sha256(raw).hexdigest()
        # NOTE: object storage of the bytes is out of scope for v1; logo_url is
        # set via a separate storage step. We persist the hash (branding freeze).
    if not updates:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Nothing to update.")
    await supabase_rest_patch("partner", f"id=eq.{partner_id}", updates)
    return {"updated": list(updates.keys())}


# ── Canonical industries (frontend dropdown fetches, never hardcodes) ──

def _load_industry_cfg() -> dict:
    global _INDUSTRY_CFG
    if _INDUSTRY_CFG is None:
        from pathlib import Path
        p = Path(__file__).resolve().parents[2] / "config" / "org_profile_weights.json"
        with open(p) as f:
            _INDUSTRY_CFG = json.load(f).get("industry_taxonomy", {})
    return _INDUSTRY_CFG


def _industry_ids() -> set[str]:
    tax = _load_industry_cfg()
    if isinstance(tax, dict):
        return set(tax.keys())
    if isinstance(tax, list):
        return {t.get("id") for t in tax if isinstance(t, dict)}
    return set()


@router.get("/industries")
async def list_industries(user: AuthenticatedUser = require_role("partner_admin", "admin")):
    """Canonical industry taxonomy for the New-Client dropdown."""
    tax = _load_industry_cfg()
    if isinstance(tax, dict):
        return [{"id": k, "label": (v.get("label") if isinstance(v, dict) else str(v)) or k}
                for k, v in tax.items()]
    return tax
