from collections.abc import Awaitable, Callable

from fabric.inventory.application.ports import IdempotentRequest, Reply, UnitOfWork


async def run_once(
    uow: UnitOfWork, request: IdempotentRequest, command: Callable[[UnitOfWork], Awaitable[Reply]]
) -> Reply:
    async with uow:
        stored = await uow.idempotency_keys.claim(request)
        if stored is not None:
            return stored
        reply = await command(uow)
        await uow.idempotency_keys.complete(request, reply)
        await uow.commit()
        return reply
