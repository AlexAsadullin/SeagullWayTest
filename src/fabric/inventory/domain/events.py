from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from fabric.inventory.domain.values import FabricSku, Meters


@dataclass(frozen=True, slots=True)
class MaterialReserved:
    order_id: UUID
    sku: FabricSku
    lines: tuple[tuple[UUID, Meters], ...]
    occurred_at: datetime


@dataclass(frozen=True, slots=True)
class ReservationCancelled:
    order_id: UUID
    sku: FabricSku
    released_meters: Meters
    occurred_at: datetime


DomainEvent = MaterialReserved | ReservationCancelled
