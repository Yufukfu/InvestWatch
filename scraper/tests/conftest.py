"""Shared test fixtures: a local HTTP stub server that records what it receives."""

import threading
import time
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest


@dataclass
class Route:
    status: int = 200
    body: bytes = b""
    headers: dict[str, str] = field(default_factory=dict)
    delay: float = 0.0


@dataclass(frozen=True)
class Received:
    path: str
    headers: tuple[tuple[str, str], ...]  # in wire order
    connect: bool  # True for a CONNECT request: the client is using this server as its proxy


class Stub:
    """Routes are set per test; every request is logged."""

    def __init__(self) -> None:
        self.routes: dict[str, Route] = {}
        self.requests: list[Received] = []
        self.connect_status = 200  # what a CONNECT gets; 407 plays a proxy that refuses our credentials
        stub = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"  # keep-alive, so a tunnelled request follows a CONNECT

            def log_message(self, *args) -> None:  # silence the default stderr log
                pass

            def do_CONNECT(self) -> None:
                stub.requests.append(Received(self.path, tuple(self.headers.items()), True))
                if stub.connect_status != 200:
                    self.send_response(stub.connect_status)
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                self.send_response(200, "Connection established")
                self.end_headers()  # the next request on this socket is the tunnelled one

            def do_GET(self) -> None:
                stub.requests.append(Received(self.path, tuple(self.headers.items()), False))
                route = stub.routes.get(self.path, Route(status=404, body=b"not found"))
                time.sleep(route.delay)
                try:
                    self.send_response(route.status)
                    for name, value in route.headers.items():
                        self.send_header(name, value)
                    self.send_header("Content-Length", str(len(route.body)))
                    self.end_headers()
                    self.wfile.write(route.body)
                except (BrokenPipeError, ConnectionResetError):  # the client gave up (timeout test)
                    pass

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._server.daemon_threads = True
        self.port = self._server.server_address[1]
        threading.Thread(target=self._server.serve_forever, daemon=True).start()

    def route(
        self,
        path: str,
        *,
        status: int = 200,
        body: bytes = b"",
        content_type: str | None = "text/html; charset=utf-8",
        headers: dict[str, str] | None = None,
        delay: float = 0.0,
    ) -> None:
        all_headers = dict(headers or {})
        if content_type is not None:
            all_headers["Content-Type"] = content_type
        self.routes[path] = Route(status=status, body=body, headers=all_headers, delay=delay)

    def url(self, path: str = "/", host: str = "127.0.0.1") -> str:
        return f"http://{host}:{self.port}{path}"

    def close(self) -> None:
        self._server.shutdown()
        self._server.server_close()


@pytest.fixture
def stub():
    server = Stub()
    yield server
    server.close()


@pytest.fixture
def stub2():
    """A second server, for tests that need two proxies."""
    server = Stub()
    yield server
    server.close()
