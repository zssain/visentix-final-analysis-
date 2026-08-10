"""RunPod Serverless LLM adapter — unit tests (no network, no GPU).

Covers the acceptance matrix: success, 401 (no retry), 429/5xx (bounded retry),
timeout (retry), RunPod job FAILED, COMPLETED-but-missing-output, IN_PROGRESS →
/status poll → COMPLETED, and API-key non-leakage. External HTTP is faked.
"""
import httpx
import pytest
from pydantic import SecretStr

from app.config import settings
from app.services import llm as llm_mod
from app.services.llm import LLMClient, RunPodServerlessError

_URL = "https://api.runpod.ai/v2/ep123/runsync"


class FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {}
        self.request = httpx.Request("POST", _URL)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"HTTP {self.status_code}", request=self.request,
                response=httpx.Response(self.status_code, request=self.request),
            )

    def json(self):
        return self._payload


class FakeClient:
    """Async client stub. `responses` is consumed in order across post()+get();
    an Exception item is raised (to simulate a transport error)."""

    def __init__(self, responses, capture):
        # SHARED list (not a copy): retries create a new client each attempt, but
        # they must keep draining the SAME response sequence.
        self._responses = responses
        self._capture = capture

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    def _next(self):
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    async def post(self, url, headers=None, json=None):
        self._capture.setdefault("posts", []).append({"url": url, "headers": headers, "json": json})
        return self._next()

    async def get(self, url, headers=None):
        self._capture.setdefault("gets", []).append({"url": url, "headers": headers})
        return self._next()


@pytest.fixture
def rp(monkeypatch):
    """A serverless-configured LLMClient + a mutable capture dict. Use
    `install(responses)` to arm the fake HTTP client."""
    monkeypatch.setattr(settings, "llm_backend", "runpod_serverless")
    monkeypatch.setattr(settings, "runpod_endpoint_id", "ep123")
    monkeypatch.setattr(settings, "runpod_api_key", SecretStr("TEST-SECRET-KEY"))
    monkeypatch.setattr(settings, "runpod_serverless_base_url", "https://api.runpod.ai/v2")
    monkeypatch.setattr(settings, "hosted_qwen_model", "qwen3:8b")
    # never actually sleep during retries/polling
    async def _no_sleep(*_a, **_k):
        return None
    monkeypatch.setattr(llm_mod.asyncio, "sleep", _no_sleep)
    llm_mod._client = None
    capture: dict = {}

    def install(responses):
        monkeypatch.setattr(llm_mod.httpx, "AsyncClient", lambda *a, **k: FakeClient(responses, capture))

    client = LLMClient()
    assert client._backend == "runpod_serverless"
    return client, install, capture


def _completed(content="hello"):
    return FakeResponse(200, {
        "id": "job-1", "status": "COMPLETED", "delayTime": 120, "executionTime": 2000,
        "output": {"model": "qwen3:8b", "message": {"role": "assistant", "content": content}, "done": True},
    })


@pytest.mark.anyio
async def test_success_and_payload_shape(rp):
    client, install, capture = rp
    install([_completed("hi there")])
    r = await client._chat_runpod_serverless("SYS", "USER")
    assert r.content == "hi there"
    assert r.backend == "runpod_serverless"
    post = capture["posts"][0]
    assert post["url"].endswith("/ep123/runsync")
    assert post["headers"]["Authorization"] == "Bearer TEST-SECRET-KEY"
    inp = post["json"]["input"]
    assert inp["operation"] == "chat" and inp["model"] == "qwen3:8b"
    assert inp["stream"] is False and inp["think"] is False
    assert inp["options"] == {"num_predict": 500}
    assert inp["messages"][0]["role"] == "system" and inp["messages"][1]["role"] == "user"


@pytest.mark.anyio
async def test_401_is_not_retried(rp):
    client, install, capture = rp
    install([FakeResponse(401)])
    out = await client.classify("some clause", ["data_sharing", "other"])
    assert out.get("degraded") is True          # honest fallback
    assert len(capture["posts"]) == 1           # fail-fast, single attempt


@pytest.mark.anyio
async def test_429_is_retried_then_succeeds(rp):
    client, install, capture = rp
    install([FakeResponse(429), FakeResponse(429), _completed('{"category":"other","confidence":0.1}')])
    out = await client.classify("clause", ["data_sharing", "other"])
    assert out.get("degraded") is not True       # eventually succeeded
    assert len(capture["posts"]) == 3


@pytest.mark.anyio
async def test_5xx_retries_bounded_then_degrades(rp):
    client, install, capture = rp
    install([FakeResponse(503), FakeResponse(503), FakeResponse(503)])
    out = await client.classify("clause", ["data_sharing", "other"])
    assert out.get("degraded") is True
    assert len(capture["posts"]) == 3            # MAX_RETRIES, not unbounded


@pytest.mark.anyio
async def test_timeout_is_retried(rp):
    client, install, capture = rp
    install([httpx.ReadTimeout("slow"), _completed('{"category":"other","confidence":0.2}')])
    out = await client.classify("clause", ["data_sharing", "other"])
    assert out.get("degraded") is not True       # retried past the timeout, succeeded
    assert len(capture["posts"]) == 2            # 1 timed-out attempt + 1 success


@pytest.mark.anyio
async def test_job_failed_raises_terminal(rp):
    client, install, capture = rp
    install([FakeResponse(200, {"id": "j", "status": "FAILED", "error": "worker crashed"})])
    with pytest.raises(RunPodServerlessError):
        await client._chat_runpod_serverless("s", "u")
    # and via classify() → degraded, not retried
    install([FakeResponse(200, {"id": "j", "status": "FAILED", "error": "x"})])
    out = await client.classify("clause", ["data_sharing", "other"])
    assert out.get("degraded") is True


@pytest.mark.anyio
async def test_completed_missing_output_raises(rp):
    client, install, _ = rp
    install([FakeResponse(200, {"id": "j", "status": "COMPLETED"})])
    with pytest.raises(RunPodServerlessError):
        await client._chat_runpod_serverless("s", "u")


@pytest.mark.anyio
async def test_in_progress_polls_status_to_completed(rp):
    client, install, capture = rp
    install([
        FakeResponse(200, {"id": "j5", "status": "IN_PROGRESS"}),   # runsync returns early
        FakeResponse(200, {"id": "j5", "status": "IN_PROGRESS"}),   # /status poll 1
        _completed("done-after-poll"),                              # /status poll 2
    ])
    r = await client._chat_runpod_serverless("s", "u")
    assert r.content == "done-after-poll"
    assert len(capture["posts"]) == 1 and len(capture["gets"]) == 2
    assert "/ep123/status/j5" in capture["gets"][0]["url"]


@pytest.mark.anyio
async def test_api_key_never_leaks_in_logs_or_errors(rp, caplog):
    client, install, _ = rp
    install([FakeResponse(200, {"id": "j", "status": "FAILED", "error": "boom"})])
    with caplog.at_level("DEBUG"):
        try:
            await client._chat_runpod_serverless("s", "u")
        except RunPodServerlessError as e:
            assert "TEST-SECRET-KEY" not in str(e)
    assert "TEST-SECRET-KEY" not in caplog.text
