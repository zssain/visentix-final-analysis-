"""SEC-005 — small reusable in-process rate limiter for expensive endpoints.

Fixed-window counters, thread-safe via a Lock (same style as auth.py's login
limiter, `_rl_check`/`_rl_record_failure`). `check_rate_limit(key, limit, window_s)`
raises HTTPException(429, ...) with a Retry-After header once a key exceeds
`limit` requests within the rolling `window_s` seconds.

!!! MULTI-REPLICA MARKER !!!
This limiter lives in PROCESS MEMORY, so its counters are PER-REPLICA. On Azure
Container Apps (which can scale to N replicas) the effective limit becomes N ×
`limit`. This mirrors the known gap already flagged for auth.py's login limiter
(RLS-AUDIT.md / LAUNCH-READINESS.md). For a HARD, cluster-wide limit this MUST be
backed by a shared store (Redis, or a platform_setting counter with atomic
increment).
TODO(SEC-005): swap the in-process `_buckets` dict for a shared Redis-backed
store before running >1 replica with strict throttles. Until then, keep replica
count at 1 for endpoints that rely on this for a real cap (documented per-route).
"""

import time
from collections import deque
from threading import Lock

from fastapi import HTTPException, Request, status

from app.config import settings

# key -> deque[float] of request timestamps within the current window.
# NOTE: per-replica (see module docstring). Pruned lazily on each check.
_buckets: dict[str, deque[float]] = {}
_lock = Lock()


def _prune(dq: "deque[float]", now: float, window_s: int) -> None:
    cutoff = now - window_s
    while dq and dq[0] < cutoff:
        dq.popleft()


def check_rate_limit(
    key: str,
    *,
    limit: int,
    window_s: int,
    now: float | None = None,
) -> None:
    """Record one hit for `key` and raise 429 if it exceeds `limit`/`window_s`.

    Fixed rolling window: keeps the timestamps of hits inside the last
    `window_s` seconds; if that count would exceed `limit`, the request is
    rejected with HTTP 429 and a Retry-After header (seconds until the oldest
    in-window hit ages out). Thread-safe.

    `now` is injectable for deterministic tests (default: time.time()).
    """
    t = time.time() if now is None else now
    with _lock:
        dq = _buckets.setdefault(key, deque())
        _prune(dq, t, window_s)
        if len(dq) >= limit:
            retry_after = int(dq[0] + window_s - t) + 1
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    "Too many requests. Please slow down and retry in a moment."
                ),
                headers={"Retry-After": str(max(1, retry_after))},
            )
        dq.append(t)


def client_key(request: Request, user=None) -> str:
    """Build a rate-limit key that prefers the authenticated user over IP.

    Keying on `user.user_id` is stricter and fairer than IP: it survives NAT
    (many users behind one IP) and shared corporate egress, and it can't be
    dodged by rotating source IPs. Falls back to the peer IP for unauthenticated
    callers.

    X-Forwarded-For is only trusted when `settings.trusted_proxy` is True — behind
    a trusted reverse proxy the real client IP is in that header; without a trusted
    proxy the header is client-controlled and MUST be ignored (else the limit is
    trivially bypassed by spoofing it).
    """
    uid = getattr(user, "user_id", None) if user is not None else None
    if uid:
        return f"user:{uid}"

    ip = None
    if settings.trusted_proxy:
        xff = request.headers.get("X-Forwarded-For", "")
        if xff:
            # Left-most entry is the original client (trusted-proxy contract).
            ip = xff.split(",")[0].strip()
    if not ip:
        ip = request.client.host if request.client else "unknown"
    return f"ip:{ip}"


def reset() -> None:
    """Clear all counters (test helper; not used in request paths)."""
    with _lock:
        _buckets.clear()
