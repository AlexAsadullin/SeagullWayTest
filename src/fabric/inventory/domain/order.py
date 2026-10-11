from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from fabric.inventory.domain.errors import (
    InvalidOrderStatus,
    InvalidValue,
    ReservationMismatch,
    SkuMismatch,
)
from fabric.inventory.domain.events import DomainEvent, MaterialReserved, ReservationCancelled
from fabric.inventory.domain.picker import RollPicker
from fabric.inventory.domain.roll import Roll
from fabric.inventory.domain.values import FabricSku, Meters


class OrderStatus(StrEnum):
    DRAFT = "draft"
    RESERVED = "reserved"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class ReservationLine:
    roll_id: UUID
    meters: Meters


class ProductionOrder:
    def __init__(
        self,
        id: UUID,
        sku: FabricSku,
        quantity: int,
        consumption_per_unit: Meters,
        status: OrderStatus = OrderStatus.DRAFT,
        lines: Sequence[ReservationLine] = (),
    ) -> None:
        if quantity <= 0:
            raise InvalidValue(f"quantity must be positive, got {quantity}")
        if not consumption_per_unit:
            raise InvalidValue("consumption per unit must be positive")
        self.id = id
        self.sku = sku
        self.quantity = quantity
        self.consumption_per_unit = consumption_per_unit
        self.status = status
        self.lines = list(lines)
        self._events: list[DomainEvent] = []

    @classmethod
    def draft(
        cls, sku: FabricSku, quantity: int, consumption_per_unit: Meters
    ) -> "ProductionOrder":
        return cls(uuid4(), sku, quantity, consumption_per_unit)

    @property
    def required(self) -> Meters:
        return self.consumption_per_unit * self.quantity

    def reserve(self, rolls: Sequence[Roll], picker: RollPicker) -> None:
        if self.status is not OrderStatus.DRAFT:
            raise InvalidOrderStatus(f"only draft order can be reserved, order is {self.status}")

        cuts = picker.pick(rolls, self.required)
        foreign = [roll.id for roll, _ in cuts if roll.sku != self.sku]
        if foreign:
            raise SkuMismatch(f"rolls {foreign} are not {self.sku}")
        cut_total = sum((meters for _, meters in cuts), Meters.zero())
        if cut_total != self.required:
            raise ReservationMismatch(f"order needs {self.required} m, cuts give {cut_total} m")

        for roll, meters in cuts:
            roll.reserve(meters)
        self.lines = [ReservationLine(roll.id, meters) for roll, meters in cuts]
        self.status = OrderStatus.RESERVED
        self._events.append(
            MaterialReserved(
                order_id=self.id,
                sku=self.sku,
                lines=tuple((line.roll_id, line.meters) for line in self.lines),
                occurred_at=datetime.now(UTC),
            )
        )

    def cancel(self, rolls: Mapping[UUID, Roll]) -> None:
        if self.status is OrderStatus.CANCELLED:
            return
        if self.status is not OrderStatus.RESERVED:
            raise InvalidOrderStatus(
                f"only reserved order can be cancelled, order is {self.status}"
            )

        for line in self.lines:
            rolls[line.roll_id].release(line.meters)
        self.status = OrderStatus.CANCELLED
        self._events.append(
            ReservationCancelled(
                order_id=self.id,
                sku=self.sku,
                released_meters=self.required,
                occurred_at=datetime.now(UTC),
            )
        )

    def pull_events(self) -> list[DomainEvent]:
        events, self._events = self._events, []
        return events
