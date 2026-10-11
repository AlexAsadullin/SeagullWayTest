from typing import Any
from uuid import uuid4

from fabric.inventory.domain.events import DomainEvent, MaterialReserved, ReservationCancelled
from fabric.inventory.infrastructure.models import OutboxRow


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
