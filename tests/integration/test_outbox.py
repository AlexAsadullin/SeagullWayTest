from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from fabric.inventory.infrastructure.models import OutboxRow
from tests.integration.api_helpers import add_order, add_roll, cancel, reserve


async def outbox(sessions: async_sessionmaker[AsyncSession]) -> list[OutboxRow]:
    async with sessions() as session:
        return list(await session.scalars(select(OutboxRow).order_by(OutboxRow.occurred_at)))


async def test_reserve_writes_material_reserved(
    client: AsyncClient, sessions: async_sessionmaker[AsyncSession]
) -> None:
    roll = await add_roll(client, "100")
    order = await add_order(client, 10, "2")

    await reserve(client, order["id"])

    [row] = await outbox(sessions)
    assert row.event_type == "MaterialReserved"
    assert row.published_at is None
    assert row.attempts == 0
    assert row.payload == {
        "order_id": order["id"],
        "sku": "TKN-0001",
        "lines": [{"roll_id": roll["id"], "meters": "20.00"}],
    }


async def test_refused_reserve_writes_nothing(
    client: AsyncClient, sessions: async_sessionmaker[AsyncSession]
) -> None:
    order = await add_order(client, 10, "2")

    await reserve(client, order["id"])

    assert await outbox(sessions) == []


async def test_cancel_twice_writes_one_cancelled_event(
    client: AsyncClient, sessions: async_sessionmaker[AsyncSession]
) -> None:
    await add_roll(client, "100")
    order = await add_order(client, 10, "2")
    await reserve(client, order["id"])

    await cancel(client, order["id"])
    await cancel(client, order["id"])

    rows = await outbox(sessions)
    assert [row.event_type for row in rows] == ["MaterialReserved", "ReservationCancelled"]
    assert rows[1].payload["released_meters"] == "20.00"


async def test_idempotent_repeat_writes_no_second_event(
    client: AsyncClient, sessions: async_sessionmaker[AsyncSession]
) -> None:
    await add_roll(client, "100")
    order = await add_order(client, 10, "2")

    await reserve(client, order["id"], key="once")
    await reserve(client, order["id"], key="once")

    assert len(await outbox(sessions)) == 1
