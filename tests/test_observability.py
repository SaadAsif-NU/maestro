from __future__ import annotations

import json
import logging

from maestro.observability import JsonFormatter, configure_logging, get_logger, log_event


def test_json_formatter_includes_fields():
    record = logging.LogRecord("maestro", logging.INFO, "", 0, "run.started", None, None)
    record.fields = {"event": "run.started", "run_id": "r1"}
    parsed = json.loads(JsonFormatter().format(record))
    assert parsed["message"] == "run.started"
    assert parsed["level"] == "INFO"
    assert parsed["run_id"] == "r1"


def test_configure_logging_is_idempotent():
    configure_logging("DEBUG")
    configure_logging("INFO")
    logger = get_logger()
    assert len(logger.handlers) == 1
    assert logger.level == logging.INFO


def test_log_event_carries_structured_fields():
    configure_logging("INFO")
    logger = get_logger()
    captured: list[logging.LogRecord] = []

    class Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            captured.append(record)

    logger.addHandler(Capture())
    log_event("run.completed", run_id="r1", agents=6)
    logger.handlers = [h for h in logger.handlers if not isinstance(h, Capture)]
    assert any(getattr(r, "fields", {}).get("agents") == 6 for r in captured)
