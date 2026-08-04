"""SEC-005 — in-process rate limiter tests.

Deterministic: the limiter takes an injectable `now` clock, so we advance a fake
clock instead of sleeping. Covers: trips (429) after N calls, resets after the
window ages out, per-user keying, and X-Forwarded-For only honored behind a
trusted proxy.
"""

import pytest
from fastapi import HTTPException

from app.services import ratelimit


@pytest.fixture(autouse=True)
def _clean_buckets():
    ratelimit.reset()
    yield
    ratelimit.reset()


class _FakeClock:
    def __init__(self, t: float = 1000.0):
        self.t = t

    def now(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


# ── trips after N calls ──────────────────────────────────────

def test_allows_up_to_limit_then_429():
    clk = _FakeClock()
    for _ in range(3):
        ratelimit.check_rate_limit("k", limit=3, window_s=60, now=clk.now())
    with pytest.raises(HTTPException) as ei:
        ratelimit.check_rate_limit("k", limit=3, window_s=60, now=clk.now())
    assert ei.value.status_code == 429
    assert "Retry-After" in ei.value.headers


# ── resets after the window ──────────────────────────────────

def test_resets_after_window():
    clk = _FakeClock()
    for _ in range(3):
        ratelimit.check_rate_limit("k", limit=3, window_s=60, now=clk.now())
    with pytest.raises(HTTPException):
        ratelimit.check_rate_limit("k", limit=3, window_s=60, now=clk.now())

    # Advance past the window — the earlier hits age out, budget is restored.
    clk.advance(61)
    ratelimit.check_rate_limit("k", limit=3, window_s=60, now=clk.now())  # no raise


def test_partial_window_slides():
    clk = _FakeClock()
    # 2 hits at t0, then advance 30s and add a 3rd — all 3 in a 60s window → trip.
    ratelimit.check_rate_limit("k", limit=3, window_s=60, now=clk.now())
    ratelimit.check_rate_limit("k", limit=3, window_s=60, now=clk.now())
    clk.advance(30)
    ratelimit.check_rate_limit("k", limit=3, window_s=60, now=clk.now())
    with pytest.raises(HTTPException):
        ratelimit.check_rate_limit("k", limit=3, window_s=60, now=clk.now())
    # Advance so the first two (at t0) age out; one hit remains in window → allowed.
    clk.advance(31)  # now t0+61, first two gone, third (t0+30) still in window
    ratelimit.check_rate_limit("k", limit=3, window_s=60, now=clk.now())


# ── keying is per-user ───────────────────────────────────────

def test_keying_is_independent_per_key():
    clk = _FakeClock()
    for _ in range(3):
        ratelimit.check_rate_limit("user:A", limit=3, window_s=60, now=clk.now())
    with pytest.raises(HTTPException):
        ratelimit.check_rate_limit("user:A", limit=3, window_s=60, now=clk.now())
    # A different user's key is untouched.
    ratelimit.check_rate_limit("user:B", limit=3, window_s=60, now=clk.now())


# ── client_key: user beats IP, XFF honored only when trusted ─

class _Req:
    def __init__(self, host="1.2.3.4", xff=None):
        self.headers = {"X-Forwarded-For": xff} if xff else {}

        class _C:
            pass
        c = _C()
        c.host = host
        self.client = c


class _User:
    def __init__(self, uid):
        self.user_id = uid


def test_client_key_prefers_user_id():
    req = _Req(host="9.9.9.9")
    assert ratelimit.client_key(req, _User("u-42")) == "user:u-42"


def test_client_key_falls_back_to_peer_ip(monkeypatch):
    monkeypatch.setattr(ratelimit.settings, "trusted_proxy", False)
    req = _Req(host="5.6.7.8", xff="1.1.1.1")
    # Untrusted → XFF ignored, key on real peer.
    assert ratelimit.client_key(req, None) == "ip:5.6.7.8"


def test_client_key_honors_xff_when_trusted(monkeypatch):
    monkeypatch.setattr(ratelimit.settings, "trusted_proxy", True)
    req = _Req(host="5.6.7.8", xff="1.1.1.1, 5.6.7.8")
    assert ratelimit.client_key(req, None) == "ip:1.1.1.1"


def test_client_key_per_user_isolation_end_to_end():
    """Two users hitting the same endpoint budget independently."""
    clk = _FakeClock()
    ka = ratelimit.client_key(_Req(), _User("A"))
    kb = ratelimit.client_key(_Req(), _User("B"))
    for _ in range(2):
        ratelimit.check_rate_limit(ka, limit=2, window_s=60, now=clk.now())
    with pytest.raises(HTTPException):
        ratelimit.check_rate_limit(ka, limit=2, window_s=60, now=clk.now())
    # B unaffected by A exhausting its budget.
    ratelimit.check_rate_limit(kb, limit=2, window_s=60, now=clk.now())
