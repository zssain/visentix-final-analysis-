"""Explainability API tests — uniform envelopes, glossary decode, legal basis."""

import json
import time
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import jwt as pyjwt
import pytest
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.main import app
from app.routers.explain import GLOSSARY, _decode_title


# ── Helpers ──────────────────────────────────────────────────

_TEST_ORG_ID = str(uuid4())

def _make_token():
    now = int(time.time())
    return pyjwt.encode(
        {"sub": "test-user", "aud": "authenticated",
         "iat": now - 60, "exp": now + 3600, "app_role": "admin",
         "organization_id": _TEST_ORG_ID},
        settings.supabase_jwt_secret, algorithm="HS256",
    )


# ── Glossary decode ──────────────────────────────────────────

def test_glossary_decodes_score():
    title = _decode_title("score", "f002")
    assert title == "Regulatory Exposure"
    assert title != "f002"  # no bare code


def test_glossary_decodes_finding():
    title = _decode_title("finding", "SH-002")
    assert title == "Data Sharing Exposure"
    assert title != "SH-002"


def test_glossary_decodes_domain():
    title = _decode_title("domain", "CR")
    assert title == "Consumer Rights"
    assert title != "CR"


def test_glossary_all_scores_have_entries():
    for key in ["F-002", "F-003", "F-005", "F-006", "F-007", "F-008", "F-010", "F-011"]:
        entry = GLOSSARY["formulas"].get(key, {})
        assert "plain" in entry, f"Missing glossary entry for {key}"
        assert len(entry["plain"]) > 3


def test_glossary_all_findings_have_entries():
    for code in ["AI-004", "TRK-007", "SH-002", "RT-003", "CR-001", "DC-005", "SEC-002", "XB-001"]:
        entry = GLOSSARY["finding_codes"].get(code, {})
        assert "plain" in entry, f"Missing glossary entry for {code}"


def test_glossary_all_domains_have_entries():
    for did in ["CR", "DC", "SH", "RT", "AI", "SEC", "TRK", "XB"]:
        entry = GLOSSARY["domain_ids"].get(did, {})
        assert "plain" in entry, f"Missing glossary entry for {did}"


def test_glossary_no_bare_code_leak():
    """decode must never return a bare short code when a glossary entry exists."""
    for fkey in ["f002", "f005", "f010", "f011"]:
        title = _decode_title("score", fkey)
        assert not title.startswith("f0"), f"Bare code leaked: {title}"


# ── Endpoint auth ────────────────────────────────────────────

@pytest.mark.anyio
async def test_explain_requires_auth():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/reports/test-id/explain?type=score&key=f002")
        assert r.status_code == 401


@pytest.mark.anyio
async def test_explain_all_requires_auth():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/reports/test-id/explain/all")
        assert r.status_code == 401


# ── Envelope structure ───────────────────────────────────────

def test_glossary_has_vci_bands():
    bands = GLOSSARY.get("vci_bands", {})
    for label in ["Very High", "High", "Moderate", "Low", "Very Low"]:
        assert label in bands, f"Missing VCI band: {label}"


def test_glossary_has_maturity_bands():
    bands = GLOSSARY.get("maturity_bands", {})
    for label in ["Leading", "Mature", "Developing", "Lagging", "Deficient"]:
        assert label in bands, f"Missing maturity band: {label}"


def test_glossary_has_org_dimensions():
    dims = GLOSSARY.get("org_dimensions", {})
    for key in ["IC", "RSS", "PGMS", "OSI", "DSI", "EHP", "AIGMS"]:
        assert key in dims, f"Missing org dimension: {key}"


def test_glossary_formulas_have_defined_in():
    """Every formula must have a defined_in path to prevent code drift."""
    for fkey, entry in GLOSSARY.get("formulas", {}).items():
        assert "defined_in" in entry, f"Missing defined_in for {fkey}"
        assert entry["defined_in"].endswith(".py"), f"Invalid defined_in for {fkey}"


# ── Peer comparison never hardcoded ──────────────────────────

def test_peer_comparison_no_hardcoded_values():
    """The glossary and API should never contain n=30 or 2026-06-29."""
    glossary_str = json.dumps(GLOSSARY)
    assert "n=30" not in glossary_str
    assert "2026-06-29" not in glossary_str
    assert "2026-06-19" not in glossary_str
