"""Relay Redis Pub/Sub iw:events -> Socket.IO namespace /events (integration-plan §6, specs/event-relay).

Messages pass through unchanged: the Socket.IO event name is the message `type`, the payload is `data`. No
threshold logic here (ADR 0305). Messages that are not JSON or fail contracts/schemas/events.schema.json
(definition `event`) are dropped with a warning.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from pathlib import Path

import socketio
from jsonschema import Draft202012Validator, FormatChecker

CHANNEL = "iw:events"
NAMESPACE = "/events"
BACKOFF_START_S = 0.5
BACKOFF_MAX_S = 10.0

log = logging.getLogger("investwatch_api.events")


def event_validator(contracts_dir: Path) -> Draft202012Validator:
    """Validator for the `event` definition only (not stream messages); fails fast if the schema is missing."""
    schema = json.loads((contracts_dir / "schemas" / "events.schema.json").read_text(encoding="utf-8"))
    schema.pop("oneOf", None)
    schema["$ref"] = "#/$defs/event"
    return Draft202012Validator(schema, format_checker=FormatChecker())


def create_sio(cors_origins: tuple[str, ...]) -> socketio.AsyncServer:
    # None = same origin only (the gateway case; engineio also accepts X-Forwarded-Proto/-Host). An explicit
    # CORS_ORIGINS list REPLACES that default, so it must also name the dashboard's own origin.
    sio = socketio.AsyncServer(async_mode="asgi", namespaces=[NAMESPACE],
                               cors_allowed_origins=list(cors_origins) if cors_origins else None)

    @sio.on("connect", namespace=NAMESPACE)
    async def connect(sid, environ, auth=None):
        log.info("client connected", extra={"event": "connect"})

    return sio


class Relay:
    def __init__(self, sio: socketio.AsyncServer, redis, validator: Draft202012Validator, services):
        self._sio, self._redis, self._validator, self._services = sio, redis, validator, services
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        self._task = asyncio.get_running_loop().create_task(self._run())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task

    def parse(self, raw) -> dict | None:
        """The event to emit, or None (logged) for anything that is not a contract event."""
        try:
            message = json.loads(raw)
        except (TypeError, ValueError):
            log.warning("dropped event", extra={"reason": "not_json"})
            return None
        error = next(iter(self._validator.iter_errors(message)), None)
        if error is not None:
            kind = message.get("type") if isinstance(message, dict) else None
            log.warning("dropped event", extra={"reason": "schema", "event": str(kind)[:64]})
            return None
        return message

    async def _run(self) -> None:
        backoff = BACKOFF_START_S
        while True:
            pubsub = None
            try:
                pubsub = self._redis.pubsub()
                await pubsub.subscribe(CHANNEL)
                self._services.redis_connected = True
                backoff = BACKOFF_START_S
                log.info("relay subscribed", extra={"event": CHANNEL})
                while True:
                    message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                    if message is None or message.get("type") != "message":
                        continue
                    event = self.parse(message["data"])
                    if event is not None:
                        await self._emit(event)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._services.redis_connected = False
                log.warning("relay lost Redis, retrying", extra={"reason": type(exc).__name__})
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, BACKOFF_MAX_S)
            finally:
                if pubsub is not None:
                    with contextlib.suppress(Exception):
                        await pubsub.aclose()

    async def _emit(self, event: dict) -> None:
        """A Socket.IO failure drops this one event; it is not a Redis outage and must not resubscribe."""
        try:
            await self._sio.emit(event["type"], event["data"], namespace=NAMESPACE)
        except Exception as exc:
            log.error("emit failed", extra={"reason": type(exc).__name__, "event": event["type"]})
