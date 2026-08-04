"""AI-002 (retry transient HTTP errors + honest DEGRADED fallback) and
AI-004 (taxonomy-aware classifier prompt) for app/services/llm.py.

All network I/O is mocked (httpx.AsyncClient.post is patched) so these tests
never touch a real Ollama / hosted-Qwen endpoint. asyncio.sleep is patched to a
no-op so the bounded backoff does not actually wait.
"""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.services import llm as llm_mod
from app.services.llm import (
    CLASSIFY_PROMPT_VERSION,
    LLMClient,
    _build_classify_prompt,
    _degraded_result,
)

TAXONOMY = [
    "data_sharing", "tracking_cookies", "consumer_rights", "cross_border",
    "sensitive_data", "retention", "children_teens", "ai_automated_decisions", "other",
]


def _make_client() -> LLMClient:
    """A LLMClient bound to the local backend without running __init__."""
    c = LLMClient.__new__(LLMClient)
    c._backend = "local"
    return c


class _FakeResponse:
    """Minimal stand-in for httpx.Response used by _chat_local."""

    def __init__(self, status_code: int, json_body: dict | None = None):
        self.status_code = status_code
        self._json = json_body or {}
        self.request = httpx.Request("POST", "http://test/api/chat")

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"HTTP {self.status_code}",
                request=self.request,
                response=httpx.Response(self.status_code, request=self.request),
            )

    def json(self):
        return self._json


def _ok_body(category: str = "data_sharing", confidence: float = 0.9) -> dict:
    return {"message": {"content": f'{{"category": "{category}", "confidence": {confidence}}}'}}


# ── AI-002: retry transient HTTP status errors ───────────────────────────────

@pytest.mark.anyio
async def test_503_then_200_is_retried_and_succeeds():
    """A 503 (GPU cold start) followed by a 200 → retried, classification succeeds."""
    client = _make_client()

    responses = [_FakeResponse(503), _FakeResponse(200, _ok_body("data_sharing", 0.9))]
    post_mock = AsyncMock(side_effect=responses)

    class _FakeAsyncClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        post = post_mock

    with patch("app.services.llm.httpx.AsyncClient", _FakeAsyncClient), \
         patch("app.services.llm.asyncio.sleep", new=AsyncMock()):
        result = await client.classify("We share data with partners.", TAXONOMY)

    assert post_mock.await_count == 2, "should have retried once after the 503"
    assert result["category"] == "data_sharing"
    assert result["confidence"] == 0.9
    assert not result.get("degraded"), "a successful classification is NOT degraded"


@pytest.mark.anyio
async def test_400_is_not_retried_and_falls_back_once():
    """A 400 (permanent bad request) → NOT retried; falls back once to DEGRADED."""
    client = _make_client()

    post_mock = AsyncMock(return_value=_FakeResponse(400))

    class _FakeAsyncClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        post = post_mock

    sleep_mock = AsyncMock()
    with patch("app.services.llm.httpx.AsyncClient", _FakeAsyncClient), \
         patch("app.services.llm.asyncio.sleep", new=sleep_mock):
        result = await client.classify("We share data.", TAXONOMY)

    assert post_mock.await_count == 1, "400 is permanent — must NOT be retried"
    assert sleep_mock.await_count == 0, "no backoff sleep for a permanent 4xx"
    assert result["category"] == "other"
    assert result.get("degraded") is True


@pytest.mark.anyio
async def test_persistent_503_exhausts_retries_then_degrades():
    """A 503 on every attempt → retries exhausted (MAX_RETRIES) → DEGRADED fallback."""
    client = _make_client()

    post_mock = AsyncMock(return_value=_FakeResponse(503))

    class _FakeAsyncClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        post = post_mock

    with patch("app.services.llm.httpx.AsyncClient", _FakeAsyncClient), \
         patch("app.services.llm.asyncio.sleep", new=AsyncMock()):
        result = await client.classify("We share data.", TAXONOMY)

    assert post_mock.await_count == llm_mod.MAX_RETRIES
    assert result["category"] == "other"
    assert result.get("degraded") is True


# ── AI-002: honest DEGRADED signal on fallback ───────────────────────────────

@pytest.mark.anyio
async def test_degraded_fallback_zeroes_confidence_and_flags():
    """When _chat raises (any transient error path), the result is honestly DEGRADED,
    not a pretend-full-success 0.5 confidence."""
    client = _make_client()

    async def boom(system, user):
        raise httpx.ReadTimeout("timed out")

    with patch.object(client, "_chat", side_effect=boom):
        result = await client.classify("We share data.", TAXONOMY)

    assert result["category"] == "other"
    assert result["confidence"] == 0.0
    assert result["degraded"] is True


def test_degraded_result_shape():
    assert _degraded_result() == {"category": "other", "confidence": 0.0, "degraded": True}


@pytest.mark.anyio
async def test_successful_classification_not_flagged_degraded():
    """A clean valid-JSON classification carries no degraded flag and keeps confidence."""
    from app.services.llm import LLMResponse

    client = _make_client()

    async def ok(system, user):
        return LLMResponse(content='{"category": "retention", "confidence": 0.77}')

    with patch.object(client, "_chat", side_effect=ok):
        result = await client.classify("We retain data for 12 months.", TAXONOMY)

    assert result["category"] == "retention"
    assert result["confidence"] == 0.77
    assert "degraded" not in result or result["degraded"] is False


# ── AI-004: taxonomy-aware prompt ────────────────────────────────────────────

def test_prompt_contains_taxonomy_definitions():
    """The constructed classifier prompt injects real definitions from
    config/clause_taxonomy.json (single source of truth), not bare slugs."""
    prompt = _build_classify_prompt("We use cookies and pixels.", TAXONOMY)

    # A known definition substring from config/clause_taxonomy.json (Cookies row).
    assert "cookies, pixels, beacons, or similar tracking technologies" in prompt
    # A consumer-rights definition substring.
    assert "Right to request deletion of personal information." in prompt
    # Slugs are still present as the constrained allowed values.
    assert "data_sharing" in prompt
    assert "tracking_cookies" in prompt


def test_prompt_is_deterministic_and_versioned():
    """Same inputs → identical prompt (reproducible); version string is set."""
    a = _build_classify_prompt("clause text", TAXONOMY)
    b = _build_classify_prompt("clause text", TAXONOMY)
    assert a == b
    assert CLASSIFY_PROMPT_VERSION  # non-empty version string exists


def test_prompt_preserves_category_order():
    """Category order in the prompt follows the caller's order (deterministic)."""
    cats = ["retention", "data_sharing", "other"]
    prompt = _build_classify_prompt("x", cats)
    i_ret = prompt.index("- retention")
    i_share = prompt.index("- data_sharing")
    i_other = prompt.index("- other")
    assert i_ret < i_share < i_other


@pytest.mark.anyio
async def test_classify_uses_the_taxonomy_prompt():
    """classify() passes the taxonomy-aware prompt (with definitions) to _chat."""
    from app.services.llm import LLMResponse

    client = _make_client()
    captured = {}

    async def capture(system, user):
        captured["user"] = user
        return LLMResponse(content='{"category": "tracking_cookies", "confidence": 0.8}')

    with patch.object(client, "_chat", side_effect=capture):
        await client.classify("We use cookies.", TAXONOMY)

    assert "cookies, pixels, beacons, or similar tracking technologies" in captured["user"]
