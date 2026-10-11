from uuid import uuid4

from httpx import ASGITransport, AsyncClient

from fabric.main import create_app
from tests.integration.api_helpers import add_order, add_roll, cancel, reserve


async def test_roll_is_created_with_full_length_available(client: AsyncClient) -> None:
    roll = await add_roll(client, "120.5")

    assert roll["sku"] == "TKN-0001"
    assert roll["total_meters"] == "120.50"
    assert roll["available_meters"] == "120.50"


async def test_reserve_then_cancel_moves_fabric_back_and_forth(client: AsyncClient) -> None:
    await add_roll(client, "100")
    await add_roll(client, "250")
    order = await add_order(client, 200, "1.4")
    assert order["status"] == "draft"
    assert order["required_meters"] == "280.00"

    reserved = await reserve(client, order["id"])
    assert reserved.status_code == 200
    assert reserved.json()["status"] == "reserved"
    assert sorted(line["meters"] for line in reserved.json()["lines"]) == ["100.00", "180.00"]

    rolls = (await client.get("/rolls", params={"sku": "TKN-0001"})).json()
    assert sorted(roll["available_meters"] for roll in rolls) == ["0.00", "70.00"]

    cancelled = await cancel(client, order["id"])
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    rolls = (await client.get("/rolls", params={"sku": "TKN-0001"})).json()
    assert sorted(roll["available_meters"] for roll in rolls) == ["100.00", "250.00"]

    fetched = await client.get(f"/orders/{order['id']}")
    assert fetched.json() == cancelled.json()


async def test_not_enough_fabric_is_conflict(client: AsyncClient) -> None:
    await add_roll(client, "100")
    order = await add_order(client, 200, "1.4")

    response = await reserve(client, order["id"])

    assert response.status_code == 409
    assert response.json()["error"] == "insufficient_fabric"
    assert (await client.get(f"/orders/{order['id']}")).json()["status"] == "draft"


async def test_other_sku_rolls_are_not_used(client: AsyncClient) -> None:
    await add_roll(client, "500", sku="DNM-0001")
    order = await add_order(client, 10, "1")

    response = await reserve(client, order["id"])

    assert response.status_code == 409


async def test_reserving_twice_is_conflict(client: AsyncClient) -> None:
    await add_roll(client, "100")
    order = await add_order(client, 10, "1")
    await reserve(client, order["id"])

    response = await reserve(client, order["id"])

    assert response.status_code == 409
    assert response.json()["error"] == "invalid_order_status"


async def test_draft_can_not_be_cancelled(client: AsyncClient) -> None:
    order = await add_order(client, 10, "1")

    response = await cancel(client, order["id"])

    assert response.status_code == 409
    assert response.json()["error"] == "invalid_order_status"


async def test_unknown_order_is_404(client: AsyncClient) -> None:
    response = await client.get(f"/orders/{uuid4()}")

    assert response.status_code == 404
    assert response.json()["error"] == "order_not_found"


async def test_unknown_path_has_same_error_shape(client: AsyncClient) -> None:
    response = await client.get("/nowhere")

    assert response.status_code == 404
    assert set(response.json()) == {"error", "detail"}


async def test_bad_sku_is_validation_error(client: AsyncClient) -> None:
    response = await client.post("/rolls", json={"sku": "tkn-1", "total_meters": "10"})

    assert response.status_code == 422
    assert response.json()["error"] == "invalid_sku"


async def test_bad_numbers_are_validation_error(client: AsyncClient) -> None:
    negative = await client.post("/rolls", json={"sku": "TKN-0001", "total_meters": "-1"})
    too_precise = await client.post(
        "/orders", json={"sku": "TKN-0001", "quantity": 10, "consumption_per_unit": "1.405"}
    )
    zero_quantity = await client.post(
        "/orders", json={"sku": "TKN-0001", "quantity": 0, "consumption_per_unit": "1"}
    )

    for response in (negative, too_precise, zero_quantity):
        assert response.status_code == 422
        assert response.json()["error"] == "validation_error"


async def test_health_checks_database(client: AsyncClient) -> None:
    response = await client.get("/health")

    assert response.status_code == 200


async def test_health_without_database_is_503() -> None:
    app = create_app("postgresql+asyncpg://nobody:nothing@127.0.0.1:1/void")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 503
    assert response.json()["error"] == "database_unavailable"
