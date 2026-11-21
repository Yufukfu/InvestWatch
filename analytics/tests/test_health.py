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
