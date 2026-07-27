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
import time
from collections import deque
from pathlib import Path
from threading import Lock

import jwt
from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel

from app.config import settings
from app.logging import get_logger

log = get_logger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])

_TOKEN_TTL_HOURS = 24
_USERS_FILE = Path(__file__).parent.parent.parent / "local_users.json"


# ── Login rate limiting (per-account + per-IP) ──────────────────────
#
# Fixed-window counters over failed attempts only; a success clears the
# account+IP counters. In-process (fine for a single replica). NOTE: Azure
# Container Apps can scale to multiple replicas, where an in-memory limiter is
# per-replica — for hard multi-replica limits move this to a shared store
# (platform_setting/Redis). Flagged in RLS-AUDIT.md / LAUNCH-READINESS.md.

_RL_WINDOW_S = 15 * 60          # 15-minute window
_RL_MAX_PER_ACCOUNT = 5         # failed sign-ins per account per window
_RL_MAX_PER_IP = 20             # failed sign-ins per IP per window
_rl_fail: dict[str, deque[float]] = {}
_rl_lock = Lock()


def _rl_key_account(email: str) -> str:
    return f"acct:{(email or '').strip().lower()}"


def _rl_prune(dq: deque[float], now: float) -> None:
    cutoff = now - _RL_WINDOW_S
    while dq and dq[0] < cutoff:
        dq.popleft()


def _rl_check(email: str, ip: str) -> int | None:
    """Return retry-after seconds if locked out, else None."""
    now = time.time()
    with _rl_lock:
        for key, limit in ((_rl_key_account(email), _RL_MAX_PER_ACCOUNT),
                           (f"ip:{ip}", _RL_MAX_PER_IP)):
            dq = _rl_fail.get(key)
            if not dq:
                continue
            _rl_prune(dq, now)
            if len(dq) >= limit:
                return int(dq[0] + _RL_WINDOW_S - now) + 1
    return None


def _rl_record_failure(email: str, ip: str) -> None:
    now = time.time()
    with _rl_lock:
        for key in (_rl_key_account(email), f"ip:{ip}"):
            dq = _rl_fail.setdefault(key, deque())
            _rl_prune(dq, now)
            dq.append(now)


def _rl_clear(email: str, ip: str) -> None:
    with _rl_lock:
        _rl_fail.pop(_rl_key_account(email), None)
        _rl_fail.pop(f"ip:{ip}", None)


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
async def login(body: LoginRequest, request: Request) -> TokenResponse:
    ip = request.client.host if request.client else "unknown"

    # Rate limit BEFORE doing any password work (avoids timing/DoS on hashing).
    retry_after = _rl_check(body.email, ip)
    if retry_after is not None:
        minutes = max(1, round(retry_after / 60))
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(f"Too many sign-in attempts. For your security, please wait "
                    f"about {minutes} minute{'s' if minutes != 1 else ''} and try again."),
            headers={"Retry-After": str(retry_after)},
        )

    users = _load_users()
    user = next((u for u in users if u["email"] == body.email), None)

    if user is None or not _verify_password(body.password, user["salt"], user["password_hash"]):
        _rl_record_failure(body.email, ip)
        log.warning("Failed login attempt for: %s", body.email)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    _rl_clear(body.email, ip)  # success resets the counters
    token = _mint_token(user)
    log.info("Login OK: %s (%s)", user["email"], user["role"])

    return TokenResponse(
        access_token=token,
        user_id=user["id"],
        email=user["email"],
        role=user["role"],
        organization_id=user.get("organization_id"),
    )
