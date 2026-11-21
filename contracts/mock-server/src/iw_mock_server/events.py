"""Socket.IO namespace /events mounted next to the FastAPI app.

Event names and payloads follow contracts/schemas/events.schema.json: the Socket.IO event name is the
event `type` and the payload is the event `data` (integration-plan §6).
"""

from __future__ import annotations

import asyncio
import copy
import itertools
import logging
import uuid
from datetime import datetime, timezone

import socketio

from .app import bumped_timestamp, create_app
from .settings import Settings
from .store import Store, load_mock_data

NAMESPACE = "/events"
log = logging.getLogger("iw_mock_server.events")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def finding_brief(store: Store, finding: dict) -> dict:
    return {"id": finding["id"], "module": finding["module"], "score": finding["score"],
            "risk_level": store.risk_level_of(finding), "title": finding["title"], "url": finding["url"],
            "platform": finding["platform"]}


class EventHub:
    """Emits contract events and runs the replay and scan background work."""

    def __init__(self, sio: socketio.AsyncServer, store: Store, settings: Settings):
        self.sio = sio
        self.store = store  # always read store.findings etc. through the store: reset() replaces them
        self.settings = settings
        self._templates = itertools.cycle(sorted(store.findings))
        self._replay_task: asyncio.Task | None = None
        self._tasks: set[asyncio.Task] = set()
        self.clients: set[str] = set()  # connected sids on /events; replay runs only while non-empty

    def _spawn(self, coro) -> None:
        task = asyncio.get_running_loop().create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def emit(self, event_type: str, data: dict) -> None:
        log.info("emit", extra={"event": event_type})
        await self.sio.emit(event_type, data, namespace=NAMESPACE)

    def notify(self, event_type: str, data: dict) -> None:
        """Fire-and-forget emit from a request handler running on the event loop."""
        self._spawn(self.emit(event_type, data))

    # --- replay ----------------------------------------------------------------------------

    def replay_once(self) -> dict:
        """Add one finding cloned from a mock finding and emit its events. Returns the brief."""
        template_id = next(self._templates)
        template = self.store.findings.get(template_id) or next(iter(self.store.findings.values()))
        finding = copy.deepcopy(template)
        # mock timestamps can lie in the future; a replayed finding must still be the newest
        latest = max((f["detected_at"] for f in self.store.findings.values()), default=None)
        now = bumped_timestamp(latest)
        finding.update(id=str(uuid.uuid4()), status="new", note=None, detected_at=now, updated_at=now)
        self.store.add_finding(finding, limit=self.settings.max_added)

        brief = finding_brief(self.store, finding)
        self.notify("finding.created", brief)
        if brief["risk_level"] == "high":
            self.notify("finding.high_risk", brief)
        return brief

    async def _replay_loop(self) -> None:
        interval = self.settings.replay_interval_s
        while True:
            await asyncio.sleep(interval)
            if not self.clients:
                continue
            try:
                self.replay_once()
            except Exception:  # keep the loop alive; a bad template must not stop alerts
                log.exception("replay failed")

    def ensure_replay(self) -> None:
        if self.settings.replay_interval_s > 0 and (self._replay_task is None or self._replay_task.done()):
            self._replay_task = asyncio.get_running_loop().create_task(self._replay_loop())

    # --- scans -----------------------------------------------------------------------------

    def start_scan(self, source_id: str) -> None:
        source = self.store.sources.get(source_id)
        if source is not None:  # set before the 202 so a reload during the scan already sees it
            source["last_run_status"] = "running"
        # generation is taken now, not inside the task, so a reset before the task starts is noticed too
        self._spawn(self._scan(source_id, self.store.generation))

    async def _scan(self, source_id: str, generation: int) -> None:
        await self.emit("scan.started", {"source_id": source_id, "documents": None, "status": None})
        await asyncio.sleep(self.settings.scan_delay_s)
        documents = sum(1 for d in self.store.documents.values() if d.get("source_id") == source_id)
        source = self.store.sources.get(source_id)
        if source is not None and self.store.generation == generation:  # skip if reset meanwhile
            source.update(last_run_at=_now(), last_run_status="ok", documents_count=documents)
        await self.emit("scan.finished", {"source_id": source_id, "documents": documents, "status": "ok"})


def origin_check(allowed: tuple[str, ...]):
    """Socket.IO origin rule: the listed origins plus same-origin.

    python-socketio checks `Origin` even for same-origin requests, and with an explicit list it drops
    its own same-origin default. Behind the HTTPS gateway the dashboard's origin is the gateway's
    (`https://localhost:8443`), which no static list can know, so same-origin is added back here,
    using the forwarded host and scheme like engineio's default does.
    """
    if "*" in allowed:
        return "*"

    def check(origin: str, environ: dict) -> bool:
        if origin in allowed:
            return True
        host = environ.get("HTTP_X_FORWARDED_HOST", environ.get("HTTP_HOST", "")).split(",")[0].strip()
        scheme = environ.get("HTTP_X_FORWARDED_PROTO", environ.get("wsgi.url_scheme", "http")).split(",")[0].strip()
        return bool(host) and origin == f"{scheme}://{host}"

    return check


def create_asgi_app(settings: Settings | None = None, store: Store | None = None):
    """FastAPI (REST under /api) + Socket.IO (/socket.io, namespace /events) as one ASGI app."""
    settings = settings or Settings()
    store = store or Store(load_mock_data(settings.contracts_dir))
    api = create_app(settings, store)

    sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins=origin_check(settings.cors_origins))
    hub = EventHub(sio, store, settings)
    api.state.notify = hub.notify
    api.state.start_scan = hub.start_scan
    api.state.replay_once = hub.replay_once

    @sio.on("connect", namespace=NAMESPACE)
    async def on_connect(sid, environ, auth=None):
        hub.clients.add(sid)
        hub.ensure_replay()

    @sio.on("disconnect", namespace=NAMESPACE)
    async def on_disconnect(sid, reason=None):
        hub.clients.discard(sid)

    app = socketio.ASGIApp(sio, other_asgi_app=api, socketio_path="socket.io")
    app.hub = hub
    return app
