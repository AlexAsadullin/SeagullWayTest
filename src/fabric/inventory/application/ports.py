from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol, Self
from uuid import UUID

from fabric.inventory.domain.order import ProductionOrder
from fabric.inventory.domain.roll import Roll
from fabric.inventory.domain.values import FabricSku


class RollRepository(Protocol):
    async def add(self, roll: Roll) -> None: ...

    async def by_sku(self, sku: FabricSku | None) -> list[Roll]: ...

    async def lock_by_sku(self, sku: FabricSku) -> list[Roll]: ...

    async def lock_by_ids(self, roll_ids: Iterable[UUID]) -> list[Roll]: ...

    async def save(self, rolls: Iterable[Roll]) -> None: ...


class OrderRepository(Protocol):
    async def add(self, order: ProductionOrder) -> None: ...

    async def get(self, order_id: UUID, *, lock: bool = False) -> ProductionOrder | None: ...

    async def save(self, order: ProductionOrder) -> None: ...


@dataclass(frozen=True, slots=True)
class IdempotentRequest:
    key: str
    endpoint: str
    request_hash: str


@dataclass(frozen=True, slots=True)
class Reply:
    status: int
    body: dict[str, Any]


class IdempotencyStore(Protocol):
    async def claim(self, request: IdempotentRequest) -> Reply | None:
        """None means the key is ours now, otherwise the reply stored by the first request."""
        ...

    async def complete(self, request: IdempotentRequest, reply: Reply) -> None: ...


class UnitOfWork(Protocol):
    @property
    def rolls(self) -> RollRepository: ...

    @property
    def orders(self) -> OrderRepository: ...

    @property
    def idempotency_keys(self) -> IdempotencyStore: ...

    async def __aenter__(self) -> Self: ...

    async def __aexit__(self, *exc: object) -> None: ...

    async def commit(self) -> None: ...


@dataclass(frozen=True, slots=True)
class OutboxMessage:
    id: UUID
    event_type: str
    payload: dict[str, Any]
    occurred_at: datetime


class EventPublisher(Protocol):
    async def publish(self, message: OutboxMessage) -> None: ...
