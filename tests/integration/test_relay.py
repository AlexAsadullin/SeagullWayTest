import asyncio
import logging
from contextlib import suppress

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from fabric.inventory.application.ports import OutboxMessage
from fabric.inventory.infrastructure.models import OutboxRow
from fabric.inventory.infrastructure.outbox import MAX_ATTEMPTS, OutboxRelay
from fabric.inventory.infrastructure.publisher import LogEventPublisher
from fabric.relay import run
from tests.integration.api_helpers import add_order, add_roll, reserve


class RecordingPublisher:
    def __init__(self, failures: int = 0) -> None:
        self.failures = failures
        self.sent: list[OutboxMessage] = []

    async def publish(self, message: OutboxMessage) -> None:
        if self.failures:
            self.failures -= 1
            raise ConnectionError("broker is down")
        self.sent.append(message)


async def reserved_order(client: AsyncClient) -> str:
    await add_roll(client, "100")
    order = await add_order(client, 10, "2")
    await reserve(client, order["id"])
    order_id: str = order["id"]
    return order_id


async def stored(sessions: async_sessionmaker[AsyncSession]) -> OutboxRow:
    async with sessions() as session:
        return (await session.scalars(select(OutboxRow))).one()


async def test_event_is_published_once(
    client: AsyncClient, sessions: async_sessionmaker[AsyncSession]
) -> None:
    order_id = await reserved_order(client)
    publisher = RecordingPublisher()
    relay = OutboxRelay(sessions, publisher)

    await relay.relay_batch()
    await relay.relay_batch()

    [message] = publisher.sent
    assert message.event_type == "MaterialReserved"
    assert message.payload["order_id"] == order_id
    row = await stored(sessions)
    assert row.id == message.id
    assert row.published_at is not None


async def test_failed_publish_is_retried_later(
    client: AsyncClient, sessions: async_sessionmaker[AsyncSession]
) -> None:
    await reserved_order(client)
    publisher = RecordingPublisher(failures=2)
    relay = OutboxRelay(sessions, publisher)

    await relay.relay_batch()
    await relay.relay_batch()
    assert publisher.sent == []
    assert (await stored(sessions)).attempts == 2

    await relay.relay_batch()

    assert len(publisher.sent) == 1
    assert (await stored(sessions)).published_at is not None


async def test_event_is_dead_after_five_attempts(
    client: AsyncClient,
    sessions: async_sessionmaker[AsyncSession],
    caplog: pytest.LogCaptureFixture,
) -> None:
    await reserved_order(client)
    publisher = RecordingPublisher(failures=100)
    relay = OutboxRelay(sessions, publisher)

    for _ in range(MAX_ATTEMPTS + 2):
        await relay.relay_batch()

    row = await stored(sessions)
    assert row.attempts == MAX_ATTEMPTS
    assert row.published_at is None
    assert publisher.failures == 100 - MAX_ATTEMPTS
    [dead] = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert dead.getMessage() == "outbox event is dead, giving up"


async def test_rows_locked_by_another_relay_are_skipped(
    client: AsyncClient, sessions: async_sessionmaker[AsyncSession]
) -> None:
    await reserved_order(client)
    publisher = RecordingPublisher()

    async with sessions() as other, other.begin():
        await other.scalars(select(OutboxRow).with_for_update())
        assert await OutboxRelay(sessions, publisher).relay_batch() == 0

    assert await OutboxRelay(sessions, publisher).relay_batch() == 1


async def test_log_publisher_writes_event_as_json_fields(
    client: AsyncClient,
    sessions: async_sessionmaker[AsyncSession],
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="fabric.events")
    order_id = await reserved_order(client)

    await OutboxRelay(sessions, LogEventPublisher()).relay_batch()

    [record] = [r for r in caplog.records if r.name == "fabric.events"]
    assert record.event_type == "MaterialReserved"  # type: ignore[attr-defined]
    assert record.payload["order_id"] == order_id  # type: ignore[attr-defined]


async def test_run_loop_keeps_relaying(
    client: AsyncClient, sessions: async_sessionmaker[AsyncSession]
) -> None:
    await reserved_order(client)
    publisher = RecordingPublisher()

    loop = asyncio.create_task(run(OutboxRelay(sessions, publisher), interval=0.01))
    for _ in range(100):
        if publisher.sent:
            break
        await asyncio.sleep(0.01)
    loop.cancel()
    with suppress(asyncio.CancelledError):
        await loop

    assert len(publisher.sent) == 1
