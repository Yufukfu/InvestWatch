"""Per-domain state shared by all workers: a `Retry-After` deferral and a failure pause.

Both are "do not fetch this domain until T" facts held in Redis as an absolute time. `check` reports the later
of the two as a `Deferral`, which a run returns instead of fetching (not a failure: the queue requeues it).
Times are compared with the injected clock (UTC), so tests need no real waiting. The Redis TTLs only clean up.
Redis errors (`RedisError`) and a Redis that does not answer within `REDIS_TIMEOUT_SECONDS` (`TimeoutError`) propagate: the queue needs Redis as
well, so a gate that quietly let requests through would only hide an outage (the rate limiter, which can degrade
safely, has its own local fallback).
"""

import asyncio
import math
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

from iw_scraper.ratelimit import REDIS_TIMEOUT_SECONDS, domain_key
from iw_scraper.types import Deferral

_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
_MS = timedelta(milliseconds=1)
_CLEANUP_MARGIN_SECONDS = 60
_MAX_DELAY_DIGITS = 15  # more digits than this is beyond any cap; `int()` also refuses 4300+ digits

# KEYS[1] deferral key; ARGV[1] new until (ms), ARGV[2] ttl (s). Only ever moves the deferral later.
_RAISE_DEFERRAL = """
local cur = tonumber(redis.call('GET', KEYS[1]) or '0')
local new = tonumber(ARGV[1])
if new > cur then
  redis.call('SET', KEYS[1], ARGV[1], 'EX', ARGV[2])
  return new
end
return cur
"""

# KEYS[1] failure count, KEYS[2] pause key; ARGV: success (1/0), threshold, pause until (ms), pause ttl (s).
_RECORD_OUTCOME = """
if ARGV[1] == '1' then
  redis.call('DEL', KEYS[1])
  return 0
end
if redis.call('INCR', KEYS[1]) >= tonumber(ARGV[2]) then
  redis.call('SET', KEYS[2], ARGV[3], 'EX', ARGV[4])
  redis.call('DEL', KEYS[1])
  return 1
end
return 0
"""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _to_ms(moment: datetime) -> int:
    return (moment - _EPOCH) // _MS


def _from_ms(ms: bytes | str | int) -> datetime:
    return _EPOCH + int(ms) * _MS


def _ttl_seconds(span: timedelta) -> int:
    return math.ceil(span.total_seconds()) + _CLEANUP_MARGIN_SECONDS


class DomainGate:
    def __init__(
        self,
        client,
        *,
        max_retry_after: float,
        failure_threshold: int,
        pause_seconds: float,
        clock: Callable[[], datetime] = _utc_now,
        key_prefix: str = "iw:dom:",
    ) -> None:
        for name, value in (("max_retry_after", max_retry_after), ("pause_seconds", pause_seconds)):
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be a positive number of seconds")
        if failure_threshold < 1:
            raise ValueError("failure_threshold must be at least 1")
        self._client = client
        self._cap = timedelta(seconds=max_retry_after)
        self._threshold = failure_threshold
        self._pause = timedelta(seconds=pause_seconds)
        self._clock = clock
        self._prefix = key_prefix

    def _key(self, kind: str, domain: str) -> str:
        return f"{self._prefix}{kind}:{domain_key(domain)}"

    @staticmethod
    async def _redis(call):
        return await asyncio.wait_for(call, REDIS_TIMEOUT_SECONDS)

    async def check(self, domain: str) -> Deferral | None:
        """The time until which this domain must not be fetched, or None when it may be."""
        stored = await self._redis(self._client.mget(self._key("defer", domain), self._key("pause", domain)))
        now = self._clock()
        live = [until for until in (_from_ms(v) for v in stored if v is not None) if until > now]
        return Deferral(until=max(live)) if live else None

    async def defer_for_retry_after(self, domain: str, header: str | None) -> datetime | None:
        """Defer the domain for what a `Retry-After` header asks (capped); the time the deferral now ends, or None."""
        now = self._clock()
        wait = self._wait_asked(header, now)
        if wait is None or wait <= timedelta(0):
            return None
        wait = min(wait, self._cap)
        ends = await self._redis(
            self._client.eval(_RAISE_DEFERRAL, 1, self._key("defer", domain), _to_ms(now + wait), _ttl_seconds(wait))
        )
        return _from_ms(ends)

    def _wait_asked(self, header: str | None, now: datetime) -> timedelta | None:
        text = (header or "").strip()
        if not text:
            return None
        if text.isascii() and text.isdigit():  # delay-seconds; read as a number first so a huge one cannot overflow
            seconds = int(text) if len(text) <= _MAX_DELAY_DIGITS else self._cap.total_seconds()
            return timedelta(seconds=min(seconds, self._cap.total_seconds()))
        try:
            when = parsedate_to_datetime(text)
        except (TypeError, ValueError):
            return None
        return (when if when.tzinfo else when.replace(tzinfo=timezone.utc)) - now

    async def record_outcome(self, domain: str, success: bool) -> None:
        """One recorded job outcome for the domain: a success resets the failure count, enough failures pause it."""
        await self._redis(
            self._client.eval(
                _RECORD_OUTCOME,
                2,
                self._key("failures", domain),
                self._key("pause", domain),
                int(success),
                self._threshold,
                _to_ms(self._clock() + self._pause),
                _ttl_seconds(self._pause),
            )
        )
