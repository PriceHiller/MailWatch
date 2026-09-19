import datetime
import json
import logging
from typing import cast

import pytest

from mailwatch.log import JsonFormatter, configure_logging


def _record(**context: object) -> logging.LogRecord:
    record = logging.LogRecord(
        name="mailwatch.cli",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="Received message",
        args=(),
        exc_info=None,
    )
    if context:
        setattr(record, "context", context)
    return record


def _payload(formatted: str) -> dict[str, object]:
    return cast("dict[str, object]", json.loads(formatted))


def test_format_includes_core_fields() -> None:
    payload = _payload(JsonFormatter().format(_record()))

    assert payload["level"] == "INFO"
    assert payload["logger"] == "mailwatch.cli"
    assert payload["message"] == "Received message"
    assert "timestamp" in payload


def test_format_merges_context() -> None:
    payload = _payload(JsonFormatter().format(_record(subject="Testing Mailwatch", uid="42")))

    assert payload["subject"] == "Testing Mailwatch"
    assert payload["uid"] == "42"


def test_format_renders_non_serializable_values() -> None:
    payload = _payload(JsonFormatter().format(_record(date=datetime.date(2026, 9, 19))))

    assert payload["date"] == "2026-09-19"


def test_configure_logging_emits_json(capsys: pytest.CaptureFixture[str]) -> None:
    root = logging.getLogger()
    handlers = root.handlers[:]
    level = root.level
    try:
        configure_logging()
        logging.getLogger("test").info("hello", extra={"context": {"key": "value"}})
        payload = _payload(capsys.readouterr().err.strip())
    finally:
        root.handlers[:] = handlers
        root.setLevel(level)

    assert payload["message"] == "hello"
    assert payload["key"] == "value"
