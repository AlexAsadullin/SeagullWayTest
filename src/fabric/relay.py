import asyncio
import logging

from fabric.inventory.infrastructure.db import database_url, make_engine, make_session_factory
from fabric.inventory.infrastructure.outbox import OutboxRelay
from fabric.inventory.infrastructure.publisher import LogEventPublisher
from fabric.logs import configure_logging

logger = logging.getLogger("fabric.relay")


async def run(relay: OutboxRelay, interval: float = 1.0) -> None:
    while True:
        try:
            sent = await relay.relay_batch()
            if sent:
                logger.info("outbox batch processed", extra={"events": sent})
        except Exception:
            logger.exception("outbox tick failed")
        await asyncio.sleep(interval)


async def main() -> None:
    configure_logging()
    engine = make_engine(database_url())
    logger.info("outbox relay started")
    try:
        await run(OutboxRelay(make_session_factory(engine), LogEventPublisher()))
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
