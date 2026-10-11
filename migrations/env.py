import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.engine import Connection

from fabric.inventory.infrastructure.db import database_url, make_engine
from fabric.inventory.infrastructure.models import Base

config = context.config
if config.config_file_name is not None and config.attributes.get("configure_logger", True):
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_online() -> None:
    engine = make_engine(config.attributes.get("database_url") or database_url())
    async with engine.connect() as connection:
        await connection.run_sync(run_migrations)
    await engine.dispose()


asyncio.run(run_online())
