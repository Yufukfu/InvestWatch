"""The queue wrapper around one collection job: lock, concurrency cap, retry, deferral, outcome.

`ctx` carries `settings` (QueueSettings), `sources` (SourceStore), `run_source` (async (source_id, started)
-> AttemptResult) and `record_error` (async JobError -> None). `run_source` awaits `started()` once its guards
pass and before its first request, and reports failures as an AttemptResult instead of raising;
the collector and the ingest are stubs here and supplied by
`scraper-v1` and `scraper-ingest`.
"""

import asyncio
import json
import logging
import random
from dataclasses import dataclass
from datetime import UTC, datetime

from arq.connections import ArqRedis, RedisSettings, create_pool
from arq.worker import Function, Retry, func
from redis.exceptions import RedisError

from iw_scraper.config import from_env
from iw_scraper.events import derive_status, publish_scan_event
from iw_scraper.guards import KEY_PREFIX, DomainHealth, LeaseSemaphore, RunLock
from iw_scraper.retry import backoff_delay, is_transient
from iw_scraper.supervise import CONNECTION_ERRORS
from iw_scraper.types import Deferral, JobError, Reason

# arq counts every Retry as a try, deferrals included; we count failed attempts ourselves.
ARQ_MAX_TRIES = 10_000
ARQ_TIMEOUT_SLACK = 30.0
ATTEMPTS_KEY_TTL = 24 * 3600
# arq rejects a job id whose result is still stored: this is what de-duplicates a replayed schedule slot, so it
# is pinned and stays far longer than the scheduler's catch-up window
RESULT_TTL = 3600.0
KEEP_ALIVE_DIVISOR = 3

# arq pickles jobs and results by default; JSON keeps the queue readable and a poisoned Redis from running code.
# One place for the queue name and serializers: the worker, every pool and the tests share them.
QUEUE_NAME = f"{KEY_PREFIX}queue"
ARQ_OPTIONS = {"queue_name": QUEUE_NAME, "job_serializer": lambda data: json.dumps(data).encode(), "job_deserializer": json.loads}

logger = logging.getLogger(__name__)
_rng = random.Random()


@dataclass(frozen=True)
class AttemptResult:
    """What one attempt of a collection reports back to the queue."""

    documents: int = 0
    error: JobError | None = None
    http_status: int | None = None
    retry_after: float | None = None
    deferral: Deferral | None = None
    recorded: bool = False  # the collector already stored `error` as a job error, so the queue does not


@dataclass(frozen=True)
class QueueSettings:
    max_tries: int = 3
    backoff_base: float = 2.0
    backoff_cap: float = 300.0
    max_retry_after: float = 300.0  # a `Retry-After` beyond this is cut to it, so a hostile site cannot park a source
    attempt_timeout: float = 60.0
    domain_concurrency: int = 2
    lease_ttl: float = 30.0
    requeue_delay: float = 5.0
    failure_threshold: int = 5
    domain_cooldown: float = 600.0

    @classmethod
    def from_env(cls) -> "QueueSettings":
        return from_env(cls)


async def create_queue_pool(settings: RedisSettings) -> ArqRedis:
    """The arq pool that enqueues onto our queue with our serializers."""
    return await create_pool(
        settings,
        default_queue_name=ARQ_OPTIONS["queue_name"],
        job_serializer=ARQ_OPTIONS["job_serializer"],
        job_deserializer=ARQ_OPTIONS["job_deserializer"],
    )


def job_function(settings: QueueSettings) -> Function:
    return func(
        execute_job,
        name="execute_job",
        max_tries=ARQ_MAX_TRIES,
        timeout=settings.attempt_timeout + ARQ_TIMEOUT_SLACK,
        keep_result=RESULT_TTL,
    )


async def execute_job(ctx: dict, source_id: str, domain: str, requested: bool = False) -> str:
    """Returns `ok`, `partial`, `failed`, `coalesced` or `skipped`; raises `Retry` to wait and try again."""
    lock = RunLock(ctx["redis"], source_id, ctx["job_id"])
    if not await lock.acquire(ctx["settings"].lease_ttl):
        return "coalesced"
    try:
        return await _run_locked(ctx, source_id, domain, requested, lock)
    except Retry:
        raise  # the lock stays held until the job's final outcome
    except ctx.get("retry_on", CONNECTION_ERRORS):
        # a lost PostgreSQL or Redis connection is not a collection failure, and arq ends a job for good on any
        # exception but `Retry`: run it again shortly, without using up an attempt
        logger.warning("lost a dependency during job %s, it will run again", ctx["job_id"], exc_info=True)
        await _requeue(lock, ctx["settings"], ctx["settings"].requeue_delay)
    except Exception:
        # the progress bar must not hang on a collector bug, and a failed finish must not keep the lock
        try:
            await _finish_failed(ctx, source_id, requested)
        except Exception:
            logger.exception("could not publish the failed finish of a crashed job")
        await lock.release()
        raise
    except asyncio.CancelledError:
        # shutdown: arq requeues the job under the same id, which re-enters its own lock; keep the lock so
        # no other job for the source slips in meanwhile
        cfg = ctx["settings"]
        try:
            await lock.extend(max(cfg.lease_ttl, cfg.attempt_timeout))
        except (RedisError, OSError):
            logger.warning("could not extend the run lock of a cancelled job", exc_info=True)
        raise
    except BaseException:
        await lock.release()
        raise


async def _run_locked(ctx: dict, source_id: str, domain: str, requested: bool, lock: RunLock) -> str:
    redis: ArqRedis = ctx["redis"]
    cfg: QueueSettings = ctx["settings"]
    job_id = ctx["job_id"]

    source = await ctx["sources"].get(source_id)
    if source is None or not source.collectable:
        await _finish_failed(ctx, source_id, requested)
        await lock.release()
        return "skipped"

    health = DomainHealth(redis, domain, threshold=cfg.failure_threshold, cooldown=cfg.domain_cooldown)
    if (wait := await health.wait_for()) > 0:
        await _requeue(lock, cfg, wait)
    semaphore = LeaseSemaphore(redis, domain, cfg.domain_concurrency)
    lease_id = f"{job_id}:{ctx['job_try']}"
    if not await semaphore.acquire(lease_id, cfg.lease_ttl):
        await _requeue(lock, cfg, cfg.requeue_delay)

    async def announce_start() -> None:
        # once per job: retries and the collector's own call share this marker
        if await redis.set(_started_key(job_id), 1, nx=True, ex=ATTEMPTS_KEY_TTL):
            await ctx["sources"].mark_running(source_id)
            await publish_scan_event(redis, "started", source_id)

    result = await _attempt(ctx["run_source"], source_id, announce_start, lock, semaphore, lease_id, cfg)

    if result.retry_after:  # any status: a 429 or a 503 tells every worker to leave the domain alone
        await health.defer(min(result.retry_after, cfg.max_retry_after))
    if result.deferral:
        await _requeue(lock, cfg, max(0.0, (result.deferral.until - datetime.now(UTC)).total_seconds()))
    attempts_key = f"{KEY_PREFIX}attempts:{job_id}"
    if result.error and is_transient(result.error.reason, result.http_status):
        failures = await redis.incr(attempts_key)
        await redis.expire(attempts_key, ATTEMPTS_KEY_TTL)
        if failures < cfg.max_tries:
            delay = backoff_delay(
                failures,
                base=cfg.backoff_base,
                cap=cfg.backoff_cap,
                retry_after=result.retry_after,
                rng=_rng,
                retry_after_cap=cfg.max_retry_after,
            )
            await _requeue(lock, cfg, delay)

    status = derive_status(documents=result.documents, errors=1 if result.error else 0)
    await health.record(ok=status != "failed")
    if result.error and not result.recorded:
        await ctx["record_error"](result.error)
    await announce_start()  # a collector that never announced still gets a start before the finish
    await _finish_if_started(ctx, source_id, status=status, documents=result.documents)
    await redis.delete(attempts_key)
    await lock.release()
    return status


def _started_key(job_id: str) -> str:
    return f"{KEY_PREFIX}started:{job_id}"


async def _finish_failed(ctx: dict, source_id: str, requested: bool) -> None:
    """End a job that cannot continue: a job that announced its start, or a requested one, ends `failed`."""
    if ctx.get("finished"):
        return  # the real outcome is out; a later error must not publish a second finish
    if await ctx["redis"].exists(_started_key(ctx["job_id"])):
        await _finish_if_started(ctx, source_id, status="failed", documents=0)
    elif requested:
        await publish_scan_event(ctx["redis"], "finished", source_id, documents=0, status="failed")


async def _finish_if_started(ctx: dict, source_id: str, *, status: str, documents: int) -> None:
    """Publish `scan.finished` and stamp the source, once, for a job that announced its start."""
    redis: ArqRedis = ctx["redis"]
    if not await redis.delete(_started_key(ctx["job_id"])):
        return
    try:
        if await ctx["sources"].get(source_id) is not None:
            await ctx["sources"].mark_finished(source_id, at=datetime.now(UTC), status=status)
    except Exception:
        # the marker is gone, so this is the only chance to end the progress bar
        logger.exception("could not stamp the source after its run")
    await publish_scan_event(redis, "finished", source_id, documents=documents, status=status)
    ctx["finished"] = True


async def _requeue(lock: RunLock, cfg: QueueSettings, delay: float) -> None:
    """Wait `delay` seconds and run again, keeping the lock alive across the wait.

    The grace after the due time covers a busy worker starting the retry late; a lock that expires
    first would let another job in and drop this one as coalesced.
    """
    await lock.extend(delay + max(cfg.lease_ttl, cfg.attempt_timeout))
    raise Retry(defer=delay)


async def _attempt(run_source, source_id, announce_start, lock: RunLock, semaphore: LeaseSemaphore, lease_id: str, cfg: QueueSettings):
    keeper = asyncio.create_task(_keep_alive(lock, semaphore, lease_id, cfg.lease_ttl))
    try:
        async with asyncio.timeout(cfg.attempt_timeout):
            return await run_source(source_id, announce_start)
    except TimeoutError:
        return AttemptResult(error=JobError(Reason.TIMEOUT, "attempt exceeded its timeout", source_id))
    finally:
        keeper.cancel()
        await asyncio.gather(keeper, return_exceptions=True)  # the keeper has stopped before the slot is released
        await semaphore.release(lease_id)


async def _keep_alive(lock: RunLock, semaphore: LeaseSemaphore, lease_id: str, ttl: float) -> None:
    while True:
        await asyncio.sleep(ttl / KEEP_ALIVE_DIVISOR)
        try:
            if not await lock.extend(ttl):
                logger.warning("run lock lost while the job was running")
            if not await semaphore.acquire(lease_id, ttl):
                logger.warning("concurrency lease lost while the job was running")
        except (RedisError, OSError):
            logger.warning("lock and lease renewal failed, will retry", exc_info=True)
