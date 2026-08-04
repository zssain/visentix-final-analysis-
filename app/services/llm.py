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
                if self._backend == "hosted":
                    return await self._chat_hosted(system, user)
                else:
                    return await self._chat_local(system, user)
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
