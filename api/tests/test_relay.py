"""Requirements of specs/event-relay: iw:events -> Socket.IO /events, run against a live uvicorn server."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import threading
import time
import uuid
from contextlib import contextmanager
from urllib.parse import urlparse

import httpx
import pytest
import redis as redis_sync
import socketio
import uvicorn

from apiutil import FakeObjectStore, make_services
from conftest import assert_contract_valid
from dbutil import document_row, finding_row
from investwatch_api.app import create_asgi


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@contextmanager
def live_server(db_url: str, redis_url: str):
    port = _free_port()
    config = uvicorn.Config(create_asgi(lambda: make_services(db_url, redis_url, FakeObjectStore())),
                            host="127.0.0.1", port=port, log_level="warning", loop="none", lifespan="on")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started:
        assert time.monotonic() < deadline, "server did not start"
        time.sleep(0.05)
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(10)


class Listener:
    """A Socket.IO client on /events that records every event in order."""

    EVENTS = ("finding.created", "finding.high_risk", "finding.updated", "scan.started", "scan.finished")

    def __init__(self, base: str, origin: str | None = None, headers: dict | None = None):
        self.received: list[tuple[str, dict]] = []
        self._cond = threading.Condition()
        self.sio = socketio.Client(reconnection=False)
        for name in self.EVENTS:
            self.sio.on(name, namespace="/events", handler=self._handler(name))
        if origin is None:  # websocket-client sends Origin = the server's own origin
            self.sio.connect(base, namespaces=["/events"], transports=["websocket"], wait_timeout=5)
        else:  # polling sends exactly the Origin header given here
            self.sio.connect(base, namespaces=["/events"], transports=["polling"],
                             headers={"Origin": origin, **(headers or {})}, wait_timeout=5)

    def _handler(self, name):
        def handle(data):
            with self._cond:
                self.received.append((name, data))
                self._cond.notify_all()
        return handle

    def wait_for(self, count: int, timeout: float = 5.0) -> list[tuple[str, dict]]:
        with self._cond:
            self._cond.wait_for(lambda: len(self.received) >= count, timeout)
            return list(self.received)

    def close(self):
        self.sio.disconnect()


def _event(kind: str, data: dict) -> str:
    return json.dumps({"type": kind, "emitted_at": "2026-11-21T16:00:00Z", "data": data})


def _brief(**over) -> dict:
    brief = {"id": str(uuid.uuid4()), "module": "M2", "score": 0.91, "title": "Brak ostrzeżenia",
             "url": "https://alfa.example/", "platform": "web"}
    brief.update(over)
    return brief


@pytest.fixture
def server(migrated_db, app_engine, redis_clean):
    with live_server(migrated_db.app_url, redis_clean) as base:
        yield base


@pytest.fixture
def publisher(redis_clean):
    client = redis_sync.Redis.from_url(redis_clean)
    yield client
    client.close()


@pytest.fixture
def listener(server):
    lst = Listener(server)
    time.sleep(0.3)  # let the relay subscribe
    yield lst
    lst.close()


def test_finding_created_is_relayed_unchanged(listener, publisher):
    brief = _brief()
    assert_contract_valid("events", json.loads(_event("finding.created", brief)))
    publisher.publish("iw:events", _event("finding.created", brief))
    assert listener.wait_for(1) == [("finding.created", brief)]


def test_high_risk_passes_through_without_threshold_check(listener, publisher):
    low = _brief(score=0.01)  # below every threshold: the relay does not re-check (ADR 0305)
    publisher.publish("iw:events", _event("finding.high_risk", low))
    assert listener.wait_for(1) == [("finding.high_risk", low)]


def test_scan_progress_keeps_order(listener, publisher):
    src = str(uuid.uuid4())
    publisher.publish("iw:events", _event("scan.started", {"source_id": src}))
    publisher.publish("iw:events", _event("scan.finished", {"source_id": src, "documents": 3, "status": "ok"}))
    assert [k for k, _ in listener.wait_for(2)] == ["scan.started", "scan.finished"]


@pytest.mark.parametrize("bad", [
    "hello",
    json.dumps({"type": "finding.deleted", "emitted_at": "2026-11-21T16:00:00Z", "data": {}}),
    json.dumps({"type": "finding.updated", "emitted_at": "2026-11-21T16:00:00Z", "data": {"id": str(uuid.uuid4())}}),
    json.dumps({"document_id": str(uuid.uuid4()), "schema": "v1"}),
])
def test_invalid_messages_are_dropped_and_relay_continues(listener, publisher, bad):
    publisher.publish("iw:events", bad)
    good = _brief()
    publisher.publish("iw:events", _event("finding.created", good))
    assert listener.wait_for(1) == [("finding.created", good)]
    time.sleep(0.3)
    assert listener.received == [("finding.created", good)]


def test_no_client_connected(server, publisher):
    publisher.publish("iw:events", _event("finding.created", _brief()))  # nobody listens: dropped
    lst = Listener(server)
    try:
        time.sleep(0.3)
        later = _brief()
        publisher.publish("iw:events", _event("finding.created", later))
        assert lst.wait_for(1) == [("finding.created", later)]
    finally:
        lst.close()


def test_status_change_reaches_another_tab(server, migrated_db, listener):
    from sqlalchemy import create_engine, insert

    from investwatch_api.db.tables import documents, findings

    doc = document_row()
    f = finding_row(doc["id"])
    engine = create_engine(migrated_db.app_url)
    with engine.begin() as conn:
        conn.execute(insert(documents).values(doc))
        conn.execute(insert(findings).values(f))
    engine.dispose()
    r = httpx.patch(f"{server}/api/findings/{f['id']}", json={"status": "in_review"})
    assert r.status_code == 200
    assert listener.wait_for(1) == [("finding.updated", {"id": str(f["id"]), "status": "in_review"})]


def test_same_origin_connection(server):
    lst = Listener(server)
    assert lst.sio.connected
    lst.close()


def test_foreign_origin_rejected(server):
    with pytest.raises(socketio.exceptions.ConnectionError):
        Listener(server, origin="http://evil.example")


GATEWAY = {"Host": "localhost:8443", "X-Forwarded-Proto": "https"}  # what Caddy forwards to api:8000


def test_gateway_https_origin_is_accepted(server):
    lst = Listener(server, origin="https://localhost:8443", headers=GATEWAY)
    assert lst.sio.connected
    lst.close()


def test_foreign_origin_behind_the_gateway_is_rejected(server):
    with pytest.raises(socketio.exceptions.ConnectionError):
        Listener(server, origin="https://evil.example", headers=GATEWAY)


def test_emit_failure_does_not_resubscribe(listener, publisher, server):
    import asyncio

    from investwatch_api.events import NAMESPACE, Relay

    class BrokenSio:
        async def emit(self, *a, **kw):
            raise RuntimeError("boom")

    class Svc:
        redis_connected = True

    relay = Relay(BrokenSio(), None, None, Svc())
    asyncio.run(relay._emit({"type": "finding.created", "data": {}}))  # logged, not raised
    assert Svc.redis_connected is True and NAMESPACE == "/events"


def test_explicit_same_origin_over_polling_is_accepted(server):
    lst = Listener(server, origin=server)
    assert lst.sio.connected
    lst.close()


# --- Redis outages ---------------------------------------------------------------------------

class TcpProxy:
    """127.0.0.1:<port> -> Redis; `cut()` drops every connection and refuses new ones until `restore()`."""

    def __init__(self, target_host: str, target_port: int):
        self.target = (target_host, target_port)
        self.port = _free_port()
        self.enabled = True
        self._conns: list[socket.socket] = []
        self._lock = threading.Lock()
        self._server = socket.create_server(("127.0.0.1", self.port))
        threading.Thread(target=self._accept, daemon=True).start()

    def _accept(self):
        while True:
            try:
                client, _ = self._server.accept()
            except OSError:
                return
            if not self.enabled:
                client.close()
                continue
            try:
                upstream = socket.create_connection(self.target, timeout=2)
            except OSError:
                client.close()
                continue
            with self._lock:
                self._conns += [client, upstream]
            for a, b in ((client, upstream), (upstream, client)):
                threading.Thread(target=self._pipe, args=(a, b), daemon=True).start()

    @staticmethod
    def _pipe(a, b):
        try:
            while data := a.recv(65536):
                b.sendall(data)
        except OSError:
            pass
        finally:
            for s in (a, b):
                try:
                    s.close()
                except OSError:
                    pass

    def cut(self):
        self.enabled = False
        with self._lock:
            for s in self._conns:
                try:
                    s.shutdown(socket.SHUT_RDWR)
                    s.close()
                except OSError:
                    pass
            self._conns.clear()

    def restore(self):
        self.enabled = True

    def close(self):
        self.cut()
        self._server.close()


def _proxied(redis_url: str, proxy: TcpProxy) -> str:
    u = urlparse(redis_url)
    return u._replace(netloc=f"{u.netloc.rsplit('@', 1)[0]}@127.0.0.1:{proxy.port}").geturl()


@pytest.fixture
def proxy(redis_clean):
    u = urlparse(redis_clean)
    p = TcpProxy(u.hostname, u.port)
    yield p
    p.close()


def _health_redis(base):
    return httpx.get(f"{base}/api/health", timeout=10).json()["services"]["redis"]


def _publish_until_received(publisher, lst, kind, data, timeout=20.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        publisher.publish("iw:events", _event(kind, data))
        if lst.wait_for(1, timeout=0.5):
            return lst.received
    return lst.received


def test_redis_outage_and_recovery(migrated_db, app_engine, redis_clean, proxy, publisher):
    with live_server(migrated_db.app_url, _proxied(redis_clean, proxy)) as base:
        lst = Listener(base)
        try:
            time.sleep(0.3)
            proxy.cut()
            assert _health_redis(base) == "down"
            assert lst.sio.connected  # Socket.IO clients stay connected
            proxy.restore()
            after = _brief()
            got = _publish_until_received(publisher, lst, "finding.created", after)
            assert got and got[0] == ("finding.created", after)
            assert _health_redis(base) == "ok"
        finally:
            lst.close()


def test_redis_down_at_start_up(migrated_db, app_engine, redis_clean, proxy, publisher):
    proxy.cut()
    with live_server(migrated_db.app_url, _proxied(redis_clean, proxy)) as base:
        assert httpx.get(f"{base}/api/health", timeout=10).json()["services"]["redis"] == "down"
        assert httpx.get(f"{base}/api/findings", timeout=10).status_code == 200  # no Redis needed
        lst = Listener(base)
        try:
            proxy.restore()
            got = _publish_until_received(publisher, lst, "finding.created", _brief())
            assert got, "relay never started delivering after Redis came back"
        finally:
            lst.close()
