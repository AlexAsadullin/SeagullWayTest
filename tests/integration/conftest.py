from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from testcontainers.community.postgres import PostgresContainer

from fabric.inventory.infrastructure.db import make_engine, make_session_factory
from fabric.inventory.infrastructure.unit_of_work import SqlAlchemyUnitOfWork
from fabric.main import create_app

ROOT = Path(__file__).resolve().parents[2]
TABLES = "reservation_lines, production_orders, rolls, idempotency_keys, outbox"


@pytest.fixture(scope="session")
def database_url() -> Iterator[str]:
    with PostgresContainer("postgres:16-alpine", driver="asyncpg") as postgres:
        url = postgres.get_connection_url()
        config = Config(str(ROOT / "alembic.ini"))
        config.attributes["database_url"] = url
        config.attributes["configure_logger"] = False
        command.upgrade(config, "head")
        yield url


@pytest.fixture
async def engine(database_url: str) -> AsyncIterator[AsyncEngine]:
    engine = make_engine(database_url)
    async with engine.begin() as connection:
        await connection.execute(text(f"truncate {TABLES}"))
    yield engine
    await engine.dispose()


@pytest.fixture
def sessions(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return make_session_factory(engine)


@pytest.fixture
def uow(sessions: async_sessionmaker[AsyncSession]) -> SqlAlchemyUnitOfWork:
    return SqlAlchemyUnitOfWork(sessions)


@pytest.fixture
async def client(engine: AsyncEngine, database_url: str) -> AsyncIterator[AsyncClient]:
    app = create_app(database_url)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    await app.state.engine.dispose()
