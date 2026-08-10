#!/usr/bin/env python3
"""Visentix RunPod Serverless worker — Ollama + qwen3:8b (scale-to-zero).

This is the GPU leaf for the SERVERLESS architecture. A worker exists ONLY while
RunPod is processing a job; between jobs RunPod scales it to zero (no idle bill).

Design rules (see deploy/runpod/README.md):
  * NO forever-supervisor / `while true` loop. RunPod owns the worker lifecycle;
    nothing here must prevent scale-to-zero. `OLLAMA_KEEP_ALIVE=-1` is NOT used.
  * Ollama is started ONCE per worker cold start and reused for every job that
    worker serves while it stays warm. The model is loaded on first inference and
    kept in VRAM by Ollama's default keep-alive (minutes) — long enough for one
    assessment's sequential calls (classify×N + narrative), short enough that the
    worker still drains and RunPod terminates it after the idle timeout.
  * Ollama binds 127.0.0.1 only (never public). RunPod fronts the auth + queue.
  * The job contract mirrors Ollama's native /api/chat so model behaviour is
    identical to the local/hosted backends (output parity). Input:
        {"input": {"operation":"chat","model":"qwen3:8b",
                   "messages":[...],"stream":false,"think":false,"options":{...}}}
    Output (== what app/services/llm.py::_runpod_parse expects):
        {"model":"qwen3:8b","message":{"role":"assistant","content":"..."},
         "done":true,"eval_count":N,"prompt_eval_count":N}

`handler(job)` is import-safe (no side effects) so it can be unit-tested without
Ollama or the runpod SDK. Ollama startup + `runpod.serverless.start` run only
under `__main__`.
"""
from __future__ import annotations

import logging
import os
import subprocess
import threading
import time

import httpx

log = logging.getLogger("visentix.serverless")
logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))

# Internal only — never published. RunPod receives external requests, not Ollama.
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
MODEL = os.environ.get("OLLAMA_MODEL", "qwen3:8b")
# Cold-start budget: model may need to load/download on the FIRST worker start.
STARTUP_TIMEOUT_S = float(os.environ.get("OLLAMA_STARTUP_TIMEOUT_S", "300"))
# Per-request budget inside the worker (Ollama generation).
REQUEST_TIMEOUT_S = float(os.environ.get("OLLAMA_REQUEST_TIMEOUT_S", "280"))

_ollama_proc: subprocess.Popen | None = None


# ── Worker startup (runs once per cold start; NOT a supervisor) ──────────────

def _ollama_ready() -> bool:
    try:
        return httpx.get(f"{OLLAMA_URL}/api/version", timeout=3).status_code == 200
    except Exception:
        return False


def _start_ollama() -> None:
    """Start `ollama serve` bound to localhost if it isn't already up. Started
    ONCE per worker; the process lives for the worker's lifetime and dies with it
    when RunPod terminates the worker (no restart loop → scale-to-zero honoured)."""
    global _ollama_proc
    if _ollama_ready():
        return
    env = {**os.environ, "OLLAMA_HOST": "127.0.0.1"}
    # Do NOT set OLLAMA_KEEP_ALIVE=-1 — that is the always-on Pod anti-pattern.
    log.info("[startup] starting ollama serve (bound 127.0.0.1)")
    _ollama_proc = subprocess.Popen(["ollama", "serve"], env=env)
    deadline = time.time() + STARTUP_TIMEOUT_S
    while time.time() < deadline:
        if _ollama_ready():
            log.info("[startup] ollama ready")
            return
        if _ollama_proc.poll() is not None:
            raise RuntimeError("ollama serve exited during startup")
        time.sleep(1.0)
    raise RuntimeError(f"ollama did not become ready within {STARTUP_TIMEOUT_S}s")


def _ensure_model() -> None:
    """Ensure the model is present. With a network volume mounted at OLLAMA_MODELS
    this is a no-op after the first ever pull (the weights persist on the volume);
    without one it pulls into the container disk (worse cold starts). See README
    'Model storage'."""
    try:
        tags = httpx.get(f"{OLLAMA_URL}/api/tags", timeout=10).json().get("models", [])
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(f"could not list ollama models: {type(e).__name__}") from e
    names = {m.get("name", "") for m in tags}
    if MODEL in names or any(n.split(":")[0] == MODEL.split(":")[0] for n in names):
        log.info("[startup] model %s already present", MODEL)
        return
    log.info("[startup] pulling model %s (first start on this storage)", MODEL)
    rc = subprocess.run(["ollama", "pull", MODEL]).returncode
    if rc != 0:
        raise RuntimeError(f"ollama pull {MODEL} failed rc={rc}")


_model_ready = False
_model_lock = threading.Lock()


def _ensure_model_once() -> None:
    """Pull the model on the FIRST job only (lazy). Done here — not before
    runpod.serverless.start() — so the worker registers/serves promptly and RunPod
    doesn't mark it unhealthy while a multi-GB pull is still running. Thread-safe."""
    global _model_ready
    if _model_ready:
        return
    with _model_lock:
        if _model_ready:
            return
        _ensure_model()
        _model_ready = True


# ── Job handler (import-safe; unit-tested directly) ─────────────────────────

def handler(job: dict) -> dict:
    """Process one RunPod job. Raises on any failure so RunPod marks the job
    FAILED (the Azure backend then records an honest DEGRADED result — it does NOT
    silently succeed). Never logs prompt text."""
    _ensure_model_once()  # first job pulls the model (worker already registered)
    inp = (job or {}).get("input") or {}
    operation = inp.get("operation", "chat")
    if operation != "chat":
        raise ValueError(f"unsupported operation: {operation!r} (only 'chat')")

    messages = inp.get("messages")
    if not isinstance(messages, list) or not messages:
        raise ValueError("input.messages must be a non-empty list")

    body = {
        "model": inp.get("model") or MODEL,
        "messages": messages,
        "stream": False,                      # workers return one JSON, never a stream
        "think": bool(inp.get("think", False)),
        "options": inp.get("options") or {},
    }
    t0 = time.time()
    try:
        r = httpx.post(f"{OLLAMA_URL}/api/chat", json=body, timeout=REQUEST_TIMEOUT_S)
        r.raise_for_status()
        data = r.json()
    except Exception as e:  # noqa: BLE001 — surface as a FAILED job, no prompt text
        raise RuntimeError(f"ollama /api/chat failed: {type(e).__name__}") from e

    msg = data.get("message") or {}
    if not msg.get("content"):
        raise RuntimeError("ollama returned empty message content")

    log.info(
        "[handler] chat ok model=%s duration_ms=%d eval_count=%s",
        body["model"], int((time.time() - t0) * 1000), data.get("eval_count"),
    )
    return {
        "model": data.get("model", body["model"]),
        "message": {"role": msg.get("role", "assistant"), "content": msg["content"]},
        "done": data.get("done", True),
        "eval_count": data.get("eval_count"),
        "prompt_eval_count": data.get("prompt_eval_count"),
    }


if __name__ == "__main__":
    # Real worker entrypoint (NOT run during unit tests).
    # Start Ollama (fast — seconds) and register with RunPod PROMPTLY so the worker
    # is healthy immediately. The multi-GB model pull happens lazily on the first
    # job (see _ensure_model_once) rather than blocking startup.
    _start_ollama()
    import runpod  # imported here so tests don't require the SDK

    log.info("[worker] ollama up — starting runpod.serverless (model pulls on first job)")
    runpod.serverless.start({"handler": handler})
