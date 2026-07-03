"""Tool interface."""

from __future__ import annotations

from abc import ABC, abstractmethod


class Tool(ABC):
    name: str
    description: str

    @abstractmethod
    async def run(self, argument: str) -> str:
        """Execute the tool and return a text result."""
