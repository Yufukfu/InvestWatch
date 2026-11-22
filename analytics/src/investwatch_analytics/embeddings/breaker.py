"""Minimal in-memory circuit breaker, per process (design §2; `analytics-llm-p0` group 10 has none yet).

Closed: calls go through. After `failures` consecutive `failure()` calls it opens for `cooldown_s`; then one
trial call is allowed (half-open): `success()` closes it, `failure()` reopens it.
"""

from __future__ import annotations

import time
from collections.abc import Callable


class Breaker:
    def __init__(self, failures: int, cooldown_s: float, clock: Callable[[], float] = time.monotonic):
        self._limit = failures
        self._cooldown = cooldown_s
        self._clock = clock
        self._streak = 0
        self._open_until: float | None = None
        self._trial = False

    def allow(self) -> bool:
        if self._open_until is None:
            return True
        if self._trial or self._clock() < self._open_until:
            return False
        self._trial = True  # half-open: exactly one call until it reports back
        return True

    def success(self) -> None:
        self._streak = 0
        self._open_until = None
        self._trial = False

    def failure(self) -> None:
        self._streak += 1
        if self._streak >= self._limit:  # the streak survives the open state, so a failed trial reopens
            self._open_until = self._clock() + self._cooldown
        self._trial = False
