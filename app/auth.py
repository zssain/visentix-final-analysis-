"""JWT verification and role-based access control.

Validates Supabase-issued JWTs, loads user profile (role + org),
and provides role-gating dependencies for route handlers.
"""

from typing import Annotated

import httpx
import jwt
from fastapi import Depends, HTTPException, Request, status

from app.config import Settings, settings
from app.db import get_service_headers
from app.logging import get_logger

log = get_logger(__name__)


class AuthenticatedUser:
    """Represents a verified user attached to a request."""

    __slots__ = ("user_id", "role", "organization_id", "email")

    def __init__(
        self,
        user_id: str,
        role: str = "customer",
        organization_id: str | None = None,
        email: str = "",
    ):
        self.user_id = user_id
        self.role = role
        self.organization_id = organization_id
        self.email = email

    def has_role(self, *roles: str) -> bool:
        return self.role in roles


def _extract_token(request: Request) -> str:
    """Extract Bearer token from Authorization header."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
        )
    return auth_header[7:]


_jwks_client = None


def _get_jwks_client():
    """Lazy-init JWKS client for ES256 verification."""
    global _jwks_client
    if _jwks_client is None:
        from jwt import PyJWKClient
        jwks_url = f"{settings.supabase_url}/auth/v1/.well-known/jwks.json"
        _jwks_client = PyJWKClient(
            jwks_url,
            headers={"apikey": settings.supabase_anon_key},
            cache_keys=True,
            lifespan=3600,
        )
    return _jwks_client


def _decode_jwt(token: str, cfg: Settings) -> dict:
    """Decode and verify a Supabase JWT (supports ES256 + HS256 fallback)."""
    # Try ES256 via JWKS first (newer Supabase projects)
    try:
        header = jwt.get_unverified_header(token)
        if header.get("alg") == "ES256":
            jwks_client = _get_jwks_client()
            signing_key = jwks_client.get_signing_key_from_jwt(token)
            return jwt.decode(
                token, signing_key.key,
                algorithms=["ES256"],
                audience="authenticated",
            )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.InvalidTokenError:
        pass  # fall through to HS256
    except Exception:
        pass  # JWKS unavailable, fall through

    # Fallback: HS256 with JWT secret
    try:
        return jwt.decode(
            token, cfg.supabase_jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


async def _load_profile(user_id: str) -> dict | None:
    """Fetch the user's profile from the profiles table (server-side, bypasses RLS)."""
    headers = get_service_headers()
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(
            f"{settings.supabase_url}/rest/v1/profiles"
            f"?select=role,organization_id&user_id=eq.{user_id}&limit=1",
            headers=headers,
        )
        if r.status_code == 200 and r.json():
            return r.json()[0]
    return None


async def get_current_user(request: Request) -> AuthenticatedUser:
    """FastAPI dependency — verify JWT and return AuthenticatedUser."""
    token = _extract_token(request)
    payload = _decode_jwt(token, settings)

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing sub claim",
        )

    email = payload.get("email", "")

    # Local-auth tokens embed role + org directly — no profile lookup needed.
    app_role = payload.get("app_role")
    if app_role:
        return AuthenticatedUser(
            user_id=user_id,
            role=app_role,
            organization_id=payload.get("organization_id"),
            email=email,
        )

    # Supabase-auth tokens: load role from profiles table.
    profile = await _load_profile(user_id)
    if profile is None:
        log.info("No profile found for user %s, defaulting to customer", user_id)
        return AuthenticatedUser(user_id=user_id, role="customer", email=email)

    return AuthenticatedUser(
        user_id=user_id,
        role=profile["role"],
        organization_id=profile.get("organization_id"),
        email=email,
    )


# Type alias for dependency injection
CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user)]


def require_role(*allowed_roles: str):
    """Return a dependency that enforces role membership."""

    async def _check(user: CurrentUser) -> AuthenticatedUser:
        if not user.has_role(*allowed_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{user.role}' not permitted. Requires: {allowed_roles}",
            )
        return user

    return Depends(_check)
