"""Real model brain backed by an OpenAI-compatible chat API.

Works with OpenAI, Google Gemini (via its OpenAI-compatible endpoint), or any
compatible server (vLLM, Together, Groq, a local model). Streams tokens as they
arrive so the live view stays real-time.
"""

from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator

import httpx

from .base import Brain


class OpenAIBrain(Brain):
    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str = "gpt-4o-mini",
        base_url: str = "https://api.openai.com/v1",
        temperature: float = 0.4,
        name: str | None = None,
    ) -> None:
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._temperature = temperature
        # Shown in the UI badge, e.g. "gemini-2.0-flash".
        self.name = name or model
        self._client = httpx.AsyncClient(timeout=60.0)

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
        async with self._client.stream(
            "POST", f"{self._base_url}/chat/completions", json=payload, headers=headers
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data:"):
                    continue
                data = line[len("data:") :].strip()
                if not data or data == "[DONE]":
                    continue
                try:
                    choices = json.loads(data).get("choices", [])
                except json.JSONDecodeError:
                    continue
                if choices:
                    delta = choices[0].get("delta", {}).get("content")
                    if delta:
                        yield delta

    async def aclose(self) -> None:
        await self._client.aclose()
