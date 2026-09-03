"""Supabase-backed credential verification for the application login route.

The browser never receives the service-role key.  Password verification uses
Supabase Auth's password grant with the public anon key, then the server loads
the matching ``profiles`` row as the authority for application role and
workspace.  Upstream response bodies are deliberately never logged or returned.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.config import settings
from app.db import get_service_headers


@dataclass(frozen=True)
class LoginIdentity:
    user_id: str
    email: str
    role: str
    organization_id: str | None
    partner_id: str | None
    third_party_assessment_enabled: bool


async def authenticate_with_supabase(email: str, password: str) -> LoginIdentity | None:
    """Verify one credential and return its enabled application profile.

    Every rejected state intentionally collapses to ``None`` so the route can
    return one generic response for unknown users, bad passwords, missing
    profiles, disabled Auth users, and upstream rejection.
    """
    normalized_email = email.strip().lower()
    if not normalized_email or not password:
        return None

    anon_headers = {
        "apikey": settings.supabase_anon_key,
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            auth_response = await client.post(
                f"{settings.supabase_url}/auth/v1/token",
                params={"grant_type": "password"},
                headers=anon_headers,
                json={"email": normalized_email, "password": password},
            )
            if auth_response.status_code != 200:
                return None

            auth_payload = auth_response.json()
            auth_user = auth_payload.get("user") or {}
            user_id = str(auth_user.get("id") or "")
            verified_email = str(auth_user.get("email") or normalized_email).strip().lower()
            if not user_id:
                return None

            profile_response = await client.get(
                f"{settings.supabase_url}/rest/v1/profiles",
                params={
                    "select": (
                        "role,organization_id,partner_id,"
                        "third_party_assessment_enabled"
                    ),
                    "user_id": f"eq.{user_id}",
                    "limit": "1",
                },
                headers=get_service_headers(),
            )
            if profile_response.status_code != 200:
                return None
            profiles = profile_response.json()
            if not profiles:
                return None
            profile = profiles[0]
    except (httpx.HTTPError, ValueError, TypeError):
        return None

    role = str(profile.get("role") or "")
    if role not in {"customer", "sme", "admin", "partner_admin"}:
        return None
    return LoginIdentity(
        user_id=user_id,
        email=verified_email,
        role=role,
        organization_id=profile.get("organization_id"),
        partner_id=profile.get("partner_id"),
        third_party_assessment_enabled=bool(
            profile.get("third_party_assessment_enabled") is True
        ),
    )
