"""LLM client abstraction — local (Ollama) and hosted (configurable) backends.

Both backends expose the same interface: classify() and phrase().
Backend selection is env-driven via APP_ENV / HOSTED_QWEN_BASE_URL.

Data handling (AGENTS.md §3):
- Hosted endpoint MUST be zero-retention / no-training.
- Log that text was sent, NEVER the text itself.
- Minimize what is sent — only the clause text needed for the task.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any

import httpx

from app.config import settings
from app.logging import get_logger

log = get_logger(__name__)

# Retry config
MAX_RETRIES = 3
BACKOFF_BASE = 2  # seconds


@dataclass
class LLMResponse:
    """Unified response from either backend."""

    content: str
    parsed: dict | list | None = None
    model: str = ""
    backend: str = ""
    tokens_used: int = 0


class LLMClient:
    """Unified LLM client with local and hosted backends."""

    def __init__(self):
        self._backend = self._select_backend()
        log.info("LLM backend: %s", self._backend)

    def _select_backend(self) -> str:
        """Select backend based on env config.

        The hosted backend is our own Ollama running on the private RunPod pod,
        reached over the tailnet (see deploy/runpod/). It needs NO API key, so
        selection keys off the base URL alone; an API key is sent only if set.
        """
        if settings.hosted_qwen_base_url:
            return "hosted"
        return "local"

    async def classify(self, text: str, categories: list[str]) -> dict:
        """Classify text into one of the given categories.

        Returns {"category": str, "confidence": float} as constrained JSON.
        """
        system = (
            "You are a privacy notice classifier. Respond with ONLY valid JSON. "
            "No explanation, no markdown, no extra text."
        )
        prompt = (
            f"Classify this privacy notice clause into exactly one category.\n"
            f"Categories: {json.dumps(categories)}\n\n"
            f"Clause: {text[:1000]}\n\n"
            f'Respond with JSON: {{"category": "...", "confidence": 0.0-1.0}}'
        )

        log.info("LLM classify: sending %d chars (text not logged)", len(text))
        try:
            response = await self._chat(system, prompt)
        except Exception:
            log.warning("LLM classify: chat failed, returning 'other'")
            return {"category": "other", "confidence": 0.5}

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
            if "category" in parsed:
                return parsed
        except (ValueError, json.JSONDecodeError):
            pass

        log.warning("LLM classify: failed to parse JSON, falling back to 'other'")
        return {"category": "other", "confidence": 0.5}

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
        """Send a chat message to the selected backend with retries."""
        for attempt in range(MAX_RETRIES):
            try:
                if self._backend == "hosted":
                    return await self._chat_hosted(system, user)
                else:
                    return await self._chat_local(system, user)
            except (httpx.ReadTimeout, httpx.ConnectTimeout, httpx.RemoteProtocolError) as e:
                wait = BACKOFF_BASE ** attempt
                log.warning(
                    "LLM %s attempt %d/%d failed (%s), retrying in %ds",
                    self._backend, attempt + 1, MAX_RETRIES, type(e).__name__, wait,
                )
                if attempt < MAX_RETRIES - 1:
                    import asyncio
                    await asyncio.sleep(wait)
                else:
                    raise

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

    async def _chat_hosted(self, system: str, user: str) -> LLMResponse:
        """Call the hosted Ollama endpoint (private RunPod pod over the tailnet).

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
                backend="hosted",
            )


# Singleton
_client: LLMClient | None = None


def get_llm_client() -> LLMClient:
    global _client
    if _client is None:
        _client = LLMClient()
    return _client
