"""Centralized tenant-scoping — the SEC-003 minimum backstop.

Every customer-scoped Supabase read MUST derive its org filter from
`customer_org_scope()` instead of hand-writing `organization_id=eq.<uuid>`
on each route. This turns tenant isolation from "remember the filter on
every endpoint" (the failure mode that produced SEC-001) into a single
chokepoint that the cross-tenant contract test exercises directly.

Enforcement reality today: the API talks to Postgres as the RLS-bypassing
service role (see `app/db.py`), so this helper is the ONLY thing scoping a
customer's reads — there is no RLS backstop at runtime. Phase 2 (SEC-003
full) is expected to route customer reads through the anon key + the user's
JWT so the existing SELECT policies fire as a genuine second line of
defence; until that lands, this helper is load-bearing and must not be
bypassed on any tenant-scoped resource.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # avoid an import cycle (app.auth has no need to import this)
    from app.auth import AuthenticatedUser


@dataclass(frozen=True)
class OrgScope:
    """The org-scoping decision for one user on a tenant-scoped query.

    Attributes:
        clause: a PostgREST filter fragment that begins with ``&`` and can be
            concatenated onto a query string — e.g. ``&organization_id=eq.<uuid>``
            for a customer, or ``""`` (platform-wide) for ``sme``/``admin``.
        allowed: ``False`` ONLY for a ``customer`` with no ``organization_id``.
            When ``False`` the caller MUST return an empty result and MUST NOT
            issue the query — never fall back to a platform-wide read (that is
            exactly the SEC-001 leak). ``True`` otherwise.
    """

    clause: str
    allowed: bool


def customer_org_scope(
    user: "AuthenticatedUser", *, column: str = "organization_id"
) -> OrgScope:
    """Return the org-scoping decision for ``user`` on a tenant-scoped query.

    - ``customer`` with an org  → scoped to that org (``allowed=True``).
    - ``customer`` with no org  → deny (``allowed=False``); caller returns empty.
    - ``sme`` / ``admin``       → platform-wide (empty clause); they oversee all orgs.

    ``column`` lets a caller scope a table whose org column is named
    differently (e.g. partner tables), defaulting to ``organization_id``.
    """
    if user.role == "customer":
        if not user.organization_id:
            return OrgScope(clause="", allowed=False)
        return OrgScope(clause=f"&{column}=eq.{user.organization_id}", allowed=True)
    # sme / admin (and any non-customer platform role) → platform-wide view.
    return OrgScope(clause="", allowed=True)


def customer_workspace_scope(
    user: "AuthenticatedUser",
    *,
    workspace_column: str = "workspace_organization_id",
    legacy_column: str = "organization_id",
) -> OrgScope:
    """Scope new workspace-owned rows while preserving untouched legacy rows.

    New rows match the explicit workspace column. A row may use the legacy org
    owner only when its workspace column is NULL; this prevents a target's
    ``organization_id`` from becoming an alternate cross-workspace access path.
    The workspace id still comes exclusively from ``customer_org_scope``.
    """
    base = customer_org_scope(user)
    if not base.allowed or user.role != "customer":
        return base
    workspace_id = user.organization_id
    return OrgScope(
        clause=(
            f"&or=({workspace_column}.eq.{workspace_id},"
            f"and({workspace_column}.is.null,{legacy_column}.eq.{workspace_id}))"
        ),
        allowed=True,
    )


def customer_can_access_workspace_row(user: "AuthenticatedUser", row: dict) -> bool:
    """Apply the same new-row/legacy-row ownership rule to one loaded row."""
    if user.role != "customer":
        return True
    if not user.organization_id:
        return False
    workspace_id = row.get("workspace_organization_id")
    if workspace_id is not None:
        return workspace_id == user.organization_id
    return row.get("organization_id") == user.organization_id
