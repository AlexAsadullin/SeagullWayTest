from typing import Self

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from fabric.inventory.infrastructure.repositories import SqlOrderRepository, SqlRollRepository


class SqlAlchemyUnitOfWork:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def __aenter__(self) -> Self:
        self.session = self._session_factory()
        self.rolls = SqlRollRepository(self.session)
        self.orders = SqlOrderRepository(self.session)
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.session.rollback()
        await self.session.close()

    async def commit(self) -> None:
        await self.session.commit()
