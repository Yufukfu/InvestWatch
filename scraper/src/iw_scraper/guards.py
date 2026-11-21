"""Shared per-domain and per-source state in Redis (all stateless workers see the same keys)."""

from arq.connections import ArqRedis

# Our own keys; arq's `arq:job:` and `arq:result:` prefixes are fixed by the library.
KEY_PREFIX = "iw:scraper:"

_ACQUIRE_LEASE = """
local t = redis.call('TIME')
local now = t[1] * 1000 + math.floor(t[2] / 1000)
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', now)
if redis.call('ZSCORE', KEYS[1], ARGV[1]) or redis.call('ZCARD', KEYS[1]) < tonumber(ARGV[3]) then
  redis.call('ZADD', KEYS[1], now + tonumber(ARGV[2]), ARGV[1])
  return 1
end
return 0
"""

_ACQUIRE_LOCK = """
local holder = redis.call('GET', KEYS[1])
if not holder then redis.call('SET', KEYS[1], ARGV[1], 'PX', ARGV[2]) return 1 end
if holder == ARGV[1] then redis.call('PEXPIRE', KEYS[1], ARGV[2]) return 1 end
return 0
"""

_EXTEND_LOCK = """
if redis.call('GET', KEYS[1]) == ARGV[1] then return redis.call('PEXPIRE', KEYS[1], ARGV[2]) end
return 0
"""

_RELEASE_LOCK = """
if redis.call('GET', KEYS[1]) == ARGV[1] then return redis.call('DEL', KEYS[1]) end
return 0
"""


# Raise the deferral, never shorten one that is already longer (PTTL is -2 when the key is absent).
_DEFER = """
if redis.call('PTTL', KEYS[1]) < tonumber(ARGV[1]) then redis.call('SET', KEYS[1], 1, 'PX', ARGV[1]) end
return 1
"""


def _millis(seconds: float) -> int:
    return max(1, int(seconds * 1000))


class LeaseSemaphore:
    """Counting semaphore: at most `cap` live leases; a lease that is not renewed expires on its own."""

    def __init__(self, redis: ArqRedis, name: str, cap: int) -> None:
        self._redis = redis
        self._key = f"{KEY_PREFIX}sem:{name}"
        self._cap = cap

    async def acquire(self, lease_id: str, ttl: float) -> bool:
        """Take a slot, or renew the lease if `lease_id` already holds one."""
        granted = await self._redis.eval(_ACQUIRE_LEASE, 1, self._key, lease_id, _millis(ttl), self._cap)
        return granted == 1

    async def release(self, lease_id: str) -> None:
        await self._redis.zrem(self._key, lease_id)


class RunLock:
    """One run per source: held by a job id from its first attempt to its final outcome."""

    def __init__(self, redis: ArqRedis, source_id: str, owner: str) -> None:
        self._redis = redis
        self._key = f"{KEY_PREFIX}lock:{source_id}"
        self._owner = owner

    async def acquire(self, ttl: float) -> bool:
        """Take the lock; the same owner may take it again (a retry of the same job)."""
        return await self._redis.eval(_ACQUIRE_LOCK, 1, self._key, self._owner, _millis(ttl)) == 1

    async def extend(self, ttl: float) -> bool:
        return await self._redis.eval(_EXTEND_LOCK, 1, self._key, self._owner, _millis(ttl)) == 1

    async def release(self) -> None:
        await self._redis.eval(_RELEASE_LOCK, 1, self._key, self._owner)


class DomainHealth:
    """Per-domain waits: a `Retry-After` deferral, and the failure cooldown after consecutive failed jobs.

    One outcome is recorded per job for the cooldown; every worker sees both waits.
    """

    def __init__(self, redis: ArqRedis, domain: str, *, threshold: int, cooldown: float) -> None:
        self._redis = redis
        self._failures_key = f"{KEY_PREFIX}domain:{domain}:failures"
        self._paused_key = f"{KEY_PREFIX}domain:{domain}:paused"
        self._deferred_key = f"{KEY_PREFIX}domain:{domain}:deferred"
        self._threshold = threshold
        self._cooldown = cooldown

    async def paused_for(self) -> float:
        """Seconds until the domain may be used again, 0 when it is not paused."""
        remaining_ms = await self._redis.pttl(self._paused_key)
        return max(0, remaining_ms) / 1000

    async def defer(self, seconds: float) -> None:
        """Keep every worker off the domain for `seconds` (a `Retry-After`)."""
        await self._redis.eval(_DEFER, 1, self._deferred_key, _millis(seconds))

    async def deferred_for(self) -> float:
        remaining_ms = await self._redis.pttl(self._deferred_key)
        return max(0, remaining_ms) / 1000

    async def wait_for(self) -> float:
        """Seconds until the domain may be used again: the longer of the pause and the deferral."""
        return max(await self.paused_for(), await self.deferred_for())

    async def record(self, ok: bool) -> None:
        if ok:
            await self._redis.delete(self._failures_key)
            return
        if await self._redis.incr(self._failures_key) >= self._threshold:
            await self._redis.set(self._paused_key, 1, px=_millis(self._cooldown))
            await self._redis.delete(self._failures_key)
