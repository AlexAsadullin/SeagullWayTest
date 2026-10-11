from collections.abc import Iterable

from fabric.inventory.domain.errors import InsufficientFabric
from fabric.inventory.domain.roll import Roll
from fabric.inventory.domain.values import Meters


class RollPicker:
    """Smallest roll that covers the rest of the need, otherwise finish the smallest roll."""

    def pick(self, rolls: Iterable[Roll], need: Meters) -> list[tuple[Roll, Meters]]:
        candidates = sorted((r for r in rolls if r.available), key=lambda r: (r.available, r.id))
        on_hand = sum((r.available for r in candidates), Meters.zero())
        if on_hand < need:
            raise InsufficientFabric(f"need {need} m, only {on_hand} m available")

        cuts: list[tuple[Roll, Meters]] = []
        rest = need
        while rest:
            fitting = next((r for r in candidates if r.available >= rest), None)
            if fitting is not None:
                cuts.append((fitting, rest))
                break
            smallest = candidates.pop(0)
            cuts.append((smallest, smallest.available))
            rest -= smallest.available
        return cuts
