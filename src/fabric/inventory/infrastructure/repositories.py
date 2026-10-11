from collections.abc import Iterable, Sequence
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from fabric.inventory.domain.order import OrderStatus, ProductionOrder, ReservationLine
from fabric.inventory.domain.roll import Roll
from fabric.inventory.domain.values import FabricSku, Meters
from fabric.inventory.infrastructure.models import OrderRow, ReservationLineRow, RollRow


class SqlRollRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._rows: dict[UUID, RollRow] = {}

    async def add(self, roll: Roll) -> None:
        row = RollRow(id=roll.id, sku=str(roll.sku), total=roll.total.value, version=roll.version)
        self._session.add(row)
        self._rows[roll.id] = row

    async def by_sku(self, sku: FabricSku | None) -> list[Roll]:
        query = select(RollRow).order_by(RollRow.created_at, RollRow.id)
        if sku is not None:
            query = query.where(RollRow.sku == str(sku))
        return await self._load(query)

    async def lock_by_sku(self, sku: FabricSku) -> list[Roll]:
        # Every reserve takes row locks in the same id order, so two reserves on one sku
        # queue up behind each other instead of deadlocking.
        query = select(RollRow).where(RollRow.sku == str(sku)).order_by(RollRow.id)
        return await self._load(query.with_for_update())

    async def lock_by_ids(self, roll_ids: Iterable[UUID]) -> list[Roll]:
        query = select(RollRow).where(RollRow.id.in_(list(roll_ids))).order_by(RollRow.id)
        return await self._load(query.with_for_update())

    async def save(self, rolls: Iterable[Roll]) -> None:
        for roll in rolls:
            self._rows[roll.id].version = roll.version
        await self._session.flush()

    async def _load(self, query: Select[RollRow]) -> list[Roll]:
        rows = list(await self._session.scalars(query))
        reserved = await self._reserved([row.id for row in rows])
        self._rows.update((row.id, row) for row in rows)
        return [
            Roll(
                id=row.id,
                sku=FabricSku(row.sku),
                total=Meters(row.total),
                reserved=Meters(reserved.get(row.id, Decimal(0))),
                version=row.version,
            )
            for row in rows
        ]

    async def _reserved(self, roll_ids: Sequence[UUID]) -> dict[UUID, Decimal]:
        if not roll_ids:
            return {}
        query = (
            select(ReservationLineRow.roll_id, func.sum(ReservationLineRow.meters))
            .join(OrderRow, OrderRow.id == ReservationLineRow.order_id)
            .where(
                OrderRow.status == OrderStatus.RESERVED.value,
                ReservationLineRow.roll_id.in_(roll_ids),
            )
            .group_by(ReservationLineRow.roll_id)
        )
        return {roll_id: meters for roll_id, meters in await self._session.execute(query)}


class SqlOrderRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._rows: dict[UUID, OrderRow] = {}
        self.seen: list[ProductionOrder] = []

    async def add(self, order: ProductionOrder) -> None:
        row = OrderRow(
            id=order.id,
            sku=str(order.sku),
            quantity=order.quantity,
            consumption_per_unit=order.consumption_per_unit.value,
            status=order.status.value,
        )
        self._session.add(row)
        self._track(order, row)

    async def get(self, order_id: UUID, *, lock: bool = False) -> ProductionOrder | None:
        query = select(OrderRow).where(OrderRow.id == order_id)
        if lock:
            query = query.with_for_update()
        row = await self._session.scalar(query)
        if row is None:
            return None
        order = ProductionOrder(
            id=row.id,
            sku=FabricSku(row.sku),
            quantity=row.quantity,
            consumption_per_unit=Meters(row.consumption_per_unit),
            status=OrderStatus(row.status),
            lines=[ReservationLine(line.roll_id, Meters(line.meters)) for line in row.lines],
        )
        self._track(order, row)
        return order

    async def save(self, order: ProductionOrder) -> None:
        row = self._rows[order.id]
        row.status = order.status.value
        stored = {line.roll_id for line in row.lines}
        row.lines.extend(
            ReservationLineRow(roll_id=line.roll_id, meters=line.meters.value)
            for line in order.lines
            if line.roll_id not in stored
        )
        await self._session.flush()

    def _track(self, order: ProductionOrder, row: OrderRow) -> None:
        self._rows[order.id] = row
        self.seen.append(order)
