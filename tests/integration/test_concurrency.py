import asyncio
from collections import Counter

from httpx import AsyncClient

from tests.integration.api_helpers import add_order, add_roll, cancel, reserve


async def test_parallel_reserves_never_oversell_a_roll(client: AsyncClient) -> None:
    roll = await add_roll(client, "100")
    orders = [await add_order(client, 10, "1") for _ in range(20)]

    replies = await asyncio.gather(*(reserve(client, order["id"]) for order in orders))

    assert Counter(r.status_code for r in replies) == {200: 10, 409: 10}
    assert {r.json()["error"] for r in replies if r.status_code == 409} == {"insufficient_fabric"}
    [after] = (await client.get("/rolls", params={"sku": "TKN-0001"})).json()
    assert after["id"] == roll["id"]
    assert after["available_meters"] == "0.00"


async def test_mixed_reserves_and_cancels_over_several_rolls_do_not_deadlock(
    client: AsyncClient,
) -> None:
    for meters in ("30", "45", "25"):
        await add_roll(client, meters)
    reserved = [await add_order(client, 7, "2") for _ in range(4)]
    for order in reserved:
        assert (await reserve(client, order["id"])).status_code == 200
    fresh = [await add_order(client, 3, "5") for _ in range(6)]

    replies = await asyncio.gather(
        *(cancel(client, order["id"]) for order in reserved),
        *(reserve(client, order["id"]) for order in fresh),
    )

    assert all(r.status_code in (200, 409) for r in replies), [r.text for r in replies]
    assert all(r.status_code == 200 for r in replies[:4])
    reserved_now = sum(15 for r in replies[4:] if r.status_code == 200)
    rolls = (await client.get("/rolls")).json()
    left = sum(float(roll["available_meters"]) for roll in rolls)
    assert left == 100 - reserved_now
    assert all(float(roll["available_meters"]) >= 0 for roll in rolls)
