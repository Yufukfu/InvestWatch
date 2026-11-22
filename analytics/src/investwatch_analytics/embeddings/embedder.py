"""The embedder the pipeline uses: cache, then breaker, then the HTTP client. It never raises.

`embed(text, content_hash)` returns an `EmbedOutcome`: a vector and the model on success (`ok`, `cached`),
otherwise `vector=None, model=None` and a status naming why (`embed_unavailable`, `embed_timeout`,
`embed_malformed`, `breaker_open`, `empty_text`), so the finding records `model.embedder = null`.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

import numpy as np

from ..config import EmbedSettings
from .breaker import Breaker
from .cache import EmbedCache
from .client import EmbedClient, EmbedMalformed, EmbedUnavailable

log = logging.getLogger(__name__)


@dataclass(frozen=True, eq=False)
class EmbedOutcome:
    vector: np.ndarray | None
    model: str | None
    status: str

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, EmbedOutcome):
            return NotImplemented
        same_vec = (self.vector is None and other.vector is None) or (
            self.vector is not None and other.vector is not None and np.array_equal(self.vector, other.vector))
        return same_vec and self.model == other.model and self.status == other.status

    __hash__ = None  # type: ignore[assignment]


class Embedder(Protocol):
    model: str

    def embed(self, text: str, content_hash: str | None) -> EmbedOutcome: ...


class HttpEmbedder:
    def __init__(self, settings: EmbedSettings, *, redis: Any = None,
                 clock: Callable[[], float] = time.monotonic, client: EmbedClient | None = None):
        self._s = settings
        self._client = client or EmbedClient(settings)
        self._cache = EmbedCache(redis, settings) if redis is not None else None
        self._breaker = Breaker(settings.breaker_failures, settings.breaker_cooldown_s, clock)

    @property
    def model(self) -> str:
        return self._s.model

    def close(self) -> None:
        self._client.close()

    def embed(self, text: str, content_hash: str | None) -> EmbedOutcome:
        """`content_hash` is the document's stored value (ADR 0105); None or empty: embed without the cache."""
        if not text.strip():
            return EmbedOutcome(None, None, "empty_text")
        cache = self._cache if content_hash else None
        if cache is not None:
            cached = cache.get(content_hash)
            if cached is not None:
                return EmbedOutcome(cached, self._s.model, "cached")
        if not self._breaker.allow():
            log.info("embedding skipped", extra={"reason": "breaker_open", "embed_model": self._s.model})
            return EmbedOutcome(None, None, "breaker_open")
        try:
            vector = self._client.embed(text)
        except EmbedUnavailable as exc:
            self._breaker.failure()
            return EmbedOutcome(None, None, exc.reason)
        except EmbedMalformed as exc:
            self._breaker.success()  # the endpoint answered: not an outage
            return EmbedOutcome(None, None, exc.reason)
        except Exception as exc:  # noqa: BLE001 - never raise into the pipeline; also ends a half-open trial
            self._breaker.failure()
            log.warning("embed call failed", extra={"reason": "embed_unavailable", "error": type(exc).__name__,
                                                    "embed_model": self._s.model})
            return EmbedOutcome(None, None, "embed_unavailable")
        self._breaker.success()
        if cache is not None:
            cache.put(content_hash, vector)
        return EmbedOutcome(vector, self._s.model, "ok")
