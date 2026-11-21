"""Per-domain rate limit shared by all workers.

A token bucket of capacity one: each request reserves the next free start slot for its domain, so two requests
for one domain start at least `interval` apart however many workers there are. The slot lives in Redis and is
claimed by a Lua script that reads Redis's own clock, so workers need no synchronised clocks. When Redis is down
the limiter falls back to a process-local one (spacing within one worker only) and logs a warning once.
"""

import asyncio
import logging
import math
import time
from collections.abc import Awaitable, Callable
from urllib.parse import urlsplit

from redis.exceptions import RedisError

_log = logging.getLogger(__name__)

_WWW = "www."
REDIS_TIMEOUT_SECONDS = 2.0  # a Redis that does not answer is treated as down

# KEYS[1] slot key; ARGV[1] interval in ms. Returns the ms this caller must wait before starting.
_RESERVE_SLOT = """
local t = redis.call('TIME')
local now = t[1] * 1000 + math.floor(t[2] / 1000)
local slot = math.max(now, tonumber(redis.call('GET', KEYS[1]) or '0'))
local interval = tonumber(ARGV[1])
redis.call('SET', KEYS[1], slot + interval, 'PX', slot - now + interval)
return slot - now
"""


def domain_key(url_or_host: str) -> str:
    """The lowercase host without a leading `www.`: what a politeness rule is keyed by."""
    host = urlsplit(url_or_host if "://" in url_or_host else "//" + url_or_host).hostname or ""
    return host.removeprefix(_WWW)


def _check_interval(interval_seconds: float) -> float:
    if not math.isfinite(interval_seconds) or interval_seconds <= 0:
        raise ValueError("the rate limit interval must be a positive number of seconds")
    return interval_seconds


class LocalLimiter:
    def __init__(
        self,
        interval_seconds: float,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._interval = _check_interval(interval_seconds)
        self._clock = clock
        self._sleep = sleep
        self._next_slot: dict[str, float] = {}

    async def wait_turn(self, key: str) -> float:
        """Wait for the next start slot of `key` (a `domain_key`); return the seconds waited."""
        now = self._clock()
        slot = max(now, self._next_slot.get(key, 0.0))
        self._next_slot[key] = slot + self._interval  # reserved before any await, so callers never share a slot
        wait = slot - now
        if wait > 0:
            await self._sleep(wait)
        return wait


class DomainLimiter:
    def __init__(self, client, interval_seconds: float, *, key_prefix: str = "iw:rl:") -> None:
        self._client = client
        self._interval = _check_interval(interval_seconds)
        self._prefix = key_prefix
        self._local = LocalLimiter(interval_seconds)
        self._degraded = False

    async def wait_turn(self, domain: str) -> float:
        """Wait for this domain's next start slot, shared across workers; return the seconds waited."""
        key = domain_key(domain)
        try:
            wait_ms = await asyncio.wait_for(
                self._client.eval(_RESERVE_SLOT, 1, self._prefix + key, int(self._interval * 1000)),
                REDIS_TIMEOUT_SECONDS,
            )
        except (RedisError, OSError) as exc:  # a timeout is an OSError
            if not self._degraded:
                self._degraded = True
                _log.warning("rate limit: Redis unavailable (%s), using the local limiter", type(exc).__name__)
            return await self._local.wait_turn(key)
        self._degraded = False
        wait = wait_ms / 1000
        if wait > 0:
            await asyncio.sleep(wait)
        return wait
