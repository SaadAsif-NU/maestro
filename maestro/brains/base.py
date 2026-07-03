"""The brain abstraction.

A brain turns a prompt into a stream of text chunks. Agents depend only on this
interface, so the same orchestration runs on the deterministic offline brain (for
demos and tests) or a real model (OpenAI-compatible) by swapping one object.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator


class Brain(ABC):
    """Streams text for a given prompt."""

    name: str

    @abstractmethod
    def stream(
        self, prompt: str, *, system: str | None = None, role: str | None = None
    ) -> AsyncIterator[str]:
        """Yield the response as text chunks (roughly token-sized).

        ``role`` is an optional hint the offline brain uses to pick a script;
        real model brains ignore it and rely on ``system`` plus ``prompt``.
        """

    async def complete(
        self, prompt: str, *, system: str | None = None, role: str | None = None
    ) -> str:
        """Collect a full response (convenience over :meth:`stream`)."""
        parts = [chunk async for chunk in self.stream(prompt, system=system, role=role)]
        return "".join(parts)

    async def aclose(self) -> None:
        return None
