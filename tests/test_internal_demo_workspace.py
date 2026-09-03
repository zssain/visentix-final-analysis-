"""F23 private workspace/target separation and legacy-safe ownership."""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.auth import AuthenticatedUser
from app.services.internal_demo import (
    normalize_public_domain,
    resolve_internal_demo_target,
)
from app.services.tenancy import (
    customer_can_access_workspace_row,
    customer_workspace_scope,
)


WORKSPACE = str(uuid4())
TARGET = str(uuid4())
OTHER = str(uuid4())
USER = str(uuid4())


class _Response:
    def __init__(self, status_code=200, body=None):
        self.status_code = status_code
        self._body = [] if body is None else body

    def json(self):
        return self._body


def _user(*, enabled=True, workspace=WORKSPACE):
    return AuthenticatedUser(
        USER,
        role="customer",
        organization_id=workspace,
        third_party_assessment_enabled=enabled,
    )


def test_domain_normalization_is_hostname_only():
    assert normalize_public_domain("https://WWW.Example.com:443/privacy?q=secret") == "example.com"


@pytest.mark.anyio
async def test_existing_workspace_mapping_is_reused_without_org_mutation():
    async def _get(table, **kwargs):
        assert table == "workspace_target"
        assert f"workspace_organization_id=eq.{WORKSPACE}" in kwargs["filters"]
        return _Response(body=[{"target_organization_id": TARGET}])

    with patch("app.services.internal_demo.supabase_rest_get", _get), \
         patch("app.services.internal_demo.supabase_rest_post", new_callable=AsyncMock) as post:
        result = await resolve_internal_demo_target(
            _user(), source_url="https://example.com/privacy", organization_name="Example"
        )
    assert result == TARGET
    post.assert_not_awaited()


@pytest.mark.anyio
async def test_new_target_is_always_isolated_and_explicitly_linked():
    gets = []
    posts = []

    async def _get(table, **kwargs):
        gets.append((table, kwargs.get("filters", "")))
        return _Response(body=[])

    async def _post(table, payload, **kwargs):
        posts.append((table, payload))
        return _Response(status_code=201)

    with patch("app.services.internal_demo.supabase_rest_get", _get), \
         patch("app.services.internal_demo.supabase_rest_post", _post):
        target_id = await resolve_internal_demo_target(
            _user(),
            source_url="https://www.example.com/privacy",
            organization_name="Example Incorporated",
        )

    assert target_id != WORKSPACE
    assert [table for table, _ in posts] == ["organization", "workspace_target"]
    organization = posts[0][1]
    assert organization["organization_id"] == target_id
    assert organization["tenant_id"] == WORKSPACE
    assert organization["origin"] == "internal_demo_target"
    assert organization["industry"] == "unknown"
    mapping = posts[1][1]
    assert mapping == {
        "workspace_organization_id": WORKSPACE,
        "target_organization_id": target_id,
        "normalized_domain": "example.com",
        "registered_by": USER,
    }
    # The implementation must not search/reuse an existing customer or corpus
    # organization by submitted name/domain.
    assert all(table == "workspace_target" for table, _ in gets)


@pytest.mark.anyio
async def test_disabled_customer_cannot_invoke_internal_target_registration():
    with pytest.raises(ValueError):
        await resolve_internal_demo_target(
            _user(enabled=False),
            source_url="https://example.com/privacy",
            organization_name="Example",
        )


def test_workspace_scope_has_explicit_new_row_and_null_only_legacy_paths():
    scope = customer_workspace_scope(_user())
    assert scope.allowed
    assert f"workspace_organization_id.eq.{WORKSPACE}" in scope.clause
    assert f"workspace_organization_id.is.null,organization_id.eq.{WORKSPACE}" in scope.clause


def test_row_access_prefers_explicit_workspace_and_never_target_id():
    user = _user()
    assert customer_can_access_workspace_row(
        user,
        {"workspace_organization_id": WORKSPACE, "organization_id": TARGET},
    )
    assert not customer_can_access_workspace_row(
        user,
        {"workspace_organization_id": OTHER, "organization_id": WORKSPACE},
    )
    assert customer_can_access_workspace_row(
        user,
        {"workspace_organization_id": None, "organization_id": WORKSPACE},
    )
    assert not customer_can_access_workspace_row(
        user,
        {"workspace_organization_id": None, "organization_id": TARGET},
    )


def test_report_owner_resolves_workspace_before_target():
    from app.routers import reports

    with patch.object(
        reports,
        "_sb_get",
        return_value=[{
            "organization_id": TARGET,
            "workspace_organization_id": WORKSPACE,
        }],
    ):
        assert reports.assessment_org_id("notice-id") == WORKSPACE
