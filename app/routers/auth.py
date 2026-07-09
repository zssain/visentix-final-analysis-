"""Local auth router — password login, local JWT issuance.

Users are stored in local_users.json at the project root (never committed with
real credentials; gitignored in production).  Passwords are PBKDF2-SHA256
(260 000 iterations).  Tokens are HS256 JWTs accepted by get_current_user.

To add or change users run:
    python scripts/setup_local_auth.py
"""

import datetime
import hashlib
import hmac
import json
from pathlib import Path

import jwt
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.config import settings
from app.logging import get_logger

log = get_logger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])

_TOKEN_TTL_HOURS = 24
_USERS_FILE = Path(__file__).parent.parent.parent / "local_users.json"


def _load_users() -> list[dict]:
    if not _USERS_FILE.exists():
        return []
    return json.loads(_USERS_FILE.read_text())


def _verify_password(password: str, salt: str, stored_hash: str) -> bool:
    candidate = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), salt.encode(), 260_000
    ).hex()
    return hmac.compare_digest(candidate, stored_hash)


def _mint_token(user: dict) -> str:
    now = datetime.datetime.now(datetime.UTC)
    payload = {
        "sub": user["id"],
        "email": user["email"],
        "app_role": user["role"],
        "organization_id": user.get("organization_id"),
        "aud": "authenticated",
        "iat": now,
        "exp": now + datetime.timedelta(hours=_TOKEN_TTL_HOURS),
    }
    return jwt.encode(payload, settings.supabase_jwt_secret, algorithm="HS256")


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    email: str
    role: str
    organization_id: str | None = None


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest) -> TokenResponse:
    users = _load_users()
    user = next((u for u in users if u["email"] == body.email), None)

    if user is None or not _verify_password(body.password, user["salt"], user["password_hash"]):
        log.warning("Failed login attempt for: %s", body.email)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = _mint_token(user)
    log.info("Login OK: %s (%s)", user["email"], user["role"])

    return TokenResponse(
        access_token=token,
        user_id=user["id"],
        email=user["email"],
        role=user["role"],
        organization_id=user.get("organization_id"),
    )
