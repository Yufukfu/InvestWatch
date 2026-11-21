"""A fixture web server and a Chromium that maps the fixture host names to it, so tests need no network.

`source.test`, `third.test` and `other.test` all resolve to the one local server (told apart by the Host header the
server records). Every other host goes through the real address checker, so private and metadata addresses are
refused exactly as in production.
"""

import threading
from collections.abc import Awaitable, Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import async_playwright

from iw_renderer.confine import LAUNCH_ARGS
from iw_scraper.addresses import AddressChecker

FIXTURE_HOSTS = ("source.test", "third.test", "other.test")


class FixtureServer:
    def __init__(self) -> None:
        self.routes: dict[tuple[str, str], tuple[int, dict[str, str], bytes]] = {}
        self.requests: list[tuple[str, str, dict[str, str]]] = []  # (host, path, headers)
        self.raw_headers: dict[str, list[tuple[str, str]]] = {}  # path -> every header line as sent, lowercase names, duplicates kept
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802 (http.server API)
                host = (self.headers.get("Host") or "").split(":")[0]
                outer.requests.append((host, self.path, dict(self.headers)))
                outer.raw_headers[self.path] = [(n.lower(), v) for n, v in self.headers.items()]
                status, headers, body = outer.routes.get((host, self.path), (404, {}, b"not found"))
                self.send_response(status)
                headers = {"Content-Type": "text/html; charset=utf-8", **headers}
                for name, value in headers.items():
                    self.send_header(name, value)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args) -> None:  # silence the test output
                pass

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self._server.server_address[1]
        threading.Thread(target=self._server.serve_forever, daemon=True).start()

    def serve(self, host: str, path: str, body: str | bytes, content_type: str = "text/html; charset=utf-8", **headers: str) -> str:
        data = body.encode() if isinstance(body, str) else body
        self.routes[(host, path)] = (200, {"Content-Type": content_type, **headers}, data)
        return f"http://{host}:{self.port}{path}"

    def hits(self, host: str | None = None) -> list[str]:
        return [f"{h}{p}" for h, p, _ in self.requests if host is None or h == host]

    def close(self) -> None:
        self._server.shutdown()


@pytest.fixture
def server():
    fixture = FixtureServer()
    yield fixture
    fixture.close()


@pytest.fixture
def address_check() -> Callable[[str], Awaitable[str]]:
    real = AddressChecker()

    async def check(host: str) -> str:
        if host in FIXTURE_HOSTS or host == "localhost":
            return "127.0.0.1"
        return await real.check(host)

    return check


@pytest.fixture
async def browser():
    rules = ", ".join(f"MAP {host} 127.0.0.1" for host in FIXTURE_HOSTS)
    async with async_playwright() as playwright:
        launched = None
        for attempt in range(3):  # Chromium sometimes dies while starting inside a busy container; the service restarts on that
            try:
                launched = await playwright.chromium.launch(args=[*LAUNCH_ARGS, f"--host-resolver-rules={rules}"])
                break
            except PlaywrightError:
                if attempt == 2:
                    raise
        yield launched
        await launched.close()
