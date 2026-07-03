"""Structured logging.

Emits one JSON object per line so records are machine-parseable by any log
pipeline without a custom grok rule. Dependency free: a thin ``logging.Formatter``
plus a helper. The rest of the codebase logs through :func:`log_event`.
"""

from __future__ import annotations

import json
import logging
import sys
from typing import Any

LOGGER_NAME = "maestro"


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        fields = getattr(record, "fields", None)
        if isinstance(fields, dict):
            payload.update(fields)
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO") -> None:
    """Install the JSON formatter on the ``maestro`` logger (idempotent)."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger(LOGGER_NAME)
    logger.handlers = [handler]
    logger.setLevel(level.upper())
    logger.propagate = False


def get_logger() -> logging.Logger:
    return logging.getLogger(LOGGER_NAME)


def log_event(event: str, level: int = logging.INFO, **fields: Any) -> None:
    get_logger().log(level, event, extra={"fields": {"event": event, **fields}})
