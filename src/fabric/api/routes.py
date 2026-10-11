import hashlib
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import JSONResponse

from fabric.api.schemas import ErrorOut, OrderIn, OrderOut, RollIn, RollOut
from fabric.inventory.application import use_cases
from fabric.inventory.application.idempotency import run_once
from fabric.inventory.application.ports import IdempotentRequest, Reply, UnitOfWork
from fabric.inventory.domain.values import FabricSku, Meters
from fabric.inventory.infrastructure.db import database_is_up

ERRORS: dict[int | str, dict[str, Any]] = {code: {"model": ErrorOut} for code in (404, 409, 422)}

router = APIRouter(responses=ERRORS)


def unit_of_work(request: Request) -> UnitOfWork:
    uow: UnitOfWork = request.app.state.uow_factory()
    return uow


async def idempotent_request(
    request: Request,
    key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)],
) -> IdempotentRequest:
    body_hash = hashlib.sha256(await request.body()).hexdigest()
    return IdempotentRequest(key, f"{request.method} {request.url.path}", body_hash)


Uow = Annotated[UnitOfWork, Depends(unit_of_work)]
Idempotent = Annotated[IdempotentRequest, Depends(idempotent_request)]


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


@router.post("/orders/{order_id}/reserve", response_model=OrderOut)
async def reserve_order(order_id: UUID, uow: Uow, request: Idempotent) -> JSONResponse:
    async def reserve(uow: UnitOfWork) -> Reply:
        order = await use_cases.reserve_order(uow, order_id)
        return Reply(200, OrderOut.of(order).model_dump(mode="json"))

    reply = await run_once(uow, request, reserve)
    return JSONResponse(reply.body, status_code=reply.status)


@router.post("/orders/{order_id}/cancel", response_model=OrderOut)
async def cancel_order(order_id: UUID, uow: Uow, request: Idempotent) -> JSONResponse:
    async def cancel(uow: UnitOfWork) -> Reply:
        order = await use_cases.cancel_order(uow, order_id)
        return Reply(200, OrderOut.of(order).model_dump(mode="json"))

    reply = await run_once(uow, request, cancel)
    return JSONResponse(reply.body, status_code=reply.status)


@router.get("/health")
async def health(request: Request) -> JSONResponse:
    if not await database_is_up(request.app.state.engine):
        return JSONResponse(
            {"error": "database_unavailable", "detail": "can not reach postgres"}, status_code=503
        )
    return JSONResponse({"status": "ok"})
