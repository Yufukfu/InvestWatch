"""/health (document-stream-worker spec, "Observability and graceful stop")."""

from __future__ import annotations

import json
import urllib.error
import urllib.request

import pytest

from investwatch_analytics.health import start_health_server


def get(port: int, path: str = "/health") -> tuple[int, dict | None]:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=3) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as err:
        body = err.read()
        return err.code, (json.loads(body) if body else None)


@pytest.fixture
def serve():
    servers = []

    def _serve(**checks):
        server = start_health_server(0, checks, host="127.0.0.1")
        servers.append(server)
        return server.server_address[1]

    yield _serve
    for s in servers:
        s.shutdown()
        s.server_close()


def test_both_up(serve):
    port = serve(redis=lambda: True, db=lambda: True)
    assert get(port) == (200, {"status": "ok", "redis": True, "db": True})


def test_db_down(serve):
    port = serve(redis=lambda: True, db=lambda: False)
    assert get(port) == (503, {"status": "degraded", "redis": True, "db": False})


def test_redis_down(serve):
    port = serve(redis=lambda: False, db=lambda: True)
    assert get(port) == (503, {"status": "degraded", "redis": False, "db": True})


def test_a_raising_check_counts_as_down(serve):
    def boom():
        raise RuntimeError("password=hunter2")  # never echoed

    port = serve(redis=boom, db=lambda: True)
    status, body = get(port)
    assert (status, body["redis"]) == (503, False)
    assert "hunter2" not in json.dumps(body)


def test_other_paths_are_404(serve):
    port = serve(redis=lambda: True, db=lambda: True)
    assert get(port, "/")[0] == 404
    assert get(port, "/health/x")[0] == 404


def test_db_check_never_leaks_connections(serve, monkeypatch):
    """Each /health request runs on a new thread; the db check must not keep a connection per thread."""
    import psycopg

    from investwatch_analytics.storage import PostgresStore

    opened: list = []

    class FakeConn:
        closed = False

        def __init__(self) -> None:
            opened.append(self)

        def execute(self, *a, **k):
            return self

        def fetchone(self):
            return (1,)

        def close(self) -> None:
            self.closed = True

        def __enter__(self):
            return self

        def __exit__(self, *exc) -> None:
            self.close()

    monkeypatch.setattr(psycopg, "connect", lambda *a, **k: FakeConn())
    store = PostgresStore("postgresql://u@127.0.0.1:1/db")
    port = serve(redis=lambda: True, db=store.ping)
    for _ in range(20):
        assert get(port)[0] == 200
    assert len(opened) == 20 and all(c.closed for c in opened)
    assert store._all == []


def test_db_check_false_when_unreachable():
    from investwatch_analytics.storage import PostgresStore

    assert PostgresStore("postgresql://u@127.0.0.1:1/db", connect_timeout=1).ping() is False


def test_idle_client_is_dropped(serve):
    import socket
    import time

    port = serve(redis=lambda: True, db=lambda: True)
    with socket.create_connection(("127.0.0.1", port)) as idle:  # connects and never sends a request
        idle.settimeout(10)
        started = time.monotonic()
        assert idle.recv(1) == b""  # the server closes it
        assert time.monotonic() - started < 6
    assert get(port)[0] == 200  # still serving
