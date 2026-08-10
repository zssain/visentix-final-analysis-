"""Cost-regression tests:

  * /health with the runpod_serverless provider must NOT call the model
    (no /runsync, /run, or Ollama /api/version) — it must never wake a
    scale-to-zero worker.
  * SCHEDULER_ENABLED=false must register NO scheduled jobs at startup (so the
    daily monitor_notices cron cannot silently send inference).
"""
import pytest
from pydantic import SecretStr

from app.config import settings
from app.routers import health as health_mod


class _FakeResp:
    headers = {"content-range": "*/123"}

    def json(self):
        return {}


class _FakeClient:
    def __init__(self, capture):
        self._c = capture

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def get(self, url, headers=None):
        self._c.append(url)
        return _FakeResp()


@pytest.mark.anyio
async def test_health_serverless_does_not_wake_worker(monkeypatch):
    monkeypatch.setattr(settings, "llm_backend", "runpod_serverless")
    monkeypatch.setattr(settings, "runpod_endpoint_id", "ep123")
    monkeypatch.setattr(settings, "runpod_api_key", SecretStr("secret"))
    urls: list[str] = []
    monkeypatch.setattr(health_mod.httpx, "AsyncClient", lambda *a, **k: _FakeClient(urls))

    resp = await health_mod.health(cfg=settings)

    # No inference / model-waking call of ANY kind.
    forbidden = ("runsync", "/run", "api.runpod.ai", "/api/version", "/api/chat", ":11434")
    assert not any(any(f in u for f in forbidden) for u in urls), urls
    assert resp["model_backend"] == "runpod_serverless"
    assert resp["model_status"] == "not_probed"
    assert resp["llm"]["probe"] == "not_invoked_to_avoid_cold_start"
    assert resp["status"] == "healthy"  # DB-driven, not gated on a cold endpoint


def test_scheduler_disabled_registers_no_jobs(monkeypatch):
    from app.services import scheduler as sch
    monkeypatch.setattr(settings, "scheduler_enabled", False)
    sch._scheduler = None
    sch.start()
    assert sch._scheduler is None  # start() hard-returns → no GPU-triggering jobs
