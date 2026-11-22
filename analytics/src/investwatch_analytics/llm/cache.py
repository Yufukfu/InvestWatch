"""Redis response cache (ADR 0309, design §7). A Redis error is a miss or a skipped write: never raised.

The key is derived from `(content_hash, prompt_version, model)` plus module, chunk index and count, the chunk's
character span and the sorted requested rule ids. `content_hash` is the document's stored value (NFC, ADR 0105);
the judge skips the cache for a document without one (issue #31). The value is the validated response content; quote
verification is re-run on every read, so an entry edited in Redis cannot inject evidence.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Sequence
from typing import Any

log = logging.getLogger(__name__)
PREFIX = "iw:llm:v1"


def cache_key(*, module: str, content_hash: str, prompt_version: str, model: str, chunk_index: int,
              chunk_count: int, chunk_span: tuple[int, int], rule_ids: Sequence[str]) -> str:
    identity = "|".join([content_hash, prompt_version, model, str(chunk_index), str(chunk_count),
                         f"{chunk_span[0]}:{chunk_span[1]}", ",".join(sorted(rule_ids))])
    return f"{PREFIX}:{module}:{hashlib.sha256(identity.encode('utf-8')).hexdigest()}"


class LlmCache:
    def __init__(self, redis: Any, ttl_s: int):
        self._redis = redis
        self._ttl = ttl_s

    def get(self, key: str) -> dict[str, Any] | None:
        try:
            raw = self._redis.get(key)
        except Exception as exc:  # noqa: BLE001 - any Redis failure is a miss
            log.warning("llm cache read failed", extra={"reason": "llm_cache_unavailable", "error": type(exc).__name__})
            return None
        if raw is None:
            return None
        try:
            value = json.loads(raw)
        except (TypeError, ValueError):
            return None
        return value if isinstance(value, dict) and isinstance(value.get("results"), list) else None

    def set(self, key: str, content: dict[str, Any]) -> None:
        try:
            self._redis.set(key, json.dumps(content, ensure_ascii=False), ex=self._ttl)
        except Exception as exc:  # noqa: BLE001 - a failed write only costs a later call
            log.warning("llm cache write failed", extra={"reason": "llm_cache_unavailable", "error": type(exc).__name__})
