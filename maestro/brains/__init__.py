"""Pluggable model backends ("brains")."""

from __future__ import annotations

import os

from .base import Brain
from .simulated import SimulatedBrain

__all__ = ["Brain", "SimulatedBrain", "build_brain", "OpenAIBrain"]


_GEMINI_OPENAI_BASE = "https://generativelanguage.googleapis.com/v1beta/openai"


def build_brain() -> Brain:
    """Pick a brain from the environment.

    Resolution order:

    1. ``GEMINI_API_KEY`` (or ``GOOGLE_API_KEY``): Google Gemini via its
       OpenAI-compatible endpoint. A free key is available at
       https://aistudio.google.com/apikey.
    2. ``OPENAI_API_KEY``: OpenAI, or any OpenAI-compatible ``OPENAI_BASE_URL``.
    3. Otherwise the deterministic offline brain, so the studio always runs.

    Override the model with ``MAESTRO_MODEL``.
    """
    # Lower this (e.g. to 1) if a free tier keeps rate-limiting the fan-out.
    max_concurrency = int(os.environ.get("MAESTRO_MAX_CONCURRENCY", "3"))
    gemini_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if gemini_key:
        from .openai import OpenAIBrain

        model = os.environ.get("MAESTRO_MODEL", "gemini-2.0-flash")
        return OpenAIBrain(
            api_key=gemini_key,
            model=model,
            base_url=os.environ.get("GEMINI_BASE_URL", _GEMINI_OPENAI_BASE),
            name=model,
            max_concurrency=max_concurrency,
        )
    if os.environ.get("OPENAI_API_KEY"):
        from .openai import OpenAIBrain

        model = os.environ.get("MAESTRO_MODEL", "gpt-4o-mini")
        return OpenAIBrain(
            model=model,
            base_url=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            name=model,
            max_concurrency=max_concurrency,
        )
    return SimulatedBrain(delay=float(os.environ.get("MAESTRO_SIM_DELAY", "0.02")))


def __getattr__(name: str) -> object:
    if name == "OpenAIBrain":
        from .openai import OpenAIBrain

        return OpenAIBrain
    raise AttributeError(name)
