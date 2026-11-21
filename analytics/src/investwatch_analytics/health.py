"""`GET /health` for the worker container (`.docs/integration-plan.md` §7: every service has one).

Stdlib only, served from a daemon thread. 200 with `{"status": "ok", "redis": true, "db": true}` when every check
answers, 503 with the failing check marked `false` otherwise. A check that raises counts as down; its error text is
never echoed. Not routed through the gateway: the Docker HEALTHCHECK calls it on loopback.
"""

from __future__ import annotations

import json
import logging
import threading
from collections.abc import Callable, Mapping
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

log = logging.getLogger(__name__)

Check = Callable[[], bool]


def _run_check(name: str, check: Check) -> bool:
    try:
        return bool(check())
    except Exception as exc:  # a broken check is a failed check, never a 500
        log.warning("health check raised", extra={"check": name, "error": type(exc).__name__})
        return False


def start_health_server(port: int, checks: Mapping[str, Check], host: str = "0.0.0.0") -> ThreadingHTTPServer:
    """Serve /health on `host:port` (0 = any free port) in a daemon thread; returns the server (call shutdown())."""

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 (stdlib name)
            if self.path != "/health":
                self._reply(404, {"error": "not found"})
                return
            results = {name: _run_check(name, check) for name, check in checks.items()}
            healthy = all(results.values())
            self._reply(200 if healthy else 503, {"status": "ok" if healthy else "degraded", **results})

        def _reply(self, code: int, payload: dict) -> None:
            body = json.dumps(payload).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args) -> None:  # noqa: A002 (stdlib signature)
            log.debug("health request", extra={"request": format % args})

    server = ThreadingHTTPServer((host, port), Handler)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, name="health", daemon=True).start()
    return server
