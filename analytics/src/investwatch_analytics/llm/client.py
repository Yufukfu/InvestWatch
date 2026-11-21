"""OpenAI-compatible chat completions client (ADR 0304): plain `httpx`, no provider SDK.

`complete()` returns the assistant message content parsed as a JSON object with a `results` list, or raises
`LlmUnavailable` (endpoint down, timeout, HTTP error: counts toward the circuit breaker) or `LlmMalformed`
(the endpoint answered, but not in the agreed shape). Logs carry the host, model, status, latency and error
class only: never the API key, the request body (scraped text) or the response body (model output).
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any
from urllib.parse import urlsplit

import httpx

from ..config import LlmSettings

log = logging.getLogger(__name__)
CONNECT_TIMEOUT_S = 3.0
#: A chat-completions answer for a few checks is a few kB; anything far larger is not one.
MAX_RESPONSE_BYTES = 1_000_000


class LlmError(Exception):
    reason = "llm_error"

    def __init__(self, detail: str, *, status: int | None = None):
        super().__init__(detail)
        self.status = status


class LlmUnavailable(LlmError):
    """Connection error, timeout or HTTP error status. `reason` is `llm_timeout` or `llm_unavailable`."""

    def __init__(self, detail: str, *, status: int | None = None, timeout: bool = False):
        super().__init__(detail, status=status)
        self.reason = "llm_timeout" if timeout else "llm_unavailable"


class LlmMalformed(LlmError):
    reason = "llm_malformed"


class ChatClient:
    def __init__(self, settings: LlmSettings, *, transport: httpx.BaseTransport | None = None):
        self._s = settings
        self._url = settings.base_url.rstrip("/") + "/chat/completions"
        self._host = urlsplit(settings.base_url).hostname or ""
        headers = {"Content-Type": "application/json"}
        if settings.api_key:
            headers["Authorization"] = f"Bearer {settings.api_key}"
        # trust_env=False: no proxy, netrc or CA bundle from the environment (scraped text and key stay direct).
        self._http = httpx.Client(headers=headers, transport=transport, follow_redirects=False, trust_env=False)

    def close(self) -> None:
        self._http.close()

    def complete(self, system: str, user: str, *, timeout_s: float | None = None) -> dict[str, Any]:
        read = self._s.timeout_s if timeout_s is None else timeout_s
        timeout = httpx.Timeout(read, connect=min(CONNECT_TIMEOUT_S, read))
        body = {
            "model": self._s.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }
        started = time.perf_counter()
        # httpx timeouts are per socket read; the deadline also bounds a server that trickles the body.
        deadline = time.monotonic() + read
        status = None
        try:
            with self._http.stream("POST", self._url, json=body, timeout=timeout) as response:
                status = response.status_code
                if status >= 300:
                    self._log("llm call failed", started, status=status, reason="llm_unavailable")
                    raise LlmUnavailable(f"HTTP {status}", status=status)
                raw = bytearray()
                for part in response.iter_bytes():
                    raw += part
                    if len(raw) > MAX_RESPONSE_BYTES:
                        raise LlmMalformed("response too large")
                    if time.monotonic() > deadline:
                        raise httpx.ReadTimeout("total deadline exceeded")
        except httpx.TimeoutException as exc:
            self._log("llm call failed", started, error=type(exc).__name__, reason="llm_timeout")
            raise LlmUnavailable(f"timeout after {read:g} s", timeout=True) from None
        except httpx.HTTPError as exc:
            self._log("llm call failed", started, error=type(exc).__name__, reason="llm_unavailable")
            raise LlmUnavailable(f"cannot reach the LLM endpoint ({type(exc).__name__})") from None
        except LlmMalformed as exc:
            self._log("llm call failed", started, status=status, reason="llm_malformed", error=str(exc))
            raise
        try:
            content = self._content(bytes(raw))
        except LlmMalformed as exc:
            self._log("llm call failed", started, status=status, reason="llm_malformed", error=str(exc))
            raise
        self._log("llm call", started, status=status)
        return content

    @staticmethod
    def _content(raw: bytes) -> dict[str, Any]:
        try:
            envelope = json.loads(raw)
            content = envelope["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError):
            raise LlmMalformed("not a chat completions response") from None
        if not isinstance(content, str):
            raise LlmMalformed("message content is not a string")
        try:
            parsed = json.loads(content)
        except ValueError:
            raise LlmMalformed("message content is not JSON") from None
        if not isinstance(parsed, dict):
            raise LlmMalformed("message content is not a JSON object")
        if not isinstance(parsed.get("results"), list):
            raise LlmMalformed("message content has no `results` list")
        return parsed

    def _log(self, msg: str, started: float, **extra: Any) -> None:
        level = logging.INFO if msg == "llm call" else logging.WARNING
        log.log(level, msg, extra={"llm_host": self._host, "llm_model": self._s.model,
                                   "latency_ms": round((time.perf_counter() - started) * 1000), **extra})
