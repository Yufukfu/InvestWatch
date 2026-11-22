"""Embedding cache in Redis (design §3): `iw:emb:v1:{variant}:{content_hash}` -> base64 float32, with a TTL.

`variant` covers model, dimension and input length, so a swap or a different cut never reuses a vector.
Values are text, readable through a `decode_responses=True` client. Any Redis error is a miss or a skipped
write, logged and never raised; a value that does not decode to a valid vector is a miss.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import logging
from typing import Any

import numpy as np
import redis

from ..config import EmbedSettings
from .client import EmbedMalformed, validate_vector

log = logging.getLogger(__name__)


def variant(settings: EmbedSettings) -> str:
    return hashlib.sha256(f"{settings.model}|{settings.dim}|{settings.max_chars}".encode()).hexdigest()[:12]


def cache_key(settings: EmbedSettings, content_hash: str) -> str:
    return f"iw:emb:v1:{variant(settings)}:{content_hash}"


class EmbedCache:
    def __init__(self, client: Any, settings: EmbedSettings):
        self._r = client
        self._s = settings

    def get(self, content_hash: str) -> np.ndarray | None:
        try:
            raw = self._r.get(cache_key(self._s, content_hash))
        except (redis.RedisError, UnicodeDecodeError) as exc:  # a decode_responses client decodes in get()
            log.warning("embedding cache read failed", extra={"reason": "embed_cache_unavailable",
                                                              "error": type(exc).__name__})
            return None
        if raw is None:
            return None
        try:
            data = base64.b64decode(raw, validate=True)
            if len(data) != 4 * self._s.dim:  # bounds the work on an oversized planted value
                return None
            # validate_vector rejects NaN or a zero vector: a miss too.
            return validate_vector(np.frombuffer(data, dtype=np.float32).tolist(), self._s.dim)
        except (binascii.Error, ValueError, EmbedMalformed):
            return None

    def put(self, content_hash: str, vector: np.ndarray) -> None:
        value = base64.b64encode(np.asarray(vector, dtype=np.float32).tobytes()).decode("ascii")
        try:
            self._r.set(cache_key(self._s, content_hash), value, ex=self._s.cache_ttl_s)
        except redis.RedisError as exc:
            log.warning("embedding cache write failed", extra={"reason": "embed_cache_unavailable",
                                                               "error": type(exc).__name__})
