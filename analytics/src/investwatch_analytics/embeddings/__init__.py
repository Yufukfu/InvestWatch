"""Embeddings for the analytics preprocessing (analytics-embeddings; ADR 0313).

`client.EmbedClient` talks to an OpenAI-compatible `/embeddings` endpoint; `embedder.HttpEmbedder` adds the
Redis cache and the circuit breaker and never raises; `build_embedder(settings, redis)` returns `None` when
`EMBED_BASE_URL` is empty.
"""

from __future__ import annotations

from typing import Any

from ..config import EmbedSettings
from .embedder import Embedder, EmbedOutcome, HttpEmbedder

__all__ = ["Embedder", "EmbedOutcome", "HttpEmbedder", "build_embedder"]


def build_embedder(settings: EmbedSettings, redis: Any = None) -> HttpEmbedder | None:
    """`None` when `EMBED_BASE_URL` is empty (embeddings off); `redis` enables the vector cache."""
    if not settings.enabled:
        return None
    return HttpEmbedder(settings, redis=redis)
