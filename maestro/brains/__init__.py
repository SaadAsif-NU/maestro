"""Pluggable model backends ("brains") and provider configuration."""

from __future__ import annotations

import os

from .base import Brain
from .simulated import SimulatedBrain

__all__ = [
    "Brain",
    "SimulatedBrain",
    "OpenAIBrain",
    "build_brain",
    "provider_status",
    "provider_models",
    "default_selection",
]

_GEMINI_OPENAI_BASE = "https://generativelanguage.googleapis.com/v1beta/openai"

# Curated model menus for the UI. Any model can still be forced via MAESTRO_MODEL
# or by editing these lists.
_GEMINI_MODELS = [
    "gemini-2.5-flash",
    "gemini-3.5-flash",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-1.5-flash",
]
_OPENAI_MODELS = ["gpt-5", "gpt-4o", "gpt-4o-mini", "gpt-4.1-mini"]

_DEFAULT_GEMINI = "gemini-2.5-flash"
_DEFAULT_OPENAI = "gpt-4o-mini"


def _gemini_key() -> str | None:
    return os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")


def _max_concurrency() -> int:
    return int(os.environ.get("MAESTRO_MAX_CONCURRENCY", "3"))


def provider_status() -> dict[str, bool]:
    """Which providers have an API key configured (offline is always available)."""
    return {
        "simulated": True,
        "gemini": bool(_gemini_key()),
        "openai": bool(os.environ.get("OPENAI_API_KEY")),
    }


def provider_models(provider: str) -> list[str]:
    return {"simulated": ["simulated"], "gemini": _GEMINI_MODELS, "openai": _OPENAI_MODELS}.get(
        provider, []
    )


def default_selection() -> tuple[str, str]:
    """The provider/model a keyless run would auto-pick (respects MAESTRO_MODEL)."""
    override = os.environ.get("MAESTRO_MODEL")
    if _gemini_key():
        return ("gemini", override or _DEFAULT_GEMINI)
    if os.environ.get("OPENAI_API_KEY"):
        return ("openai", override or _DEFAULT_OPENAI)
    return ("simulated", "simulated")


def _simulated() -> Brain:
    return SimulatedBrain(delay=float(os.environ.get("MAESTRO_SIM_DELAY", "0.02")))


def build_brain(provider: str | None = None, model: str | None = None) -> Brain:
    """Build a brain for an explicit provider/model, or auto-detect from the env.

    Falls back to the offline brain if a real provider is requested without a key,
    so a run never crashes.
    """
    if provider is None:
        provider, model = default_selection()

    if provider == "gemini" and _gemini_key():
        from .openai import OpenAIBrain

        chosen = model or _DEFAULT_GEMINI
        return OpenAIBrain(
            api_key=_gemini_key(),
            model=chosen,
            base_url=os.environ.get("GEMINI_BASE_URL", _GEMINI_OPENAI_BASE),
            name=chosen,
            max_concurrency=_max_concurrency(),
        )
    if provider == "openai" and os.environ.get("OPENAI_API_KEY"):
        from .openai import OpenAIBrain

        chosen = model or _DEFAULT_OPENAI
        return OpenAIBrain(
            model=chosen,
            base_url=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            name=chosen,
            max_concurrency=_max_concurrency(),
        )
    return _simulated()


def __getattr__(name: str) -> object:
    if name == "OpenAIBrain":
        from .openai import OpenAIBrain

        return OpenAIBrain
    raise AttributeError(name)
