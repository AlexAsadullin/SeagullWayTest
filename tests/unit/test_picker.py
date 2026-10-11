import pytest

from fabric.inventory.domain.errors import InsufficientFabric
from fabric.inventory.domain.picker import RollPicker
from fabric.inventory.domain.roll import Roll
from fabric.inventory.domain.values import FabricSku, Meters

JERSEY = FabricSku("TKN-0001")


def rolls(*left: str) -> list[Roll]:
    return [Roll.receive(JERSEY, Meters(meters)) for meters in left]


def cut_sizes(cuts: list[tuple[Roll, Meters]]) -> list[tuple[str, str]]:
    return [(str(roll.available), str(meters)) for roll, meters in cuts]


def test_picks_smallest_roll_that_covers_whole_need() -> None:
    cuts = RollPicker().pick(rolls("100", "30", "50", "25"), Meters(28))

    assert cut_sizes(cuts) == [("30.00", "28.00")]


def test_exact_fit_is_preferred_over_bigger_roll() -> None:
    cuts = RollPicker().pick(rolls("50", "28"), Meters(28))

    assert cut_sizes(cuts) == [("28.00", "28.00")]


def test_without_fitting_roll_finishes_smallest_rolls_first() -> None:
    cuts = RollPicker().pick(rolls("10", "20", "15"), Meters(40))

    assert cut_sizes(cuts) == [("10.00", "10.00"), ("15.00", "15.00"), ("20.00", "15.00")]


def test_after_finishing_a_roll_looks_for_fitting_one_again() -> None:
    # Nothing covers 38, so 10 is finished first. Then 28 fits into 30 and 35 stays untouched.
    cuts = RollPicker().pick(rolls("35", "10", "30"), Meters(38))

    assert cut_sizes(cuts) == [("10.00", "10.00"), ("30.00", "28.00")]


def test_skips_rolls_with_nothing_left() -> None:
    empty, full = rolls("10", "10")
    empty.reserve(Meters(10))

    cuts = RollPicker().pick([empty, full], Meters(4))

    assert [roll for roll, _ in cuts] == [full]


def test_not_enough_fabric_raises() -> None:
    with pytest.raises(InsufficientFabric):
        RollPicker().pick(rolls("10", "5"), Meters("15.01"))


def test_picking_does_not_touch_rolls() -> None:
    candidates = rolls("10", "5")

    RollPicker().pick(candidates, Meters(12))

    assert [roll.available for roll in candidates] == [Meters(10), Meters(5)]
