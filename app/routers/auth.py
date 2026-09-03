"""Supabase credential login with application-session JWT issuance."""

import datetime
import time
from collections import deque
from threading import Lock

import jwt
from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel

from app.config import settings
from app.logging import get_logger
from app.services.authentication import LoginIdentity, authenticate_with_supabase

log = get_logger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])

_TOKEN_TTL_HOURS = 24


# ── Login rate limiting (per-account + per-IP) ──────────────────────
#
# Fixed-window counters over failed attempts only; a success clears the
# account+IP counters. In-process (fine for a single replica). NOTE: Azure
# Container Apps can scale to multiple replicas, where an in-memory limiter is
# per-replica — for hard multi-replica limits move this to a shared store
# (platform_setting/Redis). Flagged in logs/archive/2026-08/RLS-AUDIT.md / logs/archive/2026-07/LAUNCH-READINESS.md.

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


def _mint_token(user: LoginIdentity) -> str:
    now = datetime.datetime.now(datetime.UTC)
    payload = {
        "sub": user.user_id,
        "email": user.email,
        "app_role": user.role,
        "organization_id": user.organization_id,
        "partner_id": user.partner_id,
        "third_party_assessment_enabled": user.third_party_assessment_enabled,
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

    user = await authenticate_with_supabase(body.email, body.password)
    if user is None:
        _rl_record_failure(body.email, ip)
        log.warning("Failed login attempt")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    _rl_clear(body.email, ip)  # success resets the counters
    token = _mint_token(user)
    log.info("Login succeeded for user %s", user.user_id)

    return TokenResponse(
        access_token=token,
        user_id=user.user_id,
        email=user.email,
        role=user.role,
        organization_id=user.organization_id,
    )
