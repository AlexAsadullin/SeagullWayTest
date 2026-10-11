from typing import Self

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from fabric.inventory.infrastructure.outbox import outbox_row
from fabric.inventory.infrastructure.repositories import (
    SqlIdempotencyStore,
    SqlOrderRepository,
    SqlRollRepository,
)


class SqlAlchemyUnitOfWork:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def __aenter__(self) -> Self:
        self.session = self._session_factory()
        self.rolls = SqlRollRepository(self.session)
        self.orders = SqlOrderRepository(self.session)
        self.idempotency_keys = SqlIdempotencyStore(self.session)
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.session.rollback()
        await self.session.close()

    async def commit(self) -> None:
        for order in self.orders.seen:
            self.session.add_all(outbox_row(event) for event in order.pull_events())
        await self.session.commit()
