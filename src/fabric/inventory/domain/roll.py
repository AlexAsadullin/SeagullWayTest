from dataclasses import dataclass, field
from uuid import UUID, uuid4

from fabric.inventory.domain.errors import InsufficientFabric, InvalidValue
from fabric.inventory.domain.values import FabricSku, Meters


@dataclass(eq=False)
class Roll:
    id: UUID
    sku: FabricSku
    total: Meters
    reserved: Meters = field(default_factory=Meters.zero)
    version: int = 0

    @classmethod
    def receive(cls, sku: FabricSku, total: Meters) -> "Roll":
        if not total:
            raise InvalidValue("roll must have some fabric on it")
        return cls(id=uuid4(), sku=sku, total=total)

    @property
    def available(self) -> Meters:
        return self.total - self.reserved

    def reserve(self, meters: Meters) -> None:
        if meters > self.available:
            raise InsufficientFabric(
                f"roll {self.id} has {self.available} m left, asked for {meters} m"
            )
        self.reserved += meters
        self.version += 1

    def release(self, meters: Meters) -> None:
        self.reserved -= meters
        self.version += 1
