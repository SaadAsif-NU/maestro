"""Centralised runtime settings.

One typed place that owns every environment knob and its default, so the rest of
the codebase never reaches into ``os.environ`` directly. Read live from the
environment (after any ``.env`` is loaded) via :meth:`Settings.from_env`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


def _float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except ValueError:
        return default


@dataclass(frozen=True, slots=True)
class Settings:
    """Process configuration resolved from the environment."""

    log_level: str
    sim_delay: float
    max_concurrency: int
    model_override: str | None
    # Reliability guards.
    max_runs: int
    run_timeout_s: float
    max_concurrent_runs: int
    # Comma-separated CORS origins; empty means same-origin only.
    cors_origins: tuple[str, ...]

    @classmethod
    def from_env(cls) -> Settings:
        raw_cors = os.environ.get("MAESTRO_CORS_ORIGINS", "").strip()
        origins = tuple(o.strip() for o in raw_cors.split(",") if o.strip())
        return cls(
            log_level=os.environ.get("MAESTRO_LOG_LEVEL", "INFO").upper(),
            sim_delay=_float("MAESTRO_SIM_DELAY", 0.02),
            max_concurrency=max(1, _int("MAESTRO_MAX_CONCURRENCY", 3)),
            model_override=os.environ.get("MAESTRO_MODEL") or None,
            max_runs=max(1, _int("MAESTRO_MAX_RUNS", 200)),
            # Generous by default so a real-model run that hits free-tier rate
            # limits (retries + backoff) still finishes; a genuinely hung run is
            # still bounded.
            run_timeout_s=_float("MAESTRO_RUN_TIMEOUT", 300.0),
            max_concurrent_runs=max(1, _int("MAESTRO_MAX_CONCURRENT_RUNS", 8)),
            cors_origins=origins,
        )
