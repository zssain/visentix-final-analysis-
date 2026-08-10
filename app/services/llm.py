"""LLM client abstraction — local (Ollama) and hosted (configurable) backends.

Both backends expose the same interface: classify() and phrase().
Backend selection is env-driven via APP_ENV / HOSTED_QWEN_BASE_URL.

Data handling (AGENTS.md §3):
- Hosted endpoint MUST be zero-retention / no-training.
- Log that text was sent, NEVER the text itself.
- Minimize what is sent — only the clause text needed for the task.
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import httpx

from app.config import settings
from app.logging import get_logger

log = get_logger(__name__)

# Retry config
MAX_RETRIES = 3
BACKOFF_BASE = 2  # seconds

# Classifier prompt version — bump when the prompt template or the taxonomy
# injection changes so lineage stays reproducible. (Accuracy is measured
# separately by F17 / EVAL-001; this string only tracks the prompt shape.)
CLASSIFY_PROMPT_VERSION = "classify-taxonomy-v2"

# Path to the single source of truth for the clause taxonomy (definitions,
# keywords, legacy slugs). We load definitions FROM here rather than hardcoding a
# divergent taxonomy in this module.
_TAXONOMY_PATH = Path(__file__).resolve().parents[2] / "config" / "clause_taxonomy.json"


@lru_cache(maxsize=1)
def _load_taxonomy() -> list[dict]:
    """Load config/clause_taxonomy.json once (cached).

    Returns the raw list of taxonomy rows. Returns [] if the file is missing or
    unparseable — the classifier still works with bare slugs in that case (it
    just loses the injected definitions), so a bad config never breaks intake.
    """
    try:
        with _TAXONOMY_PATH.open(encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError) as e:
        log.warning("clause_taxonomy load failed (%s); prompt will use bare slugs", type(e).__name__)
        return []


def _definitions_for(categories: list[str]) -> dict[str, str]:
    """Map each requested category to a concise one-line definition.

    Callers pass legacy slugs (e.g. "data_sharing"). The taxonomy config keys
    definitions per fine-grained clause_type and tags each with a `legacy_slug`,
    so several definitions can share one slug. We aggregate the distinct
    definitions for a slug into a single concise line (deterministic order:
    taxonomy file order, de-duplicated). A category with no match (e.g. "other")
    is simply omitted — the prompt falls back to the bare slug for it.
    """
    rows = _load_taxonomy()
    out: dict[str, list[str]] = {}
    for cat in categories:  # deterministic: preserves the caller's category order
        defs: list[str] = []
        for row in rows:  # taxonomy-file order → stable
            if row.get("legacy_slug") != cat:
                continue
            d = (row.get("definition") or "").strip()
            if d and d not in defs:
                defs.append(d)
        if defs:
            out[cat] = " / ".join(defs)
    return {c: out[c] for c in categories if c in out}


def _degraded_result() -> dict:
    """Honest fallback result for a failed classification.

    Zeroed confidence + `degraded=True` so the caller can record in lineage that
    the label is a keyword/`other` fallback rather than a full AI classification.
    """
    return {"category": "other", "confidence": 0.0, "degraded": True}


def _build_classify_prompt(text: str, categories: list[str]) -> str:
    """Construct the taxonomy-aware classifier prompt.

    Injects concise one-line definitions (loaded from config/clause_taxonomy.json)
    for each category so the model knows what each slug means, then asks for
    constrained JSON. Kept deterministic (category order preserved, definitions in
    taxonomy-file order) so the prompt is reproducible for a given version.
    """
    definitions = _definitions_for(categories)
    def_lines = "\n".join(
        f"- {cat}: {definitions[cat]}" if cat in definitions else f"- {cat}"
        for cat in categories
    )
    return (
        f"Classify this privacy notice clause into exactly one category.\n"
        f"Choose the single best-fitting category from the definitions below.\n\n"
        f"Categories (with definitions):\n{def_lines}\n\n"
        f"Allowed values (respond with exactly one of these): {json.dumps(categories)}\n\n"
        f"Clause: {text[:1000]}\n\n"
        f'Respond with JSON: {{"category": "...", "confidence": 0.0-1.0}}'
    )


@dataclass
class LLMResponse:
    """Unified response from either backend."""

    content: str
    parsed: dict | list | None = None
    model: str = ""
    backend: str = ""
    tokens_used: int = 0


class RunPodServerlessError(RuntimeError):
    """A terminal, NON-retryable RunPod Serverless failure (job FAILED/CANCELLED,
    missing/malformed worker output, or missing config). Distinct from httpx
    transport/status errors so the ONE retry policy in `_chat` doesn't retry it —
    it propagates and the caller records an honest DEGRADED result. Never carries a
    secret in its message."""


class LLMClient:
    """Unified LLM client. Providers: local Ollama, legacy hosted Ollama (Pod),
    and RunPod Serverless (scale-to-zero). classify()/phrase() are provider-agnostic."""

    def __init__(self):
        # Fail fast on misconfiguration — NO network call (never wakes a worker).
        settings.validate_llm_backend()
        self._backend = self._select_backend()
        log.info("LLM backend: %s", self._backend)

    def _select_backend(self) -> str:
        """Provider is resolved centrally in config (LLM_BACKEND, else auto):
        'local' | 'hosted_ollama' | 'runpod_serverless'."""
        return settings.effective_llm_backend

    async def classify(self, text: str, categories: list[str]) -> dict:
        """Classify text into one of the given categories.

        Returns {"category": str, "confidence": float} as constrained JSON on a
        successful AI classification.

        On any failure (transient error after retries, or unparseable output) it
        returns an HONEST DEGRADED result: {"category": "other", "confidence": 0.0,
        "degraded": True}. The `degraded` flag + zeroed confidence let the caller
        record in lineage that this label came from a fallback, NOT from a full AI
        classification — we do not pretend AI succeeded. Successful results never
        carry `degraded` (callers can treat its absence/False as "AI-classified").
        """
        system = (
            "You are a privacy notice classifier. Respond with ONLY valid JSON. "
            "No explanation, no markdown, no extra text."
        )
        # Taxonomy-aware prompt: injects one-line definitions loaded from
        # config/clause_taxonomy.json (single source of truth). See
        # CLASSIFY_PROMPT_VERSION. (Any accuracy effect is measured by F17.)
        prompt = _build_classify_prompt(text, categories)

        log.info(
            "LLM classify: sending %d chars (text not logged), prompt=%s",
            len(text), CLASSIFY_PROMPT_VERSION,
        )
        try:
            response = await self._chat(system, prompt)
        except Exception:
            log.warning("LLM classify: chat failed, returning DEGRADED 'other'")
            return _degraded_result()

        # Parse constrained JSON
        try:
            parsed = json.loads(response.content.strip())
            if "category" in parsed and parsed["category"] in categories:
                return parsed
        except (json.JSONDecodeError, KeyError):
            pass

        # Fallback: try to extract JSON from response
        try:
            start = response.content.index("{")
            end = response.content.rindex("}") + 1
            parsed = json.loads(response.content[start:end])
            if "category" in parsed and parsed["category"] in categories:
                return parsed
        except (ValueError, json.JSONDecodeError):
            pass

        log.warning("LLM classify: failed to parse JSON, DEGRADED fallback to 'other'")
        return _degraded_result()

    async def phrase(self, template: str, context: dict) -> str:
        """Smooth a pre-computed finding/recommendation into professional language.

        The LLM only phrases — it never invents claims, numbers, or recommendations.
        """
        system = (
            "You are a professional privacy intelligence writer. "
            "Rephrase the given template using the provided context. "
            "Do NOT invent any claims, numbers, or recommendations. "
            "Use exposure/likelihood language only. "
            "Never use: violation, violates, illegal, unlawful, non-compliant, "
            "breach of law, guilty, liable."
        )
        prompt = (
            f"Template: {template}\n\n"
            f"Context: {json.dumps(context)}\n\n"
            f"Rephrased (professional, 2-3 sentences):"
        )

        log.info("LLM phrase: sending template (%d chars, text not logged)", len(template))
        response = await self._chat(system, prompt)
        return response.content.strip()

    async def _chat(self, system: str, user: str) -> LLMResponse:
        """Send a chat message to the selected backend with bounded-backoff retries.

        Retries only TRANSIENT failures:
          * network-level: ReadTimeout, ConnectTimeout, RemoteProtocolError
          * HTTP status:   429 (rate limit) and 5xx (e.g. a 502/503 from a GPU
            cold start) — these are expected to clear on a retry.

        A non-429 4xx (400/401/403/404/…) is PERMANENT — a bad request/auth issue
        won't fix itself, so we do NOT retry it; it propagates immediately and the
        caller records an honest DEGRADED fallback instead of burning the backoff.
        """
        for attempt in range(MAX_RETRIES):
            try:
                if self._backend == "local":
                    return await self._chat_local(system, user)
                elif self._backend == "runpod_serverless":
                    return await self._chat_runpod_serverless(system, user)
                else:  # hosted_ollama — legacy always-on Pod
                    return await self._chat_hosted_ollama(system, user)
            except httpx.HTTPStatusError as e:
                status = e.response.status_code
                if not (status == 429 or 500 <= status < 600):
                    # Permanent 4xx (bad request / auth / not found) — fail fast.
                    log.warning(
                        "LLM %s got permanent HTTP %d, not retrying",
                        self._backend, status,
                    )
                    raise
                last_exc, detail = e, f"HTTP {status}"
            except (httpx.ReadTimeout, httpx.ConnectTimeout, httpx.RemoteProtocolError) as e:
                last_exc, detail = e, type(e).__name__

            # Transient failure (retryable HTTP status or network error): bounded backoff.
            if attempt >= MAX_RETRIES - 1:
                raise last_exc  # retries exhausted → propagate the last exception
            wait = BACKOFF_BASE ** attempt
            log.warning(
                "LLM %s attempt %d/%d failed (%s), retrying in %ds",
                self._backend, attempt + 1, MAX_RETRIES, detail, wait,
            )
            await asyncio.sleep(wait)

        raise RuntimeError("LLM retries exhausted")

    async def _chat_local(self, system: str, user: str) -> LLMResponse:
        """Call local Ollama endpoint."""
        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post(
                f"{settings.ollama_base_url}/api/chat",
                json={
                    "model": settings.qwen_local_model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "stream": False,
                    "think": False,
                    "options": {"num_predict": 500},
                },
            )
            r.raise_for_status()
            data = r.json()
            content = data.get("message", {}).get("content", "")
            return LLMResponse(
                content=content,
                model=settings.qwen_local_model,
                backend="local",
            )

    async def _chat_hosted_ollama(self, system: str, user: str) -> LLMResponse:
        """Call the LEGACY hosted Ollama endpoint (always-on RunPod Pod over the tailnet).

        Retained for back-compat + rollback. Production uses runpod_serverless.

        This is the SAME Ollama server as local, just remote — so the request
        MUST be byte-for-byte identical to _chat_local (native /api/chat,
        stream=False, think=False, num_predict=500). The only differences are
        the base URL, an optional bearer token (sent only if configured), and
        the backend label. Keeping the payload identical guarantees the model
        sees the same prompt/params regardless of where it runs; classifier
        outputs and versions stay stable across backends.
        """
        headers = {"Content-Type": "application/json"}
        if settings.hosted_qwen_api_key:
            headers["Authorization"] = f"Bearer {settings.hosted_qwen_api_key}"
        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post(
                f"{settings.hosted_qwen_base_url}/api/chat",
                headers=headers,
                json={
                    "model": settings.hosted_qwen_model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "stream": False,
                    "think": False,
                    "options": {"num_predict": 500},
                },
            )
            r.raise_for_status()
            data = r.json()
            content = data.get("message", {}).get("content", "")
            return LLMResponse(
                content=content,
                model=settings.hosted_qwen_model,
                backend="hosted_ollama",
            )

    # ── RunPod Serverless (scale-to-zero) ────────────────────────────────────
    async def _chat_runpod_serverless(self, system: str, user: str) -> LLMResponse:
        """Call the qwen3:8b model on a RunPod Serverless endpoint.

        The GPU worker exists ONLY while a job is being processed; between jobs
        RunPod scales it to zero (no idle billing). This method:
          1. Builds the SAME native Ollama /api/chat payload as the local/hosted
             backends (stream=False, think=False, num_predict=500) so generation
             behaviour is backend-independent (output parity).
          2. Wraps it in RunPod's job envelope `{"input": {...}}`.
          3. POSTs to `{base}/{endpoint_id}/runsync` with a Bearer API key.
          4. If runsync returns before the job is COMPLETED (cold start > runsync
             wait window), polls `/status/{id}` until terminal or timeout.
          5. Validates the RunPod envelope + the worker's Ollama-shaped output.

        Transient failures (429, 5xx, network timeout) raise httpx errors that the
        ONE retry policy in `_chat` handles. Terminal failures (job FAILED, missing
        output) raise RunPodServerlessError (NOT retried → caller degrades). No
        secret (API key) or prompt text is ever logged.
        """
        endpoint = settings.runpod_endpoint_id
        api_key = settings.runpod_api_key.get_secret_value()
        if not endpoint or not api_key:
            # validate_llm_backend() covers startup; guard here for direct callers.
            raise RunPodServerlessError("RunPod Serverless not configured (endpoint id / api key)")

        base = settings.runpod_serverless_base_url.rstrip("/")
        model = settings.llm_model_name
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        payload = {
            "input": {
                "operation": "chat",
                "model": model,
                # IDENTICAL inference params to _chat_local / _chat_hosted_ollama.
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "stream": False,
                "think": False,
                "options": {"num_predict": 500},
            }
        }

        overall = settings.runpod_serverless_timeout_seconds
        timeout = httpx.Timeout(overall, connect=15.0)
        t0 = time.monotonic()
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.post(f"{base}/{endpoint}/runsync", headers=headers, json=payload)
            r.raise_for_status()  # 401/403/404 → permanent; 429/5xx → retried by _chat
            env = r.json()
            env = await self._runpod_await_terminal(client, base, endpoint, headers, env, t0, overall)

        return self._runpod_parse(env, model, t0)

    async def _runpod_await_terminal(
        self, client: httpx.AsyncClient, base: str, endpoint: str, headers: dict,
        env: dict, t0: float, overall: float,
    ) -> dict:
        """If runsync returned a non-terminal status (cold start exceeded its wait
        window), poll GET /status/{id} until the job reaches a terminal state or
        the overall budget is exhausted. Polling is backend-only — the browser is
        polling the assessment status separately, never RunPod."""
        NON_TERMINAL = {"IN_QUEUE", "IN_PROGRESS"}
        status = (env or {}).get("status")
        job_id = (env or {}).get("id")
        while status in NON_TERMINAL and job_id:
            if time.monotonic() - t0 >= overall:
                raise httpx.ReadTimeout(f"RunPod job {job_id} exceeded {overall}s budget (status={status})")
            await asyncio.sleep(2.0)
            r = await client.get(f"{base}/{endpoint}/status/{job_id}", headers=headers)
            r.raise_for_status()
            env = r.json()
            status = env.get("status")
        return env

    def _runpod_parse(self, env: dict, model: str, t0: float) -> LLMResponse:
        """Validate the RunPod envelope + extract the Ollama-shaped worker output."""
        status = (env or {}).get("status")
        job_id = (env or {}).get("id")
        dur_ms = int((time.monotonic() - t0) * 1000)
        if status != "COMPLETED":
            err = env.get("error") if isinstance(env, dict) else None
            # Log safe metadata only (no prompt text, no api key).
            log.warning(
                "runpod_serverless job non-COMPLETED provider=runpod_serverless status=%s "
                "job_id=%s duration_ms=%d", status, job_id, dur_ms,
            )
            raise RunPodServerlessError(
                f"RunPod job {job_id} status={status}"
                + (f": {str(err)[:200]}" if err else "")
            )
        output = env.get("output")
        if not isinstance(output, dict):
            raise RunPodServerlessError(f"RunPod job {job_id} COMPLETED but output missing/invalid")
        content = (output.get("message") or {}).get("content", "")
        log.info(
            "runpod_serverless ok provider=runpod_serverless operation=chat model=%s "
            "job_id=%s status=COMPLETED delay_ms=%s exec_ms=%s duration_ms=%d",
            model, job_id, env.get("delayTime"), env.get("executionTime"), dur_ms,
        )
        return LLMResponse(
            content=content,
            model=output.get("model", model),
            backend="runpod_serverless",
        )


# Singleton
_client: LLMClient | None = None


def get_llm_client() -> LLMClient:
    global _client
    if _client is None:
        _client = LLMClient()
    return _client
