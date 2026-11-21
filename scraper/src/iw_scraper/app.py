"""Composition root: joins the queue, the collector, the ingest pipeline and the stores into the two processes.

`worker` runs the arq worker, the scan-request consumer and `/health`; `scheduler` enqueues due sources and runs
the republish sweep. Everything is configured from the environment (`config.py`, `.env.example`).
"""

import asyncio
import logging
import os
import signal
import time
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass

import asyncpg
from arq.connections import ArqRedis, RedisSettings, create_pool

from iw_scraper.collect import Collector
from iw_scraper.config import fetch_settings, proxy_settings, rate_limit_settings, target_settings
from iw_scraper.health import check_redis, serve_health
from iw_scraper.ingest.errors import record_error as store_job_error
from iw_scraper.ingest.pipeline import Ingestor
from iw_scraper.ingest.publisher import sweep
from iw_scraper.ingest.storage import Storage
from iw_scraper.jobs import QueueSettings
from iw_scraper.logs import configure_logging
from iw_scraper.pgstore import PgSourceStore
from iw_scraper.proxy import ProxyRotator
from iw_scraper.ratelimit import DomainLimiter
from iw_scraper.scan_requests import ScanRequestConsumer, consumer_name
from iw_scraper.scheduler import Scheduler
from iw_scraper.supervise import CONNECTION_ERRORS
from iw_scraper.targets import AddressGuard, UrlGuard
from iw_scraper.types import JobError
from iw_scraper.worker import RunnerSettings, run_consumer, run_worker

logger = logging.getLogger(__name__)

# a lost PostgreSQL connection is retried like a lost Redis one; anything else is a bug and ends the process
RETRY_ON = (
    *CONNECTION_ERRORS,
    asyncpg.exceptions.PostgresConnectionError,
    asyncpg.exceptions.CannotConnectNowError,
    asyncpg.InterfaceError,
)
HOSTS_TTL_SECONDS = 60.0


@dataclass(frozen=True)
class Runtime:
    pool: asyncpg.Pool
    storage: Storage
    redis: ArqRedis
    store: PgSourceStore
    collector: Collector

    async def record_error(self, error: JobError) -> None:
        await store_job_error(self.pool, error)


def allowed_urls(
    store: PgSourceStore, extra_hosts, ports, *, ttl: float = HOSTS_TTL_SECONDS, clock=time.monotonic
) -> Callable[[], Awaitable[UrlGuard]]:
    """The URL guard for a run: the hosts of every collectable source (so a source added in the dashboard
    applies within `ttl` seconds) plus the configured extras. Cached, so a run does not query for it."""
    cached: tuple[float, UrlGuard] | None = None

    async def current() -> UrlGuard:
        nonlocal cached
        if cached is None or clock() - cached[0] >= ttl:
            cached = (clock(), UrlGuard.for_sources(await store.collectable(), extra_hosts, ports))
        return cached[1]

    return current


def assemble(
    pool: asyncpg.Pool,
    storage: Storage,
    redis: ArqRedis,
    *,
    urls: Callable[[], Awaitable[UrlGuard]],
    addresses: AddressGuard,
    rotator: ProxyRotator,
    limiter,
    timeout: float,
    max_bytes: int,
) -> Runtime:
    store = PgSourceStore(pool)
    collector = Collector(
        store, Ingestor(pool, storage, redis),
        urls=urls, addresses=addresses, rotator=rotator, limiter=limiter, timeout=timeout, max_bytes=max_bytes,
    )
    return Runtime(pool, storage, redis, store, collector)


@asynccontextmanager
async def runtime(redis_url: str):
    """Open the real stores from the environment, build the collector, close everything afterwards."""
    pool = await asyncpg.create_pool(os.environ["DATABASE_URL"], min_size=1, max_size=5)
    try:
        storage = Storage(
            os.environ["MINIO_ENDPOINT"],
            os.environ["MINIO_ACCESS_KEY"],
            os.environ["MINIO_SECRET_KEY"],
            bucket=os.environ.get("MINIO_BUCKET", "iw-raw"),
            secure=os.environ.get("MINIO_SECURE", "false").lower() == "true",
        )
        await storage.check_bucket()
        redis = await create_pool(RedisSettings.from_dsn(redis_url))
        try:
            proxies, mode, cooldown = proxy_settings()
            ports, internal_hosts, extra_hosts = target_settings()
            _, interval = rate_limit_settings()
            timeout, max_bytes = fetch_settings()
            store = PgSourceStore(pool)
            yield assemble(
                pool, storage, redis,
                urls=allowed_urls(store, extra_hosts, ports),
                addresses=AddressGuard(internal_hosts=internal_hosts),
                rotator=ProxyRotator(proxies, mode, cooldown),
                limiter=DomainLimiter(redis, interval),
                timeout=timeout, max_bytes=max_bytes,
            )
        finally:
            await redis.aclose()
    finally:
        await pool.close()


async def _run_together(stop: asyncio.Event, *coroutines) -> None:
    """Run the parts of one process; when one ends with an error, stop the others (they drain) and raise it, so
    the stores are never closed under a part that is still working."""
    tasks = [asyncio.create_task(coroutine) for coroutine in coroutines]
    done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_EXCEPTION)
    stop.set()
    results = await asyncio.gather(*tasks, return_exceptions=True)
    for result in results:
        if isinstance(result, BaseException) and not isinstance(result, asyncio.CancelledError):
            raise result


async def run_worker_process(stop: asyncio.Event) -> None:
    runner = RunnerSettings.from_env()
    queue = QueueSettings.from_env()
    async with runtime(runner.redis_url) as rt:
        checks = {
            "redis": lambda: check_redis(rt.redis),
            "postgres": lambda: rt.pool.fetchval("SELECT 1"),
            "minio": rt.storage.check_bucket,
        }
        health = await serve_health(checks, host=runner.health_host, port=runner.health_port)
        ctx = {"sources": rt.store, "run_source": rt.collector.run_source, "record_error": rt.record_error}
        consumer = ScanRequestConsumer(rt.redis, rt.store, rt.record_error, consumer=consumer_name())
        try:
            await _run_together(
                stop,
                run_worker(ctx, queue, runner, stop=stop, retry_on=RETRY_ON),
                run_consumer(consumer, runner, stop=stop, retry_on=RETRY_ON),
            )
        finally:
            health.close()


async def run_scheduler_process(stop: asyncio.Event) -> None:
    runner = RunnerSettings.from_env()
    async with runtime(runner.redis_url) as rt:
        async def republish() -> None:
            await sweep(rt.pool, rt.redis)

        scheduler = asyncio.create_task(Scheduler(rt.redis, rt.store, rt.record_error, sweep=republish).run())
        await stop.wait()
        scheduler.cancel()
        await asyncio.gather(scheduler, return_exceptions=True)


def main(role: str) -> None:
    runners = {"worker": run_worker_process, "scheduler": run_scheduler_process}
    if role not in runners:
        raise SystemExit(f"usage: python -m iw_scraper {'|'.join(runners)}")
    configure_logging()

    async def run() -> None:
        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for name in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(name, stop.set)
        await runners[role](stop)

    try:
        asyncio.run(run())
    except Exception as error:  # startup or a crashed part: one redacted JSON line, then a non-zero exit
        logger.exception("%s stopped: %s", role, type(error).__name__)
        raise SystemExit(1) from None
