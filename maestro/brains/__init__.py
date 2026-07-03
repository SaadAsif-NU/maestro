"""Pluggable model backends ("brains")."""

from __future__ import annotations

import os

from .base import Brain
from .simulated import SimulatedBrain

__all__ = ["Brain", "SimulatedBrain", "build_brain", "OpenAIBrain"]


def build_brain() -> Brain:
    """Pick a brain from the environment.

    Uses a real OpenAI-compatible model when ``OPENAI_API_KEY`` is set, otherwise
    the deterministic offline brain so the studio always runs.
    """
    if os.environ.get("OPENAI_API_KEY"):
        from .openai import OpenAIBrain

        return OpenAIBrain(
            model=os.environ.get("MAESTRO_MODEL", "gpt-4o-mini"),
            base_url=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        )
    return SimulatedBrain(delay=float(os.environ.get("MAESTRO_SIM_DELAY", "0.02")))


def __getattr__(name: str) -> object:
    if name == "OpenAIBrain":
        from .openai import OpenAIBrain

        return OpenAIBrain
    raise AttributeError(name)
