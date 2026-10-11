from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from fabric.api.errors import install_error_handlers
from fabric.api.middleware import request_context
from fabric.api.routes import router
from fabric.inventory.infrastructure.db import database_url, make_engine, make_session_factory
from fabric.inventory.infrastructure.unit_of_work import SqlAlchemyUnitOfWork
from fabric.logs import configure_logging


def create_app(url: str | None = None) -> FastAPI:
    engine = make_engine(url or database_url())
    sessions = make_session_factory(engine)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        await engine.dispose()

    app = FastAPI(title="fabric reservations", lifespan=lifespan)
    app.state.engine = engine
    app.state.uow_factory = lambda: SqlAlchemyUnitOfWork(sessions)
    app.middleware("http")(request_context)
    install_error_handlers(app)
    app.include_router(router)
    return app


configure_logging()
app = create_app()
