"""Local stub of an OpenAI-compatible chat completions endpoint. Tests never call a real LLM.

`StubLLM` runs a `ThreadingHTTPServer` on 127.0.0.1:<free port> and answers `POST /v1/chat/completions` from a
scripted queue. Each script item is a `Reply`; when the queue is empty the stub answers `default`. Every
request (path, headers, parsed JSON body) is recorded in `requests`.
"""

from __future__ import annotations

import json
import socket
import threading
import time
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

#: Loopback ports the test network guard lets through (conftest `_no_real_llm`).
_PORTS: set[int] = set()


def register_port(port: int) -> None:
    _PORTS.add(port)


def is_stub_port(port: int | None) -> bool:
    return port in _PORTS


@dataclass
class Reply:
    status: int = 200
    content: str | None = None          # the assistant message content (a JSON string for the judge)
    body: bytes | None = None           # a raw body instead of a chat-completions envelope
    sleep_s: float = 0.0                # sleep before answering (timeout tests)
    close: bool = False                 # drop the connection without answering

    @classmethod
    def results(cls, *items: dict[str, Any]) -> "Reply":
        return cls(content=json.dumps({"results": list(items)}, ensure_ascii=False))


@dataclass
class StubLLM:
    script: list[Reply] = field(default_factory=list)
    default: Reply = field(default_factory=lambda: Reply.results())
    requests: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        stub = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args: Any) -> None:  # keep test output clean
                return

            def do_POST(self) -> None:  # noqa: N802 (http.server API)
                length = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(length)
                try:
                    body = json.loads(raw)
                except ValueError:
                    body = None
                stub.requests.append({"path": self.path, "headers": dict(self.headers), "body": body})
                reply = stub.script.pop(0) if stub.script else stub.default
                if reply.sleep_s:
                    time.sleep(reply.sleep_s)
                if reply.close:
                    self.connection.shutdown(socket.SHUT_RDWR)
                    return
                if reply.body is not None:
                    payload = reply.body
                else:
                    payload = json.dumps({
                        "id": "stub", "object": "chat.completion", "model": (body or {}).get("model"),
                        "choices": [{"index": 0, "finish_reason": "stop",
                                     "message": {"role": "assistant", "content": reply.content}}],
                    }).encode("utf-8")
                self.send_response(reply.status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._server.daemon_threads = True
        register_port(self._server.server_address[1])
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    @property
    def base_url(self) -> str:
        host, port = self._server.server_address[:2]
        return f"http://{host}:{port}/v1"

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()


def closed_port_url() -> str:
    """A base URL on 127.0.0.1 where nothing listens (connection refused)."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    register_port(port)
    return f"http://127.0.0.1:{port}/v1"
