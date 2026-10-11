import asyncio
import os

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

DEFAULT_DATABASE_URL = "postgresql+asyncpg://fabric:fabric@localhost:5432/fabric"


def database_url() -> str:
    return os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)


def make_engine(url: str) -> AsyncEngine:
    return create_async_engine(url, pool_pre_ping=True)


def make_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


async def database_is_up(engine: AsyncEngine) -> bool:
    try:
        async with asyncio.timeout(2), engine.connect() as connection:
            await connection.execute(text("select 1"))
    except (OSError, TimeoutError, SQLAlchemyError):
        return False
    return True
