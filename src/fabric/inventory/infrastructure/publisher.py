import logging

from fabric.inventory.application.ports import OutboxMessage

logger = logging.getLogger("fabric.events")


class LogEventPublisher:
    async def publish(self, message: OutboxMessage) -> None:
        logger.info(
            "event published",
            extra={
                "event_id": str(message.id),
                "event_type": message.event_type,
                "occurred_at": message.occurred_at.isoformat(),
                "payload": message.payload,
            },
        )
