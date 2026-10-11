import json
import logging
import sys

from fabric.logs import JsonFormatter, request_id


def test_formatter_outputs_extra_fields_and_errors() -> None:
    record = logging.makeLogRecord({"msg": "boom", "levelname": "ERROR", "roll": "r1"})
    try:
        raise ValueError("torn fabric")
    except ValueError:
        record.exc_info = sys.exc_info()

    entry = json.loads(JsonFormatter().format(record))

    assert entry["message"] == "boom"
    assert entry["roll"] == "r1"
    assert "torn fabric" in entry["exc_info"]
    assert "request_id" not in entry


def test_formatter_adds_current_request_id() -> None:
    token = request_id.set("abc")
    try:
        entry = json.loads(JsonFormatter().format(logging.makeLogRecord({"msg": "hi"})))
    finally:
        request_id.reset(token)

    assert entry["request_id"] == "abc"
