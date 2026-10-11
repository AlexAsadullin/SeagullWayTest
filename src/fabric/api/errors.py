from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from fabric.inventory.application.errors import (
    ApplicationError,
    IdempotencyKeyConflict,
    OrderNotFound,
)
from fabric.inventory.domain.errors import DomainError, InvalidValue

APPLICATION_STATUS: dict[type[ApplicationError], int] = {
    OrderNotFound: 404,
    IdempotencyKeyConflict: 409,
}


def error_response(status: int, error: str, detail: str) -> JSONResponse:
    return JSONResponse({"error": error, "detail": detail}, status_code=status)


async def on_domain_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, DomainError)
    # Bad sku or meters reach the domain only through the request body, so it is a client typo.
    status = 422 if isinstance(exc, InvalidValue) else 409
    return error_response(status, exc.code, exc.detail)


async def on_application_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, ApplicationError)
    return error_response(APPLICATION_STATUS.get(type(exc), 409), exc.code, exc.detail)


async def on_validation_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    detail = "; ".join(
        f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}" for error in exc.errors()
    )
    return error_response(422, "validation_error", detail)


async def on_http_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, HTTPException)
    error = "not_found" if exc.status_code == 404 else "http_error"
    return error_response(exc.status_code, error, str(exc.detail))


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(DomainError, on_domain_error)
    app.add_exception_handler(ApplicationError, on_application_error)
    app.add_exception_handler(RequestValidationError, on_validation_error)
    app.add_exception_handler(HTTPException, on_http_error)
