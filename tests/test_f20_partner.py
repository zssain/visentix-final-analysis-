"""F20 — Partner Portal tests.

Guards the MUST-NOTs + ACs: cross-partner isolation (workspace/report/feed);
partner cannot approve or flip the gate (403 everywhere); feed excludes n<10 +
carries no org identity + recomputes live after rehearsal/soft-remove; API keys
hashed + plaintext-once + immediate revocation + access-logged; branded render
leaves the body byte-identical (numbers unchanged) and is deterministic; single
intake path (no forked review); customer tenancy untouched.
"""

import hashlib
import time
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import jwt as pyjwt
import pytest
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.main import app
from app.services import partner as P
from app.services.products.mapping import objects_for_product

_PARTNER_A = str(uuid4())
_PARTNER_B = str(uuid4())
_WS = str(uuid4())
_ORG = str(uuid4())

# A valid white-label object type (don't hardcode — read the product mapping).
_OTYPE = objects_for_product("white_label")[0]["object_type"]


def _token(role="partner_admin", org=None, partner=_PARTNER_A):
    now = int(time.time())
    claims = {"sub": "u", "aud": "authenticated", "iat": now - 60, "exp": now + 3600,
              "app_role": role}
    if org:
        claims["organization_id"] = org
    if partner:
        claims["partner_id"] = partner
    return pyjwt.encode(claims, settings.supabase_jwt_secret, algorithm="HS256")


def _hdr(role="partner_admin", partner=_PARTNER_A, org=None):
    return {"Authorization": f"Bearer {_token(role, org, partner)}"}


class _Resp:
    def __init__(self, data, status_code=200):
        self._data, self.status_code, self.text = data, status_code, ""

    def json(self):
        return self._data


# ── AC-1: cross-partner workspace isolation ──────────────────

@pytest.mark.anyio
async def test_resolve_workspace_cross_partner_invisible():
    async def _get(table, *, select="*", filters="", limit=1000, count=False):
        # workspace belongs to partner A
        return _Resp([{"id": _WS, "partner_id": _PARTNER_A, "client_org_id": _ORG, "name": "Acme"}])
    with patch.object(P, "supabase_rest_get", _get):
        # partner B cannot resolve it
        assert await P.resolve_workspace(_WS, _PARTNER_B, is_admin=False) is None
        # partner A can; our admin can
        assert (await P.resolve_workspace(_WS, _PARTNER_A, is_admin=False))["id"] == _WS
        assert (await P.resolve_workspace(_WS, _PARTNER_B, is_admin=True))["id"] == _WS


# ── AC-2: customer tenancy untouched (partner route rejects customer) ──

@pytest.mark.anyio
async def test_customer_cannot_reach_partner_routes():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/partner/workspaces",
                        headers={"Authorization": f"Bearer {_token(role='customer', partner=None)}"})
    assert r.status_code == 403


def test_authenticated_user_partner_id_default_none():
    from app.auth import AuthenticatedUser
    u = AuthenticatedUser(user_id="x", role="customer")
    assert u.partner_id is None  # existing customers unaffected


# ── AC-3: partner cannot approve or flip gate (single review path) ──

@pytest.mark.anyio
@pytest.mark.parametrize("method,path", [
    ("post", "/review/{}/approve"),
    ("post", "/review/gate-mode"),
    ("get", "/review/queue"),
])
async def test_partner_forbidden_on_review_endpoints(method, path):
    transport = ASGITransport(app=app)
    url = path.format(uuid4())
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        fn = getattr(c, method)
        r = await (fn(url, json={}, headers=_hdr()) if method == "post" else fn(url, headers=_hdr()))
    assert r.status_code == 403, f"{path} should 403 for partner_admin"


# ── AC-4: partner assessment reuses the single intake path, scoped to workspace ──

@pytest.mark.anyio
async def test_partner_assessment_reuses_single_path_scoped_to_workspace():
    seen = {}

    async def _intake(*, user, url=None, text=None, file=None, organization_id=None,
                      organization_name=None):
        seen["org"] = organization_id
        seen["role"] = user.role
        return {"assessment_id": "NID", "organization_id": organization_id, "status": "scored"}

    with patch.object(P, "resolve_workspace",
                      AsyncMock(return_value={"id": _WS, "partner_id": _PARTNER_A, "client_org_id": _ORG})), \
         patch("app.routers.assessments.run_assessment_intake", _intake):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.post(f"/partner/workspaces/{_WS}/assessments",
                             data={"text": "We collect email."}, headers=_hdr())
    assert r.status_code == 201
    assert seen["org"] == _ORG            # scoped to the workspace's client org
    assert seen["role"] == "partner_admin"  # not 'customer' → org param honored


@pytest.mark.anyio
async def test_partner_assessment_cross_partner_workspace_404():
    with patch.object(P, "resolve_workspace", AsyncMock(return_value=None)):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.post(f"/partner/workspaces/{_WS}/assessments",
                             data={"text": "x"}, headers=_hdr(partner=_PARTNER_B))
    assert r.status_code == 404


# ── Feed aggregation reads (shared) ──────────────────────────

def _feed_reads(*, n_big=10, rehearsal=None, cqs=None):
    rehearsal = rehearsal or set()
    orgs = [f"org{i}" for i in range(n_big)] + [f"small{i}" for i in range(3)]
    cqs = cqs if cqs is not None else set(orgs)

    async def _get(table, *, select="*", filters="", limit=1000, count=False):
        if table == "privacy_notice":
            return _Resp([{"organization_id": o} for o in cqs])
        if table == "organization" and "origin=eq.rehearsal" in filters:
            return _Resp([{"organization_id": o} for o in rehearsal])
        if table == "organization":
            # 10 "retail" orgs (big cohort) + 3 "airline" orgs (small cohort)
            rows = [{"organization_id": f"org{i}", "industry": "retail"} for i in range(n_big)]
            rows += [{"organization_id": f"small{i}", "industry": "airline"} for i in range(3)]
            return _Resp(rows)
        if table == "derived_data_item":
            rows = []
            for o in orgs:
                rows.append({"object_type": _OTYPE, "organization_id": o, "score": 55.0,
                             "confidence_score": 0.7, "formula_version_id": "F-010_v1",
                             "generated_at": "2026-07-01"})
            return _Resp(rows)
        return _Resp([])
    return _get


# ── AC-5: feed suppresses n<10, no org identity, carries population_n/schema ──

@pytest.mark.anyio
async def test_feed_suppresses_small_cohorts_and_hides_identity():
    with patch.object(P, "supabase_rest_get", _feed_reads(n_big=10)):
        feed = await P.build_feed_aggregates()
    import json as _json
    blob = _json.dumps(feed)
    assert "organization_id" not in blob            # no member identity (MUST NOT)
    assert feed["schema_version"] == P.FEED_SCHEMA_VERSION
    # retail (n=10) present; airline (n=3) suppressed
    segs = {r["segment"] for r in feed["records"]}
    assert "retail" in segs and "airline" not in segs
    retail = next(r for r in feed["records"] if r["segment"] == "retail")
    assert retail["population_n"] == 10
    assert feed["suppressed_cohort_count"] >= 1
    assert feed["min_cohort_n"] == 10               # OD-05 citation surfaced


# ── AC-5b: live recompute after rehearsal / soft-remove ──────

@pytest.mark.anyio
async def test_feed_recomputes_live_after_rehearsal_marking():
    # First call: retail cohort has 10 → present.
    with patch.object(P, "supabase_rest_get", _feed_reads(n_big=10)):
        before = await P.build_feed_aggregates()
    assert any(r["segment"] == "retail" for r in before["records"])

    # Mark 2 retail orgs rehearsal → n drops to 8 → cohort suppressed on next call.
    with patch.object(P, "supabase_rest_get", _feed_reads(n_big=10, rehearsal={"org0", "org1"})):
        after = await P.build_feed_aggregates()
    assert not any(r["segment"] == "retail" for r in after["records"])  # live exclusion


# ── AC-6 / AC-7: API keys hashed, plaintext once, masked, revoke immediate ──

@pytest.mark.anyio
async def test_api_key_stores_hash_returns_plaintext_once():
    captured = {}

    async def _post(table, payload, **k):
        captured["payload"] = payload
        return _Resp([], 201)
    with patch.object(P, "supabase_rest_post", _post):
        out = await P.create_api_key(_PARTNER_A, "prod")
    plaintext = out["api_key"]
    assert plaintext.startswith("vsx_")
    # Only the HASH is stored — never the plaintext.
    assert captured["payload"]["key_hash"] == hashlib.sha256(plaintext.encode()).hexdigest()
    assert plaintext not in str(captured["payload"])
    assert captured["payload"]["key_last4"] == plaintext[-4:]


@pytest.mark.anyio
async def test_list_api_keys_masked_no_hash():
    async def _get(table, *, select="*", filters="", limit=1000, count=False):
        return _Resp([{"id": "k1", "label": "prod", "key_last4": " abcd"[-4:],
                       "created_at": "t", "last_used_at": None, "revoked_at": None}])
    with patch.object(P, "supabase_rest_get", _get):
        keys = await P.list_api_keys(_PARTNER_A)
    assert keys[0]["masked"].startswith("vsx_…")
    assert "key_hash" not in keys[0] and "api_key" not in keys[0]


@pytest.mark.anyio
async def test_verify_api_key_rejects_revoked_and_accepts_valid():
    plaintext = "vsx_secret"
    # Revoked / unknown → the revoked_at=is.null filter returns nothing → None.
    async def _none(table, *, select="*", filters="", limit=1000, count=False):
        return _Resp([])
    with patch.object(P, "supabase_rest_get", _none):
        assert await P.verify_api_key(plaintext) is None

    async def _hit(table, *, select="*", filters="", limit=1000, count=False):
        assert hashlib.sha256(plaintext.encode()).hexdigest() in filters  # hash-compare
        return _Resp([{"id": "k1", "partner_id": _PARTNER_A, "revoked_at": None}])
    with patch.object(P, "supabase_rest_get", _hit), \
         patch.object(P, "supabase_rest_patch", AsyncMock(return_value=_Resp({}, 204))):
        ctx = await P.verify_api_key(plaintext)
    assert ctx["partner_id"] == _PARTNER_A


@pytest.mark.anyio
async def test_feed_requires_key_or_admin_and_logs_access():
    # No key + non-admin (partner_admin JWT, but feed needs a key) → 403.
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/feed/white-label", headers=_hdr())
    assert r.status_code == 403

    # Valid key path → aggregates served + access logged.
    logged = {}

    async def _log(pid, kid, endpoint, row_count):
        logged.update({"pid": pid, "kid": kid, "rows": row_count})
    with patch.object(P, "verify_api_key", AsyncMock(return_value={"partner_id": _PARTNER_A, "api_key_id": "k1"})), \
         patch.object(P, "build_feed_aggregates", AsyncMock(return_value={"record_count": 2, "records": []})), \
         patch.object(P, "log_feed_access", _log):
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.get("/feed/white-label", headers={"X-Partner-Key": "vsx_x"})
    assert r.status_code == 200
    assert logged["pid"] == _PARTNER_A and logged["rows"] == 2


@pytest.mark.anyio
async def test_feed_rejects_invalid_key():
    transport = ASGITransport(app=app)
    with patch.object(P, "verify_api_key", AsyncMock(return_value=None)):
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.get("/feed/white-label", headers={"X-Partner-Key": "vsx_bad"})
    assert r.status_code == 401


# ── AC-8: branded render — body byte-identical, only header band differs ──

def _sample_report():
    from app.services.report.assembly import ReportPayload, ReportSection
    return ReportPayload(
        assessment_id="NID12345678", organization_name="Acme Retail",
        generated_date="2026-07-28",
        sections=[
            # Section 1 is the cover (PHASE 6 renders it via _render_cover).
            ReportSection(number=1, title="Cover", content={
                "organization": "Acme Retail", "report_title": "Acme",
                "date": "2026-07-18", "overall_score": 61.0, "vci_label": "high"}),
            # Section 2 carries the headline number in the report body.
            ReportSection(number=2, title="Executive Summary", content={
                "summary": "Acme Retail overview.", "overall_score": 61.0,
                "overall_band": "Developing", "takeaways": [],
                "cohort_size": 25, "cohort_date": "2026-07-18"}),
        ],
        cohort_size=25, cohort_date="2026-07-18", vci_label="high",
    )


def test_branding_is_header_only_body_unchanged():
    from app.services.report.renderer import render_html, _render_section
    report = _sample_report()
    plain = render_html(report, None)
    branded = render_html(report, {"partner_id": _PARTNER_A, "partner_name": "LawCo",
                                   "brand_color": "#123456", "logo_url": None})
    # Branded emits the band element; plain does not. (The `.brand-band` CSS class
    # lives in the stylesheet of BOTH renders — check for the emitted <div>.)
    assert '<div class="brand-band"' in branded and '<div class="brand-band"' not in plain
    assert "LawCo" in branded
    # The report BODY is byte-identical apart from the injected band — branding
    # never changes a number or wording. A content section renders verbatim in both.
    body = _render_section(report.sections[1])
    assert body in plain and body in branded
    assert "61.0" in plain and "61.0" in branded  # the headline number is unchanged
    # Rigorous F20: strip the band → the whole document is identical.
    import re
    stripped = re.sub(r'<div class="brand-band".*?</div>', "", branded, count=1, flags=re.S)
    assert stripped == plain


def test_branded_render_is_deterministic():
    from app.services.report.renderer import render_html
    report = _sample_report()
    b = {"partner_id": _PARTNER_A, "partner_name": "LawCo", "brand_color": "#123456", "logo_url": None}
    assert render_html(report, b) == render_html(report, b)  # byte-identical per snapshot


# ── SEC-009: PARTNER_KEY_PEPPER fail-closed in production ─────────────────────

@pytest.mark.anyio
async def test_verify_fails_closed_when_pepper_unset_in_production(monkeypatch):
    """A missing pepper in PRODUCTION must reject partner-key verification, NOT
    silently fall back to unsalted sha256 (which would undo SEC-009)."""
    monkeypatch.setattr(settings, "partner_key_pepper", "")
    monkeypatch.setattr(settings, "app_env", "production")
    # Guard: if this ever fell back to legacy verify it would hit the DB; assert it
    # returns None BEFORE any lookup by failing the test if supabase is called.
    called = {"n": 0}

    async def _boom(*a, **k):
        called["n"] += 1
        raise AssertionError("verify hit the DB instead of failing closed")

    monkeypatch.setattr(P, "supabase_rest_get", _boom, raising=False)
    assert await P.verify_api_key("vsx_anykey") is None
    assert called["n"] == 0


def test_store_fails_closed_when_pepper_unset_in_production(monkeypatch):
    """Minting a new key with no pepper in production must raise, never store a
    weak legacy-hashed key."""
    monkeypatch.setattr(settings, "partner_key_pepper", "")
    monkeypatch.setattr(settings, "app_env", "production")
    with pytest.raises(P.PartnerKeyPepperMissing):
        P._hash_key("vsx_plaintext")


def test_dev_still_allows_legacy_without_pepper(monkeypatch):
    """Dev/local (non-prod) keeps the migration-safe legacy path so local work is
    not blocked by an unset pepper."""
    monkeypatch.setattr(settings, "partner_key_pepper", "")
    monkeypatch.setattr(settings, "app_env", "development")
    assert P._hash_key("vsx_plaintext") == hashlib.sha256(b"vsx_plaintext").hexdigest()


def test_pepper_set_uses_hmac_and_keeps_legacy_candidate(monkeypatch):
    """With a pepper set, stored digest is HMAC (not bare sha256), and verify still
    accepts legacy digests for migration safety."""
    monkeypatch.setattr(settings, "partner_key_pepper", "unit-test-pepper")
    hmac_digest = P._hash_key("vsx_plaintext")
    assert hmac_digest != hashlib.sha256(b"vsx_plaintext").hexdigest()  # peppered, not bare
    assert hmac_digest == P._hmac_hash_key("vsx_plaintext")


# ── AC-9: industries served from the canonical config ────────

@pytest.mark.anyio
async def test_industries_from_config():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/partner/industries", headers=_hdr())
    assert r.status_code == 200
    ids = {row["id"] for row in r.json()}
    assert "retail" in ids and "healthcare" in ids  # canonical taxonomy slugs
