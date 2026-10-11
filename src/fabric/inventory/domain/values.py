import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Self

from fabric.inventory.domain.errors import InvalidSku, InvalidValue, NegativeMeters

_CENT = Decimal("0.01")
_SKU_PATTERN = re.compile(r"[A-Z]{3}-\d{4}")


@dataclass(frozen=True, order=True, slots=True)
class Meters:
    value: Decimal

    def __init__(self, value: Decimal | int | str) -> None:
        try:
            amount = Decimal(value)
        except InvalidOperation:
            raise InvalidValue(f"not a number: {value!r}") from None
        if not amount.is_finite():
            raise InvalidValue(f"not a number: {value!r}")
        # Refuse silent rounding: 1.405 m per shirt rounded to 1.41 would break exact reservations.
        if amount != amount.quantize(_CENT):
            raise InvalidValue(f"meters must have at most two decimals, got {value}")
        if amount < 0:
            raise NegativeMeters(f"meters can not be negative, got {value}")
        object.__setattr__(self, "value", amount.quantize(_CENT))

    @classmethod
    def zero(cls) -> Self:
        return cls(0)

    def __add__(self, other: "Meters") -> "Meters":
        return Meters(self.value + other.value)

    def __sub__(self, other: "Meters") -> "Meters":
        return Meters(self.value - other.value)

    def __mul__(self, times: int) -> "Meters":
        return Meters(self.value * times)

    def __bool__(self) -> bool:
        return self.value > 0

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True)
class FabricSku:
    value: str

    def __post_init__(self) -> None:
        if not _SKU_PATTERN.fullmatch(self.value):
            raise InvalidSku(f"sku must look like TKN-0001, got {self.value!r}")

    def __str__(self) -> str:
        return self.value
