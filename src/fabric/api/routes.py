from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from fabric.api.schemas import ErrorOut, OrderIn, OrderOut, RollIn, RollOut
from fabric.inventory.application import use_cases
from fabric.inventory.application.ports import UnitOfWork
from fabric.inventory.domain.values import FabricSku, Meters
from fabric.inventory.infrastructure.db import database_is_up

ERRORS: dict[int | str, dict[str, Any]] = {code: {"model": ErrorOut} for code in (404, 409, 422)}

router = APIRouter(responses=ERRORS)


def unit_of_work(request: Request) -> UnitOfWork:
    uow: UnitOfWork = request.app.state.uow_factory()
    return uow


Uow = Annotated[UnitOfWork, Depends(unit_of_work)]


@router.post("/rolls", status_code=201)
async def receive_roll(body: RollIn, uow: Uow) -> RollOut:
    async with uow:
        roll = await use_cases.receive_roll(uow, FabricSku(body.sku), Meters(body.total_meters))
        await uow.commit()
    return RollOut.of(roll)


@router.get("/rolls")
async def list_rolls(uow: Uow, sku: str | None = None) -> list[RollOut]:
    async with uow:
        rolls = await use_cases.list_rolls(uow, FabricSku(sku) if sku else None)
    return [RollOut.of(roll) for roll in rolls]


@router.post("/orders", status_code=201)
async def draft_order(body: OrderIn, uow: Uow) -> OrderOut:
    async with uow:
        order = await use_cases.draft_order(
            uow, FabricSku(body.sku), body.quantity, Meters(body.consumption_per_unit)
        )
        await uow.commit()
    return OrderOut.of(order)


@router.get("/orders/{order_id}")
async def get_order(order_id: UUID, uow: Uow) -> OrderOut:
    async with uow:
        return OrderOut.of(await use_cases.get_order(uow, order_id))


@router.post("/orders/{order_id}/reserve")
async def reserve_order(order_id: UUID, uow: Uow) -> OrderOut:
    async with uow:
        order = await use_cases.reserve_order(uow, order_id)
        await uow.commit()
    return OrderOut.of(order)


@router.post("/orders/{order_id}/cancel")
async def cancel_order(order_id: UUID, uow: Uow) -> OrderOut:
    async with uow:
        order = await use_cases.cancel_order(uow, order_id)
        await uow.commit()
    return OrderOut.of(order)


@router.get("/health")
async def health(request: Request) -> JSONResponse:
    if not await database_is_up(request.app.state.engine):
        return JSONResponse(
            {"error": "database_unavailable", "detail": "can not reach postgres"}, status_code=503
        )
    return JSONResponse({"status": "ok"})
