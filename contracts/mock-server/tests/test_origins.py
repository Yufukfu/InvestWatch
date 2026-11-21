"""Socket.IO origin check: listed origins, `*`, and same-origin (dashboard behind the HTTPS gateway)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from iw_mock_server.events import create_asgi_app
from iw_mock_server.settings import Settings

HANDSHAKE = "/socket.io/?EIO=4&transport=polling"
GATEWAY = {"Host": "localhost:8443", "X-Forwarded-Proto": "https"}  # what Caddy forwards to the upstream


def handshake(contracts_dir, origins: tuple[str, ...], headers: dict) -> int:
    settings = Settings(contracts_dir=contracts_dir, replay_interval_s=0, cors_origins=origins)
    with TestClient(create_asgi_app(settings)) as client:
        return client.get(HANDSHAKE, headers=headers).status_code


DEFAULTS = ("http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173")


@pytest.mark.parametrize(("origins", "headers", "expected"), [
    (DEFAULTS, {**GATEWAY, "Origin": "https://localhost:8443"}, 200),  # same origin through the gateway
    (DEFAULTS, {"Host": "localhost:8000", "Origin": "http://localhost:8000"}, 200),  # same origin, direct
    (DEFAULTS, {"Origin": "http://localhost:5173"}, 200),  # listed
    (DEFAULTS, {**GATEWAY, "Origin": "https://evil.example"}, 400),  # neither listed nor same origin
    (DEFAULTS, {**GATEWAY, "Origin": "http://localhost:8443"}, 400),  # same host, wrong scheme
    (("*",), {"Origin": "https://anything.example"}, 200),
])
def test_socketio_origin_check(contracts_dir, origins, headers, expected):
    assert handshake(contracts_dir, origins, headers) == expected


def test_same_origin_uses_the_forwarded_scheme_and_host():
    # uvicorn in a container does not trust Caddy's address, so the scope scheme stays http and
    # only the forwarded headers say the browser used https
    from iw_mock_server.events import origin_check

    check = origin_check(DEFAULTS)
    environ = {"wsgi.url_scheme": "http", "HTTP_HOST": "mock-api:8000",
               "HTTP_X_FORWARDED_PROTO": "https", "HTTP_X_FORWARDED_HOST": "localhost:8443"}

    assert check("https://localhost:8443", environ) is True
    assert check("http://mock-api:8000", environ) is False
