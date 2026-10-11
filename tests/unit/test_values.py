from decimal import Decimal

import pytest

from fabric.inventory.domain.errors import InvalidSku, InvalidValue, NegativeMeters
from fabric.inventory.domain.values import FabricSku, Meters


def test_meters_keep_two_decimals() -> None:
    assert Meters("1.4").value == Decimal("1.40")
    assert str(Meters(3)) == "3.00"


def test_meters_reject_negative() -> None:
    with pytest.raises(NegativeMeters):
        Meters("-0.01")


def test_meters_reject_more_than_two_decimals() -> None:
    with pytest.raises(InvalidValue):
        Meters("1.405")


def test_meters_reject_garbage() -> None:
    with pytest.raises(InvalidValue):
        Meters("ten")
    with pytest.raises(InvalidValue):
        Meters("NaN")


def test_meters_arithmetic_returns_meters() -> None:
    assert Meters("1.40") + Meters("0.60") == Meters(2)
    assert Meters(10) - Meters("2.5") == Meters("7.5")
    assert Meters("1.4") * 200 == Meters(280)


def test_subtraction_below_zero_is_domain_error() -> None:
    with pytest.raises(NegativeMeters):
        Meters(5) - Meters("5.01")


def test_meters_compare() -> None:
    assert Meters(1) < Meters("1.01")
    assert not Meters.zero()


@pytest.mark.parametrize("raw", ["TKN-0001", "ABC-9999"])
def test_sku_accepts_valid(raw: str) -> None:
    assert str(FabricSku(raw)) == raw


@pytest.mark.parametrize("raw", ["tkn-0001", "TKN0001", "TK-0001", "TKN-001", "TKN-00011", ""])
def test_sku_rejects_invalid(raw: str) -> None:
    with pytest.raises(InvalidSku):
        FabricSku(raw)
