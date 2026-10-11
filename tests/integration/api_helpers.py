from typing import Any
from uuid import uuid4

from httpx import AsyncClient, Response


async def add_roll(client: AsyncClient, meters: str, sku: str = "TKN-0001") -> dict[str, Any]:
    response = await client.post("/rolls", json={"sku": sku, "total_meters": meters})
    assert response.status_code == 201, response.text
    roll: dict[str, Any] = response.json()
    return roll


async def add_order(
    client: AsyncClient, quantity: int, per_unit: str, sku: str = "TKN-0001"
) -> dict[str, Any]:
    response = await client.post(
        "/orders", json={"sku": sku, "quantity": quantity, "consumption_per_unit": per_unit}
    )
    assert response.status_code == 201, response.text
    order: dict[str, Any] = response.json()
    return order


async def reserve(client: AsyncClient, order_id: str, key: str | None = None) -> Response:
    headers = {"Idempotency-Key": key or str(uuid4())}
    return await client.post(f"/orders/{order_id}/reserve", headers=headers)


async def cancel(client: AsyncClient, order_id: str, key: str | None = None) -> Response:
    headers = {"Idempotency-Key": key or str(uuid4())}
    return await client.post(f"/orders/{order_id}/cancel", headers=headers)
