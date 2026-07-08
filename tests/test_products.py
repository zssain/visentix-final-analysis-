"""Product mapping, white-label feed, and VCI review gate tests.

VICBNF-006: Product mapping returns correct objects per product.
VICBNF-009: White-label feed carries VCI + versioning + permitted_use.
VICBNF-010: Low-VCI objects are gated for analyst review.
"""

import time
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import jwt as pyjwt
import pytest
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.main import app
from app.services.products.mapping import (
    PRODUCTS,
    VCI_ROUTE_FOR_REVIEW,
    VCI_DO_NOT_PRESENT,
    is_object_in_product,
    needs_analyst_review,
    objects_for_product,
    product_includes,
    should_not_present_as_definitive,
    visibility_note,
)
from app.services.review import (
    clear_low_vci_object,
    flag_low_vci_object,
    get_analyst_review_banner,
    get_low_vci_objects,
    reset_reviews,
)


# ── Fixtures ──────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _clean():
    reset_reviews()
    yield
    reset_reviews()


# ── Product mapping (VICBNF-006) ─────────────────────────────

def test_all_four_products_exist():
    assert "one_time" in PRODUCTS
    assert "grc_continuous" in PRODUCTS
    assert "white_label" in PRODUCTS
    assert "quarterly" in PRODUCTS


def test_one_time_includes_all_core_objects():
    objects = objects_for_product("one_time")
    types = {o["object_type"] for o in objects}
    assert "regulatory_exposure" in types
    assert "overall_intelligence" in types
    assert "benchmark_percentile" in types
    assert "disclosure_maturity" in types


def test_white_label_excludes_findings():
    includes = product_includes("white_label")
    assert includes["findings"] is False
    assert includes["recommendations"] is False
    assert includes["vci"] is True


def test_every_product_requires_vci():
    for product_type in PRODUCTS:
        includes = product_includes(product_type)
        assert includes["vci"] is True, f"{product_type} must require VCI"


def test_every_product_requires_cohort_disclosure():
    for product_type in PRODUCTS:
        includes = product_includes(product_type)
        assert includes["cohort_disclosure"] is True, f"{product_type} must disclose cohort"


def test_is_object_in_product():
    assert is_object_in_product("overall_intelligence", "one_time") is True
    assert is_object_in_product("trend_delta", "one_time") is False
    assert is_object_in_product("trend_delta", "grc_continuous") is True


def test_visibility_note_present():
    note = visibility_note("regulatory_exposure", "one_time")
    assert "exposure" in note.lower()
    assert len(note) > 10  # non-trivial guidance


def test_unknown_product_raises():
    with pytest.raises(KeyError):
        objects_for_product("nonexistent_product")


# ── VCI review thresholds (VICBNF-010) ───────────────────────

def test_vci_review_threshold_values():
    assert VCI_ROUTE_FOR_REVIEW == 60
    assert VCI_DO_NOT_PRESENT == 40


def test_needs_analyst_review_low_vci():
    assert needs_analyst_review(39.0) is True  # Very Low
    assert needs_analyst_review(55.0) is True  # Low
    assert needs_analyst_review(60.0) is False  # Moderate — OK


def test_should_not_present_very_low():
    assert should_not_present_as_definitive(35.0) is True
    assert should_not_present_as_definitive(45.0) is False


# ── VCI review gate (VICBNF-010) ─────────────────────────────

def test_flag_low_vci_object():
    flag_low_vci_object("assess-1", "regulatory_exposure", 35.0, 45.0)
    pending = get_low_vci_objects("assess-1")
    assert len(pending) == 1
    assert pending[0]["object_type"] == "regulatory_exposure"
    assert pending[0]["vci_score"] == 35.0


def test_low_vci_banner():
    flag_low_vci_object("assess-1", "regulatory_exposure", 30.0, 40.0)
    banner = get_analyst_review_banner("assess-1")
    assert banner is not None
    assert "pending analyst review" in banner.lower()
    assert "Regulatory Exposure" in banner


def test_no_banner_when_vci_sufficient():
    banner = get_analyst_review_banner("assess-no-flags")
    assert banner is None


def test_clear_low_vci_object():
    flag_low_vci_object("assess-1", "transparency", 45.0, 30.0)
    assert len(get_low_vci_objects("assess-1")) == 1
    clear_low_vci_object("assess-1", "transparency")
    assert len(get_low_vci_objects("assess-1")) == 0


def test_banner_gone_after_clearing():
    flag_low_vci_object("assess-1", "transparency", 45.0, 30.0)
    clear_low_vci_object("assess-1", "transparency")
    assert get_analyst_review_banner("assess-1") is None


# ── White-label feed endpoint (VICBNF-009) ───────────────────

def _make_token():
    now = int(time.time())
    return pyjwt.encode(
        {"sub": "test-user", "aud": "authenticated",
         "iat": now - 60, "exp": now + 3600, "app_role": "admin"},
        settings.supabase_jwt_secret, algorithm="HS256",
    )


@pytest.mark.anyio
async def test_white_label_feed_requires_admin():
    token = pyjwt.encode(
        {"sub": "test", "aud": "authenticated",
         "iat": int(time.time()) - 60, "exp": int(time.time()) + 3600,
         "app_role": "customer"},
        settings.supabase_jwt_secret, algorithm="HS256",
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/feed/white-label",
                        headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 403


@pytest.mark.anyio
async def test_white_label_feed_structure():
    token = _make_token()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/feed/white-label",
                        headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        body = r.json()
        assert "dataset_id" in body
        assert "schema_version" in body
        assert "refresh_date" in body
        assert "permitted_use" in body
        assert "confidence_metadata" in body
        assert "records" in body
        assert isinstance(body["records"], list)


@pytest.mark.anyio
async def test_white_label_feed_records_have_required_fields():
    token = _make_token()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/feed/white-label",
                        headers={"Authorization": f"Bearer {token}"})
        body = r.json()
        for record in body["records"]:
            assert "object_type" in record
            assert "score" in record
            assert "vci" in record
            assert "score" in record["vci"]
            assert "band" in record["vci"]
            assert "formula_version" in record
            assert "permitted_use" in record
            assert "data_dictionary_reference" in record
