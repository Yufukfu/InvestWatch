"""ASGI app: FastAPI routes under /api (contracts/openapi.yaml) plus Socket.IO namespace /events.

Every route is `async def` (api-v1 design decision 1). Dependencies live in one `Services` object built in the
lifespan, so tests can inject their own database, Redis and object store.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from . import errors, settings
from .objectstore import MinioStore, ObjectStore
from .thresholds import ThresholdStore

log = logging.getLogger("investwatch_api")
HEALTH_TIMEOUT_S = 2.0


@dataclass
class Services:
    engine: AsyncEngine
    redis: object  # redis.asyncio.Redis
    objects: ObjectStore
    thresholds: ThresholdStore = field(init=False)
    redis_connected: bool = False  # kept up to date by the event relay

    def __post_init__(self):
        self.thresholds = ThresholdStore(self.redis)

    async def close(self) -> None:
        await self.engine.dispose()
        with contextlib.suppress(Exception):
            await self.redis.aclose()


def services_from_env() -> Services:
    from redis.asyncio import Redis

    return Services(
        engine=create_async_engine(settings.app_database_url(), pool_pre_ping=True),
        redis=Redis.from_url(settings.redis_url(), socket_connect_timeout=2, socket_timeout=5,
                             health_check_interval=30),
        objects=MinioStore(**settings.minio_settings()),
    )


ServicesFactory = Callable[[], Services]


async def _check(probe: Callable[[], Awaitable[object]]) -> str:
    try:
        result = await asyncio.wait_for(probe(), HEALTH_TIMEOUT_S)
    except Exception:
        return "down"
    return "down" if result is False else "ok"


def create_app(services_factory: ServicesFactory = services_from_env) -> FastAPI:
    from .events import Relay, create_sio, event_validator

    origins = settings.cors_origins()
    validator = event_validator(settings.contracts_dir())  # fails fast if contracts/ is missing
    sio = create_sio(origins)

    @contextlib.asynccontextmanager
    async def lifespan(api: FastAPI):
        services = services_factory()
        api.state.services = services
        relay = Relay(sio, services.redis, validator, services)
        relay.start()
        try:
            yield
        finally:
            await relay.stop()
            await services.close()

    api = FastAPI(title="InvestWatch API", version="1.2.0", lifespan=lifespan)
    api.state.sio = sio
    errors.install(api)
    if origins:
        api.add_middleware(CORSMiddleware, allow_origins=list(origins), allow_methods=["*"], allow_headers=["*"])

    @api.get("/api/health")
    async def health(request: Request):
        svc: Services = request.app.state.services

        async def db():
            async with svc.engine.connect() as conn:
                await conn.execute(text("SELECT 1"))

        postgres, redis, minio = await asyncio.gather(_check(db), _check(svc.redis.ping), _check(svc.objects.ping))
        services = {"api": "ok", "postgres": postgres, "redis": redis, "minio": minio}
        status = "down" if postgres == "down" else ("degraded" if "down" in (redis, minio) else "ok")
        return {"status": status, "services": services}

    from .routes import register

    register(api)
    return api


def create_asgi(services_factory: ServicesFactory = services_from_env):
    """FastAPI under /api plus Socket.IO on /socket.io (namespace /events), one ASGI app on port 8000."""
    import socketio

    api = create_app(services_factory)
    return socketio.ASGIApp(api.state.sio, other_asgi_app=api, socketio_path="socket.io")
