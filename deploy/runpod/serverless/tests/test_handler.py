"""Local unit tests for the RunPod Serverless worker handler.

Run WITHOUT a GPU, Ollama, or the runpod SDK:
    pytest deploy/runpod/serverless/tests -q

The handler module is import-safe (Ollama startup + runpod.serverless.start run
only under __main__), so we import it directly and mock the local Ollama HTTP call.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import handler as H  # noqa: E402


@pytest.fixture(autouse=True)
def _model_already_ready(monkeypatch):
    # The handler waits on a background model-pull Event; pre-set it in tests
    # (no Ollama running) so we exercise only the chat path.
    import threading
    ev = threading.Event()
    ev.set()
    monkeypatch.setattr(H, "_model_ready", ev)


class _Resp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def _ok_ollama(*_a, **_k):
    return _Resp({
        "model": "qwen3:8b",
        "message": {"role": "assistant", "content": '{"category":"data_sharing","confidence":0.9}'},
        "done": True,
        "eval_count": 42,
        "prompt_eval_count": 100,
    })


def test_handler_chat_success(monkeypatch):
    monkeypatch.setattr(H.httpx, "post", _ok_ollama)
    out = H.handler({"input": {
        "operation": "chat", "model": "qwen3:8b",
        "messages": [{"role": "user", "content": "classify this"}],
        "stream": False, "think": False, "options": {"num_predict": 500},
    }})
    assert out["message"]["content"] == '{"category":"data_sharing","confidence":0.9}'
    assert out["model"] == "qwen3:8b"
    assert out["done"] is True
    assert out["eval_count"] == 42


def test_handler_rejects_missing_messages():
    with pytest.raises(ValueError):
        H.handler({"input": {"operation": "chat"}})


def test_handler_rejects_unknown_operation():
    with pytest.raises(ValueError):
        H.handler({"input": {"operation": "embeddings", "messages": [{"role": "user", "content": "x"}]}})


def test_handler_raises_on_empty_content(monkeypatch):
    monkeypatch.setattr(H.httpx, "post",
                        lambda *a, **k: _Resp({"message": {"role": "assistant", "content": ""}}))
    with pytest.raises(RuntimeError):
        H.handler({"input": {"messages": [{"role": "user", "content": "x"}]}})


def test_handler_raises_on_ollama_error(monkeypatch):
    def _boom(*_a, **_k):
        raise RuntimeError("connection refused")
    monkeypatch.setattr(H.httpx, "post", _boom)
    with pytest.raises(RuntimeError):
        H.handler({"input": {"messages": [{"role": "user", "content": "x"}]}})
