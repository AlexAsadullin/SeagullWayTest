from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from fabric.inventory.application.errors import OrderNotFound
from fabric.inventory.application.use_cases import (
    cancel_order,
    draft_order,
    get_order,
    list_rolls,
    receive_roll,
    reserve_order,
)
from fabric.inventory.domain.order import OrderStatus
from fabric.inventory.domain.values import FabricSku, Meters
from fabric.inventory.infrastructure.models import RollRow
from fabric.inventory.infrastructure.unit_of_work import SqlAlchemyUnitOfWork

JERSEY = FabricSku("TKN-0001")


async def test_reserved_meters_survive_reload(uow: SqlAlchemyUnitOfWork) -> None:
    async with uow:
        roll = await receive_roll(uow, JERSEY, Meters(300))
        order = await draft_order(uow, JERSEY, 200, Meters("1.4"))
        await uow.commit()

    async with uow:
        await reserve_order(uow, order.id)
        await uow.commit()

    async with uow:
        [stored_roll] = await list_rolls(uow, JERSEY)
        stored_order = await get_order(uow, order.id)

    assert stored_roll.id == roll.id
    assert stored_roll.available == Meters(20)
    assert stored_roll.version == 1
    assert stored_order.status is OrderStatus.RESERVED
    assert [(line.roll_id, line.meters) for line in stored_order.lines] == [(roll.id, Meters(280))]


async def test_cancelled_order_gives_fabric_back(uow: SqlAlchemyUnitOfWork) -> None:
    async with uow:
        await receive_roll(uow, JERSEY, Meters(100))
        order = await draft_order(uow, JERSEY, 10, Meters(5))
        await uow.commit()
    async with uow:
        await reserve_order(uow, order.id)
        await uow.commit()

    async with uow:
        await cancel_order(uow, order.id)
        await uow.commit()

    async with uow:
        [roll] = await list_rolls(uow, None)
        cancelled = await get_order(uow, order.id)
    assert roll.available == Meters(100)
    assert roll.version == 2
    assert cancelled.status is OrderStatus.CANCELLED
    assert len(cancelled.lines) == 1


async def test_uncommitted_reservation_is_rolled_back(
    uow: SqlAlchemyUnitOfWork, sessions: async_sessionmaker[AsyncSession]
) -> None:
    async with uow:
        await receive_roll(uow, JERSEY, Meters(100))
        order = await draft_order(uow, JERSEY, 10, Meters(5))
        await uow.commit()

    async with uow:
        await reserve_order(uow, order.id)

    async with sessions() as session:
        versions = list(await session.scalars(select(RollRow.version)))
    async with uow:
        assert (await get_order(uow, order.id)).status is OrderStatus.DRAFT
    assert versions == [0]


async def test_rolls_are_filtered_by_sku(uow: SqlAlchemyUnitOfWork) -> None:
    async with uow:
        await receive_roll(uow, JERSEY, Meters(10))
        await receive_roll(uow, FabricSku("DNM-0001"), Meters(10))
        await uow.commit()

    async with uow:
        assert [str(r.sku) for r in await list_rolls(uow, JERSEY)] == ["TKN-0001"]
        assert len(await list_rolls(uow, None)) == 2


async def test_unknown_order_is_not_found(uow: SqlAlchemyUnitOfWork) -> None:
    async with uow:
        with pytest.raises(OrderNotFound):
            await reserve_order(uow, uuid4())
