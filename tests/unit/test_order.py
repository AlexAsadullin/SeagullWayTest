from collections.abc import Iterable
from uuid import uuid4

import pytest

from fabric.inventory.domain.errors import (
    InsufficientFabric,
    InvalidOrderStatus,
    InvalidValue,
    ReservationMismatch,
    SkuMismatch,
)
from fabric.inventory.domain.events import MaterialReserved, ReservationCancelled
from fabric.inventory.domain.order import OrderStatus, ProductionOrder
from fabric.inventory.domain.picker import RollPicker
from fabric.inventory.domain.roll import Roll
from fabric.inventory.domain.values import FabricSku, Meters

JERSEY = FabricSku("TKN-0001")
DENIM = FabricSku("DNM-0001")


def roll(total: str, sku: FabricSku = JERSEY) -> Roll:
    return Roll.receive(sku, Meters(total))


def shirts(quantity: int = 200, per_unit: str = "1.4") -> ProductionOrder:
    return ProductionOrder.draft(JERSEY, quantity, Meters(per_unit))


class TakeEverything(RollPicker):
    def pick(self, rolls: Iterable[Roll], need: Meters) -> list[tuple[Roll, Meters]]:
        return [(r, r.available) for r in rolls]


def test_required_meters_is_quantity_times_consumption() -> None:
    assert shirts(200, "1.4").required == Meters(280)


@pytest.mark.parametrize(("quantity", "per_unit"), [(0, "1.4"), (-5, "1.4"), (10, "0")])
def test_order_rejects_empty_quantity_or_consumption(quantity: int, per_unit: str) -> None:
    with pytest.raises(InvalidValue):
        ProductionOrder.draft(JERSEY, quantity, Meters(per_unit))


def test_roll_without_fabric_is_rejected() -> None:
    with pytest.raises(InvalidValue):
        roll("0")


def test_reserve_cuts_exact_meters_and_emits_event() -> None:
    order = shirts(200, "1.4")
    big = roll("300")

    order.reserve([big], RollPicker())

    assert order.status is OrderStatus.RESERVED
    assert [(line.roll_id, line.meters) for line in order.lines] == [(big.id, Meters(280))]
    assert big.available == Meters(20)
    [event] = order.pull_events()
    assert isinstance(event, MaterialReserved)
    assert event.order_id == order.id
    assert event.lines == ((big.id, Meters(280)),)


def test_reserve_spreads_over_several_rolls() -> None:
    order = shirts(100, "1.5")
    rolls = [roll("100"), roll("60")]

    order.reserve(rolls, RollPicker())

    assert sum((line.meters for line in order.lines), Meters.zero()) == Meters(150)
    assert sorted(r.available for r in rolls) == [Meters(0), Meters(10)]


def test_partial_reservation_is_refused() -> None:
    order = shirts(200, "1.4")
    small = roll("100")

    with pytest.raises(InsufficientFabric):
        order.reserve([small], RollPicker())

    assert order.status is OrderStatus.DRAFT
    assert order.lines == []
    assert small.available == Meters(100)
    assert order.pull_events() == []


def test_cuts_must_sum_to_required_exactly() -> None:
    order = shirts(10, "1")

    with pytest.raises(ReservationMismatch):
        order.reserve([roll("50")], TakeEverything())


def test_cuts_from_other_sku_are_refused() -> None:
    order = shirts(10, "1")

    with pytest.raises(SkuMismatch):
        order.reserve([roll("10", DENIM)], TakeEverything())


def test_roll_never_goes_below_zero() -> None:
    small = roll("5")
    with pytest.raises(InsufficientFabric):
        small.reserve(Meters("5.01"))
    assert small.available == Meters(5)


def test_only_draft_order_can_be_reserved() -> None:
    order = shirts(10, "1")
    order.reserve([roll("100")], RollPicker())

    with pytest.raises(InvalidOrderStatus):
        order.reserve([roll("100")], RollPicker())


def test_cancel_releases_rolls_and_emits_event() -> None:
    order = shirts(10, "1")
    big = roll("100")
    order.reserve([big], RollPicker())
    order.pull_events()

    order.cancel({big.id: big})

    assert order.status is OrderStatus.CANCELLED
    assert big.available == Meters(100)
    [event] = order.pull_events()
    assert isinstance(event, ReservationCancelled)
    assert event.released_meters == Meters(10)


def test_cancel_twice_does_not_emit_second_event() -> None:
    order = shirts(10, "1")
    big = roll("100")
    order.reserve([big], RollPicker())
    order.cancel({big.id: big})
    order.pull_events()

    order.cancel({big.id: big})

    assert order.status is OrderStatus.CANCELLED
    assert big.available == Meters(100)
    assert order.pull_events() == []


def test_draft_order_can_not_be_cancelled() -> None:
    with pytest.raises(InvalidOrderStatus):
        shirts().cancel({})


def test_cancelled_order_can_not_be_reserved_again() -> None:
    order = ProductionOrder(uuid4(), JERSEY, 1, Meters(1), status=OrderStatus.CANCELLED)

    with pytest.raises(InvalidOrderStatus):
        order.reserve([roll("10")], RollPicker())
