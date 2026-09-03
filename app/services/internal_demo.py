"""F23 private demo-workspace target registration.

Targets created here are deliberately isolated from existing customer/corpus
organizations, even when a submitted domain matches one. The only reuse is an
explicit ``workspace_target`` edge inside the caller's own workspace.
"""

from __future__ import annotations

import hashlib
import re
from urllib.parse import urlparse
from uuid import uuid4

from app.auth import AuthenticatedUser
from app.db import supabase_rest_get, supabase_rest_post


def normalize_public_domain(source_url: str) -> str:
    hostname = (urlparse(source_url).hostname or "").strip().rstrip(".").lower()
    if hostname.startswith("www."):
        hostname = hostname[4:]
    return hostname.encode("idna").decode("ascii") if hostname else ""


def _target_slug(workspace_id: str, domain: str) -> str:
    label = re.sub(r"[^a-z0-9]+", "-", domain.lower()).strip("-")[:60]
    digest = hashlib.sha256(f"{workspace_id}|{domain}".encode()).hexdigest()[:16]
    return f"demo-target-{digest}-{label}"[:120].rstrip("-")


def _display_name(domain: str) -> str:
    first = domain.split(".", 1)[0].replace("-", " ").strip()
    return first.title() or domain


async def resolve_internal_demo_target(
    user: AuthenticatedUser,
    *,
    source_url: str,
    organization_name: str | None,
) -> str:
    """Resolve/create one target inside an enabled customer's workspace."""
    if (
        user.role != "customer"
        or not user.organization_id
        or not user.third_party_assessment_enabled
    ):
        raise ValueError("internal demo target capability is not enabled")

    workspace_id = user.organization_id
    domain = normalize_public_domain(source_url)
    if not domain:
        raise ValueError("source URL has no public hostname")

    existing = await supabase_rest_get(
        "workspace_target",
        select="target_organization_id",
        filters=(
            f"workspace_organization_id=eq.{workspace_id}"
            f"&normalized_domain=eq.{domain}"
        ),
        limit=1,
    )
    rows = existing.json() if existing.status_code == 200 else []
    if rows:
        return rows[0]["target_organization_id"]

    target_id = str(uuid4())
    slug = _target_slug(workspace_id, domain)
    name = (organization_name or "").strip()[:160] or _display_name(domain)
    organization = {
        "organization_id": target_id,
        "name": name,
        "slug": slug,
        "domain": domain,
        "industry": "unknown",
        "entity_type": "internal_demo_target",
        "tenant_id": workspace_id,
        "origin": "internal_demo_target",
    }
    created = await supabase_rest_post("organization", organization)
    if created.status_code >= 400:
        # A concurrent request may have created the deterministic workspace-only
        # slug. Reuse it only when both provenance fields prove its ownership.
        raced = await supabase_rest_get(
            "organization",
            select="organization_id,tenant_id,origin",
            filters=f"slug=eq.{slug}",
            limit=1,
        )
        candidates = raced.json() if raced.status_code == 200 else []
        if not candidates or candidates[0].get("tenant_id") != workspace_id \
                or candidates[0].get("origin") != "internal_demo_target":
            raise RuntimeError("could not create isolated demo target")
        target_id = candidates[0]["organization_id"]

    mapping = {
        "workspace_organization_id": workspace_id,
        "target_organization_id": target_id,
        "normalized_domain": domain,
        "registered_by": user.user_id,
    }
    linked = await supabase_rest_post("workspace_target", mapping)
    if linked.status_code == 409:
        raced = await supabase_rest_get(
            "workspace_target",
            select="target_organization_id",
            filters=(
                f"workspace_organization_id=eq.{workspace_id}"
                f"&normalized_domain=eq.{domain}"
            ),
            limit=1,
        )
        rows = raced.json() if raced.status_code == 200 else []
        if rows:
            return rows[0]["target_organization_id"]
    if linked.status_code >= 400:
        raise RuntimeError("could not register isolated demo target")
    return target_id

