"""OpenAI-compatible embeddings client (ADR 0313): plain `httpx`, no provider SDK; mirrors `llm.client`.

`embed()` returns an L2-normalized float32 vector of `EMBED_DIM` values, or raises `EmbedUnavailable`
(connection error, timeout, HTTP error incl. 404 for a model that is not pulled: counts toward the breaker) or
`EmbedMalformed` (the endpoint answered, but not with one valid vector). Logs carry the host, model, status,
latency and error class only: never the API key, the input text or vector values.
"""

from __future__ import annotations

import json
import logging
import math
import time
from typing import Any
from urllib.parse import urlsplit

import httpx
import numpy as np

from ..config import EmbedSettings

log = logging.getLogger(__name__)
CONNECT_TIMEOUT_S = 3.0
#: One 1024-float vector is about 20 kB of JSON; anything far larger is not one answer.
MAX_RESPONSE_BYTES = 1_000_000


class EmbedError(Exception):
    reason = "embed_error"

    def __init__(self, detail: str, *, status: int | None = None):
        super().__init__(detail)
        self.status = status


class EmbedUnavailable(EmbedError):
    """Connection error, timeout or HTTP error status. `reason` is `embed_timeout` or `embed_unavailable`."""

    def __init__(self, detail: str, *, status: int | None = None, timeout: bool = False):
        super().__init__(detail, status=status)
        self.reason = "embed_timeout" if timeout else "embed_unavailable"


class EmbedMalformed(EmbedError):
    reason = "embed_malformed"


class EmbedClient:
    def __init__(self, settings: EmbedSettings, *, transport: httpx.BaseTransport | None = None):
        self._s = settings
        self._url = settings.base_url.rstrip("/") + "/embeddings"
        self._host = urlsplit(settings.base_url).hostname or ""
        headers = {"Content-Type": "application/json"}
        if settings.api_key:
            headers["Authorization"] = f"Bearer {settings.api_key}"
        # trust_env=False: no proxy, netrc or CA bundle from the environment.
        self._http = httpx.Client(headers=headers, transport=transport, follow_redirects=False, trust_env=False)

    @property
    def model(self) -> str:
        return self._s.model

    def close(self) -> None:
        self._http.close()

    def embed(self, text: str) -> np.ndarray:
        """Embed the first `EMBED_MAX_CHARS` characters of `text` (the caller passes the normalized text)."""
        if not text.strip():
            raise ValueError("empty text is never sent to the embedder")
        read = self._s.timeout_s
        timeout = httpx.Timeout(read, connect=min(CONNECT_TIMEOUT_S, read))
        body = {"model": self._s.model, "input": [text[: self._s.max_chars]]}
        started = time.perf_counter()
        deadline = time.monotonic() + read  # also bounds a server that trickles the body
        status = None
        try:
            with self._http.stream("POST", self._url, json=body, timeout=timeout) as response:
                status = response.status_code
                if status >= 300:
                    self._log("embed call failed", started, status=status, reason="embed_unavailable")
                    raise EmbedUnavailable(f"HTTP {status}", status=status)
                raw = bytearray()
                for part in response.iter_bytes():
                    raw += part
                    if len(raw) > MAX_RESPONSE_BYTES:
                        raise EmbedMalformed("response too large")
                    if time.monotonic() > deadline:
                        raise httpx.ReadTimeout("total deadline exceeded")
        except httpx.TimeoutException as exc:
            self._log("embed call failed", started, error=type(exc).__name__, reason="embed_timeout")
            raise EmbedUnavailable(f"timeout after {read:g} s", timeout=True) from None
        except httpx.HTTPError as exc:
            self._log("embed call failed", started, error=type(exc).__name__, reason="embed_unavailable")
            raise EmbedUnavailable(f"cannot reach the embeddings endpoint ({type(exc).__name__})") from None
        except EmbedMalformed as exc:
            self._log("embed call failed", started, status=status, reason="embed_malformed", error=str(exc))
            raise
        try:
            vector = self._vector(bytes(raw))
        except EmbedMalformed as exc:
            self._log("embed call failed", started, status=status, reason="embed_malformed", error=str(exc))
            raise
        self._log("embed call", started, status=status)
        return vector

    def _vector(self, raw: bytes) -> np.ndarray:
        try:
            envelope = json.loads(raw)
            values = envelope["data"][0]["embedding"]
        except (ValueError, KeyError, IndexError, TypeError):
            raise EmbedMalformed("not an embeddings response with one vector") from None
        return validate_vector(values, self._s.dim)

    def _log(self, msg: str, started: float, **extra: Any) -> None:
        level = logging.INFO if msg == "embed call" else logging.WARNING
        log.log(level, msg, extra={"embed_host": self._host, "embed_model": self._s.model,
                                   "latency_ms": round((time.perf_counter() - started) * 1000), **extra})


def validate_vector(values: Any, dim: int) -> np.ndarray:
    """`dim` finite numbers with a non-zero norm -> L2-normalized float32; anything else is `EmbedMalformed`."""
    if not isinstance(values, list):
        raise EmbedMalformed("embedding is not a list")
    if len(values) != dim:
        raise EmbedMalformed(f"embedding has {len(values)} values, expected {dim}")
    if not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in values):
        raise EmbedMalformed("embedding has a non-numeric value")
    vector = np.asarray(values, dtype=np.float64)
    with np.errstate(over="ignore", invalid="ignore"):
        norm = float(np.linalg.norm(vector))
    # A NaN or infinite value, or an overflow of huge values, makes the norm non-finite.
    if not math.isfinite(norm) or norm == 0.0:
        raise EmbedMalformed("embedding has a zero or non-finite norm")
    return (vector / norm).astype(np.float32)
