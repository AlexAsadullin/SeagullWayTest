import logging
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from fabric.inventory.application.ports import EventPublisher, OutboxMessage
from fabric.inventory.domain.events import DomainEvent, MaterialReserved, ReservationCancelled
from fabric.inventory.infrastructure.models import OutboxRow

BATCH_SIZE = 100
# A row that reached MAX_ATTEMPTS is dead: the relay stops picking it and the log says so.
MAX_ATTEMPTS = 5

logger = logging.getLogger("fabric.relay")


def outbox_row(event: DomainEvent) -> OutboxRow:
    payload: dict[str, Any] = {"order_id": str(event.order_id), "sku": str(event.sku)}
    match event:
        case MaterialReserved(lines=lines):
            payload["lines"] = [
                {"roll_id": str(roll_id), "meters": str(meters)} for roll_id, meters in lines
            ]
        case ReservationCancelled(released_meters=released):
            payload["released_meters"] = str(released)
    return OutboxRow(
        id=uuid4(),
        event_type=type(event).__name__,
        payload=payload,
        occurred_at=event.occurred_at,
        attempts=0,
    )


class OutboxRelay:
    def __init__(
        self, sessions: async_sessionmaker[AsyncSession], publisher: EventPublisher
    ) -> None:
        self._sessions = sessions
        self._publisher = publisher

    async def relay_batch(self) -> int:
        async with self._sessions() as session, session.begin():
            # Skip locked lets several relays run side by side without sending one event twice.
            rows = await session.scalars(
                select(OutboxRow)
                .where(OutboxRow.published_at.is_(None), OutboxRow.attempts < MAX_ATTEMPTS)
                .order_by(OutboxRow.occurred_at)
                .limit(BATCH_SIZE)
                .with_for_update(skip_locked=True)
            )
            batch = list(rows)
            for row in batch:
                await self._send(row)
            return len(batch)

    async def _send(self, row: OutboxRow) -> None:
        message = OutboxMessage(row.id, row.event_type, row.payload, row.occurred_at)
        try:
            await self._publisher.publish(message)
        except Exception:
            row.attempts += 1
            log = {"event_id": str(row.id), "event_type": row.event_type, "attempts": row.attempts}
            if row.attempts >= MAX_ATTEMPTS:
                logger.error("outbox event is dead, giving up", extra=log, exc_info=True)
            else:
                logger.warning("publish failed, will retry", extra=log, exc_info=True)
            return
        row.published_at = datetime.now(UTC)
