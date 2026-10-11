import io
import json
import logging
from collections.abc import Iterator

import pytest
from httpx import AsyncClient

from fabric.logs import JsonFormatter


@pytest.fixture
def json_log() -> Iterator[io.StringIO]:
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("fabric")
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    yield stream
    logger.removeHandler(handler)


def lines(stream: io.StringIO) -> list[dict[str, object]]:
    return [json.loads(line) for line in stream.getvalue().splitlines()]


async def test_request_log_carries_generated_request_id(
    client: AsyncClient, json_log: io.StringIO
) -> None:
    response = await client.get("/health")

    [entry] = [e for e in lines(json_log) if e["message"] == "request"]
    assert entry["request_id"] == response.headers["X-Request-ID"]
    assert entry["path"] == "/health"
    assert entry["status"] == 200


async def test_incoming_request_id_is_kept(client: AsyncClient, json_log: io.StringIO) -> None:
    response = await client.get("/rolls", headers={"X-Request-ID": "cutting-room-42"})

    assert response.headers["X-Request-ID"] == "cutting-room-42"
    assert lines(json_log)[-1]["request_id"] == "cutting-room-42"
