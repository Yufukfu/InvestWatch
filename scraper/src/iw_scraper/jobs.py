"""The queue wrapper around one collection job: lock, concurrency cap, retry, deferral, outcome.

`ctx` carries `settings` (QueueSettings), `run_source` (async source_id -> AttemptResult) and
`record_error` (async JobError -> None); the collector and the ingest are stubs here and supplied by
`scraper-v1` and `scraper-ingest`.
"""

import asyncio
import random
from dataclasses import dataclass
from datetime import UTC, datetime

from arq.connections import ArqRedis
from arq.worker import Function, Retry, func

from iw_scraper.guards import DomainHealth, LeaseSemaphore, RunLock
from iw_scraper.retry import backoff_delay, is_transient
from iw_scraper.types import Deferral, JobError, Reason

# arq counts every Retry as a try, deferrals included; we count failed attempts ourselves.
ARQ_MAX_TRIES = 10_000
ARQ_TIMEOUT_SLACK = 30.0
ATTEMPTS_KEY_TTL = 24 * 3600
KEEP_ALIVE_DIVISOR = 3

_rng = random.Random()


@dataclass(frozen=True)
class AttemptResult:
    """What one attempt of a collection reports back to the queue."""

    documents: int = 0
    error: JobError | None = None
    http_status: int | None = None
    retry_after: float | None = None
    deferral: Deferral | None = None


@dataclass(frozen=True)
class QueueSettings:
    max_tries: int = 3
    backoff_base: float = 2.0
    backoff_cap: float = 300.0
    attempt_timeout: float = 60.0
    domain_concurrency: int = 2
    lease_ttl: float = 30.0
    requeue_delay: float = 5.0
    failure_threshold: int = 5
    domain_cooldown: float = 300.0


def job_function(settings: QueueSettings) -> Function:
    return func(
        execute_job,
        name="execute_job",
        max_tries=ARQ_MAX_TRIES,
        timeout=settings.attempt_timeout + ARQ_TIMEOUT_SLACK,
    )


async def execute_job(ctx: dict, source_id: str, domain: str) -> str:
    """Returns `ok`, `failed` or `coalesced`; raises `Retry` to wait and try again."""
    lock = RunLock(ctx["redis"], source_id, ctx["job_id"])
    if not await lock.acquire(ctx["settings"].lease_ttl):
        return "coalesced"
    try:
        return await _run_locked(ctx, source_id, domain, lock)
    except Retry:
        raise  # the lock stays held until the job's final outcome
    except BaseException:
        await lock.release()
        raise


async def _run_locked(ctx: dict, source_id: str, domain: str, lock: RunLock) -> str:
    redis: ArqRedis = ctx["redis"]
    cfg: QueueSettings = ctx["settings"]
    health = DomainHealth(redis, domain, threshold=cfg.failure_threshold, cooldown=cfg.domain_cooldown)

    if (paused_for := await health.paused_for()) > 0:
        await _requeue(lock, cfg, paused_for)
    semaphore = LeaseSemaphore(redis, domain, cfg.domain_concurrency)
    lease_id = f"{ctx['job_id']}:{ctx['job_try']}"
    if not await semaphore.acquire(lease_id, cfg.lease_ttl):
        await _requeue(lock, cfg, cfg.requeue_delay)

    result = await _attempt(ctx["run_source"], source_id, lock, semaphore, lease_id, cfg)

    if result.deferral:
        await _requeue(lock, cfg, max(0.0, (result.deferral.until - datetime.now(UTC)).total_seconds()))
    attempts_key = f"iw:attempts:{ctx['job_id']}"
    if result.error and is_transient(result.error.reason, result.http_status):
        failures = await redis.incr(attempts_key)
        await redis.expire(attempts_key, ATTEMPTS_KEY_TTL)
        if failures < cfg.max_tries:
            delay = backoff_delay(
                failures, base=cfg.backoff_base, cap=cfg.backoff_cap, retry_after=result.retry_after, rng=_rng
            )
            await _requeue(lock, cfg, delay)

    if result.error:
        await ctx["record_error"](result.error)
    await health.record(ok=result.error is None)
    await redis.delete(attempts_key)
    await lock.release()
    return "failed" if result.error else "ok"


async def _requeue(lock: RunLock, cfg: QueueSettings, delay: float) -> None:
    """Wait `delay` seconds and run again, keeping the lock alive across the wait."""
    await lock.extend(delay + cfg.lease_ttl)
    raise Retry(defer=delay)


async def _attempt(run_source, source_id, lock: RunLock, semaphore: LeaseSemaphore, lease_id: str, cfg: QueueSettings):
    keeper = asyncio.create_task(_keep_alive(lock, semaphore, lease_id, cfg.lease_ttl))
    try:
        async with asyncio.timeout(cfg.attempt_timeout):
            return await run_source(source_id)
    except TimeoutError:
        return AttemptResult(error=JobError(Reason.TIMEOUT, "attempt exceeded its timeout", source_id))
    finally:
        keeper.cancel()
        await semaphore.release(lease_id)


async def _keep_alive(lock: RunLock, semaphore: LeaseSemaphore, lease_id: str, ttl: float) -> None:
    while True:
        await asyncio.sleep(ttl / KEEP_ALIVE_DIVISOR)
        await lock.extend(ttl)
        await semaphore.acquire(lease_id, ttl)
