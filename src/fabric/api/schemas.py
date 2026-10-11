from decimal import Decimal
from typing import Annotated, Self
from uuid import UUID

from pydantic import BaseModel, Field

from fabric.inventory.domain.order import OrderStatus, ProductionOrder
from fabric.inventory.domain.roll import Roll

PositiveMeters = Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=2)]


class RollIn(BaseModel):
    sku: str
    total_meters: PositiveMeters


class RollOut(BaseModel):
    id: UUID
    sku: str
    total_meters: Decimal
    available_meters: Decimal
    version: int

    @classmethod
    def of(cls, roll: Roll) -> Self:
        return cls(
            id=roll.id,
            sku=str(roll.sku),
            total_meters=roll.total.value,
            available_meters=roll.available.value,
            version=roll.version,
        )


class OrderIn(BaseModel):
    sku: str
    quantity: int = Field(gt=0, le=1_000_000)
    consumption_per_unit: PositiveMeters


class LineOut(BaseModel):
    roll_id: UUID
    meters: Decimal


class OrderOut(BaseModel):
    id: UUID
    sku: str
    quantity: int
    consumption_per_unit: Decimal
    required_meters: Decimal
    status: OrderStatus
    lines: list[LineOut]

    @classmethod
    def of(cls, order: ProductionOrder) -> Self:
        return cls(
            id=order.id,
            sku=str(order.sku),
            quantity=order.quantity,
            consumption_per_unit=order.consumption_per_unit.value,
            required_meters=order.required.value,
            status=order.status,
            lines=[LineOut(roll_id=line.roll_id, meters=line.meters.value) for line in order.lines],
        )


class ErrorOut(BaseModel):
    error: str
    detail: str
