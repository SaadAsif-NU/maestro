"""Real model brain backed by an OpenAI-compatible chat API.

Works with OpenAI, Google Gemini (via its OpenAI-compatible endpoint), or any
compatible server (vLLM, Together, Groq, a local model). Streams tokens as they
arrive so the live view stays real-time.

Free tiers are rate limited, and an orchestration fans out several calls at once,
so the client is defensive: it caps how many requests run concurrently and
retries rate-limit (429) and transient server errors with exponential backoff,
honouring a Retry-After header when the provider sends one.
"""

from __future__ import annotations

import asyncio
import json
import os
import random
from collections.abc import AsyncIterator

import httpx

from .base import Brain

_RETRY_STATUS = {429, 500, 502, 503, 504}
_MAX_BACKOFF = 20.0


def _retry_after(headers: httpx.Headers) -> float | None:
    value = headers.get("retry-after")
    if not value:
        return None
    try:
        return min(float(value), _MAX_BACKOFF)
    except ValueError:
        return None


class OpenAIBrain(Brain):
    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str = "gpt-4o-mini",
        base_url: str = "https://api.openai.com/v1",
        temperature: float = 0.4,
        name: str | None = None,
        max_retries: int = 4,
        backoff_base: float = 0.6,
        max_concurrency: int = 3,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._temperature = temperature
        # Shown in the UI badge, e.g. "gemini-2.0-flash".
        self.name = name or model
        self._max_retries = max_retries
        self._backoff_base = backoff_base
        # Bound concurrent upstream calls so parallel agents do not burst past a
        # free-tier per-minute limit all at once.
        self._sem = asyncio.Semaphore(max(1, max_concurrency))
        self._client = client or httpx.AsyncClient(timeout=60.0)

    def _backoff(self, attempt: int) -> float:
        return min(_MAX_BACKOFF, self._backoff_base * (2**attempt)) + random.uniform(0.0, 0.3)

    async def stream(
        self, prompt: str, *, system: str | None = None, role: str | None = None
    ) -> AsyncIterator[str]:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        payload = {
            "model": self._model,
            "messages": messages,
            "temperature": self._temperature,
            "stream": True,
        }
        headers = {"Authorization": f"Bearer {self._api_key}"}
        url = f"{self._base_url}/chat/completions"

        async with self._sem:
            for attempt in range(self._max_retries + 1):
                try:
                    async with self._client.stream(
                        "POST", url, json=payload, headers=headers
                    ) as resp:
                        if resp.status_code in _RETRY_STATUS and attempt < self._max_retries:
                            await resp.aread()
                            await asyncio.sleep(
                                _retry_after(resp.headers) or self._backoff(attempt)
                            )
                            continue
                        resp.raise_for_status()
                        async for line in resp.aiter_lines():
                            delta = _parse_sse_delta(line)
                            if delta:
                                yield delta
                        return
                except httpx.TransportError:
                    if attempt < self._max_retries:
                        await asyncio.sleep(self._backoff(attempt))
                        continue
                    raise

    async def aclose(self) -> None:
        await self._client.aclose()


def _parse_sse_delta(line: str) -> str | None:
    if not line.startswith("data:"):
        return None
    data = line[len("data:") :].strip()
    if not data or data == "[DONE]":
        return None
    try:
        choices = json.loads(data).get("choices", [])
    except json.JSONDecodeError:
        return None
    if not choices:
        return None
    return choices[0].get("delta", {}).get("content")
