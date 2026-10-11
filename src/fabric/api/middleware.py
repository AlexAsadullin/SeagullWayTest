import logging
import time
from collections.abc import Awaitable, Callable
from uuid import uuid4

from fastapi import Request, Response

from fabric.logs import request_id

logger = logging.getLogger("fabric.api")


async def request_context(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    incoming = request.headers.get("X-Request-ID", "")
    current = incoming if 0 < len(incoming) <= 64 else uuid4().hex
    token = request_id.set(current)
    started = time.perf_counter()
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = current
        logger.info(
            "request",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": round((time.perf_counter() - started) * 1000, 1),
            },
        )
        return response
    except Exception:
        logger.exception(
            "request failed", extra={"method": request.method, "path": request.url.path}
        )
        raise
    finally:
        request_id.reset(token)
