from uuid import UUID

from fabric.inventory.application.errors import OrderNotFound
from fabric.inventory.application.ports import UnitOfWork
from fabric.inventory.domain.order import ProductionOrder
from fabric.inventory.domain.picker import RollPicker
from fabric.inventory.domain.roll import Roll
from fabric.inventory.domain.values import FabricSku, Meters

# Use cases run inside an open unit of work and leave the commit to the caller,
# so an idempotency key can be stored in the same transaction as the change.


async def receive_roll(uow: UnitOfWork, sku: FabricSku, total: Meters) -> Roll:
    """Put a new roll of fabric on the warehouse shelf."""
    roll = Roll.receive(sku, total)
    await uow.rolls.add(roll)
    return roll


async def list_rolls(uow: UnitOfWork, sku: FabricSku | None) -> list[Roll]:
    """Rolls with what is left on them after active reservations."""
    return await uow.rolls.by_sku(sku)


async def draft_order(
    uow: UnitOfWork, sku: FabricSku, quantity: int, consumption_per_unit: Meters
) -> ProductionOrder:
    """Create a production order in draft status."""
    order = ProductionOrder.draft(sku, quantity, consumption_per_unit)
    await uow.orders.add(order)
    return order


async def get_order(uow: UnitOfWork, order_id: UUID) -> ProductionOrder:
    """Order with its reservation lines."""
    return await _existing(uow, order_id, lock=False)


async def reserve_order(uow: UnitOfWork, order_id: UUID) -> ProductionOrder:
    """Reserve the whole required length for an order or fail without touching rolls."""
    order = await _existing(uow, order_id, lock=True)
    rolls = await uow.rolls.lock_by_sku(order.sku)
    order.reserve(rolls, RollPicker())
    await uow.rolls.save(rolls)
    await uow.orders.save(order)
    return order


async def cancel_order(uow: UnitOfWork, order_id: UUID) -> ProductionOrder:
    """Give the reserved fabric back to the rolls, cancelling twice is a no op."""
    order = await _existing(uow, order_id, lock=True)
    rolls = await uow.rolls.lock_by_ids(line.roll_id for line in order.lines)
    order.cancel({roll.id: roll for roll in rolls})
    await uow.rolls.save(rolls)
    await uow.orders.save(order)
    return order


async def _existing(uow: UnitOfWork, order_id: UUID, *, lock: bool) -> ProductionOrder:
    order = await uow.orders.get(order_id, lock=lock)
    if order is None:
        raise OrderNotFound(f"order {order_id} not found")
    return order
