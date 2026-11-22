"""Module thresholds in Redis key iw:settings:thresholds (ADR 0305, api-v1 design decision 4).

Format: a JSON string with the shape of the OpenAPI `Thresholds` schema, e.g. {"M1":0.6,"M2":0.5,"M3":0.7}.
The API owns the key and writes the defaults when it is missing; analytics only reads it.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable

from redis.exceptions import RedisError

from .errors import ServiceUnavailable

KEY = "iw:settings:thresholds"
# Best-F1 thresholds of the gold-set evaluation: a copy of analytics/eval/thresholds.json (ADR 0316, superseding
# ADR 0305's values; M1 from the DeepSeek gold run, ADR 0318). Written only when the key is missing; analytics/tests/test_eval_thresholds.py pins the copy.
DEFAULTS = {"M1": 0.75, "M2": 0.1, "M3": 0.4}
MODULES = ("M1", "M2", "M3")
MEDIUM_BAND = 0.2  # medium = within 0.2 below the threshold (integration-plan §4)
RETRY_AFTER_S = 5.0  # after a failed read, use the last known values without contacting Redis

log = logging.getLogger("investwatch_api.thresholds")


def risk_level(score: float, threshold: float) -> str:
    if score >= threshold:
        return "high"
    if score >= threshold - MEDIUM_BAND:
        return "medium"
    return "low"


def _parse(raw) -> dict[str, float] | None:
    try:
        value = json.loads(raw)
        out = {m: float(value[m]) for m in MODULES}
    except (TypeError, ValueError, KeyError):
        return None
    return out if all(0 <= v <= 1 for v in out.values()) else None


class ThresholdStore:
    """Reads the key on every call while Redis answers; falls back to the last good value (else defaults)."""

    def __init__(self, redis, clock: Callable[[], float] = time.monotonic):
        self._redis = redis
        self._clock = clock
        self._last: dict[str, float] = dict(DEFAULTS)
        self._skip_until = 0.0

    async def current(self) -> dict[str, float]:
        if self._clock() < self._skip_until:
            return dict(self._last)
        try:
            raw = await self._redis.get(KEY)
            if raw is None:
                await self._redis.set(KEY, json.dumps(DEFAULTS), nx=True)
                raw = await self._redis.get(KEY)
        except (RedisError, OSError) as exc:
            self._skip_until = self._clock() + RETRY_AFTER_S
            log.warning("thresholds read failed, using last known values", extra={"reason": type(exc).__name__})
            return dict(self._last)
        parsed = _parse(raw)
        if parsed is None:
            log.warning("thresholds key is malformed, using last known values")
            return dict(self._last)
        self._last = parsed
        return dict(parsed)

    async def replace(self, values: dict[str, float]) -> dict[str, float]:
        new = {m: float(values[m]) for m in MODULES}
        try:
            await self._redis.set(KEY, json.dumps(new))
        except (RedisError, OSError):
            raise ServiceUnavailable("redis") from None
        self._last = new
        self._skip_until = 0.0
        return dict(new)
