import asyncio

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from fabric.inventory.infrastructure.models import IdempotencyKeyRow, ReservationLineRow
from tests.integration.api_helpers import add_order, add_roll, cancel, reserve


async def test_repeated_reserve_returns_stored_reply(client: AsyncClient) -> None:
    await add_roll(client, "100")
    order = await add_order(client, 10, "2")

    first = await reserve(client, order["id"], key="reserve-1")
    second = await reserve(client, order["id"], key="reserve-1")

    assert first.status_code == second.status_code == 200
    assert second.json() == first.json()


async def test_repeated_cancel_returns_stored_reply(client: AsyncClient) -> None:
    await add_roll(client, "100")
    order = await add_order(client, 10, "2")
    await reserve(client, order["id"])

    first = await cancel(client, order["id"], key="cancel-1")
    second = await cancel(client, order["id"], key="cancel-1")

    assert first.status_code == second.status_code == 200
    assert second.json() == first.json()


async def test_cancel_with_new_key_after_cancel_changes_nothing(client: AsyncClient) -> None:
    await add_roll(client, "100")
    order = await add_order(client, 10, "2")
    await reserve(client, order["id"])
    await cancel(client, order["id"])

    again = await cancel(client, order["id"])

    assert again.status_code == 200
    assert again.json()["status"] == "cancelled"


async def test_same_key_on_another_endpoint_is_conflict(client: AsyncClient) -> None:
    await add_roll(client, "100")
    order = await add_order(client, 10, "2")
    await reserve(client, order["id"], key="shared")

    response = await cancel(client, order["id"], key="shared")

    assert response.status_code == 409
    assert response.json()["error"] == "idempotency_key_conflict"
    assert (await client.get(f"/orders/{order['id']}")).json()["status"] == "reserved"


async def test_same_key_with_another_body_is_conflict(client: AsyncClient) -> None:
    await add_roll(client, "100")
    order = await add_order(client, 10, "2")
    url = f"/orders/{order['id']}/reserve"
    await client.post(url, headers={"Idempotency-Key": "k"})

    response = await client.post(url, headers={"Idempotency-Key": "k"}, json={"rush": True})

    assert response.status_code == 409
    assert response.json()["error"] == "idempotency_key_conflict"


async def test_missing_key_is_validation_error(client: AsyncClient) -> None:
    order = await add_order(client, 10, "2")

    response = await client.post(f"/orders/{order['id']}/reserve")

    assert response.status_code == 422
    assert response.json()["error"] == "validation_error"


async def test_failed_reserve_does_not_burn_the_key(
    client: AsyncClient, sessions: async_sessionmaker[AsyncSession]
) -> None:
    order = await add_order(client, 10, "2")

    refused = await reserve(client, order["id"], key="retry-me")
    async with sessions() as session:
        keys = await session.scalar(select(func.count()).select_from(IdempotencyKeyRow))
    await add_roll(client, "100")
    retried = await reserve(client, order["id"], key="retry-me")

    assert refused.status_code == 409
    assert keys == 0
    assert retried.status_code == 200


async def test_parallel_requests_with_one_key_reserve_once(
    client: AsyncClient, sessions: async_sessionmaker[AsyncSession]
) -> None:
    await add_roll(client, "100")
    order = await add_order(client, 10, "2")

    replies = await asyncio.gather(*(reserve(client, order["id"], key="burst") for _ in range(10)))

    assert {r.status_code for r in replies} == {200}
    assert all(r.json() == replies[0].json() for r in replies)
    async with sessions() as session:
        lines = await session.scalar(select(func.count()).select_from(ReservationLineRow))
    assert lines == 1
