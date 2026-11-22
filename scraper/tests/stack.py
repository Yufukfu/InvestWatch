"""A running stack for the end-to-end tests: the production wiring of `app.py` on the test services, one
consumer and one arq worker per `workers`, stopped and cleaned up afterwards."""

import asyncio
import os
from contextlib import asynccontextmanager

from arq.connections import RedisSettings

from conftest import fast_settings
from iw_scraper.jobs import create_queue_pool
from iw_scraper.app import RETRY_ON, assemble
from iw_scraper.proxy import ProxyRotator
from iw_scraper.ratelimit import DomainLimiter
from iw_scraper.scan_requests import ScanRequestConsumer
from iw_scraper.worker import RunnerSettings, run_consumer, run_worker


class LoopbackAddresses:
    """Stands in for `AddressGuard`: the stub is on loopback, which the real guard refuses."""

    async def check(self, host: str) -> str:
        return "127.0.0.1"


async def wait_for(condition, timeout=20.0):
    deadline = asyncio.get_running_loop().time() + timeout
    while not await condition():
        if asyncio.get_running_loop().time() > deadline:
            raise AssertionError("condition not met in time")
        await asyncio.sleep(0.05)


@asynccontextmanager
async def stack(pool, storage, *, urls, addresses, workers=1, stages=None, renderer=None):
    redis_url = os.environ["IW_TEST_REDIS_URL"]
    redis = await create_queue_pool(RedisSettings.from_dsn(redis_url))
    await redis.flushdb()
    rt = assemble(
        pool, storage, redis, urls=urls, addresses=addresses, rotator=ProxyRotator([], "per_request", 90.0),
        limiter=DomainLimiter(redis, 0.05), timeout=10.0, max_bytes=5 * 1024 * 1024,
        stages=stages, renderer=renderer,
    )
    runner = RunnerSettings(redis_url=redis_url, poll_delay=0.05, consumer_block=0.2, shutdown_deadline=5.0)
    queue = fast_settings(attempt_timeout=20.0, lease_ttl=5.0)
    ctx = {"sources": rt.store, "run_source": rt.collector.run_source, "record_error": rt.record_error}
    stop = asyncio.Event()
    tasks = []
    for number in range(workers):
        consumer = ScanRequestConsumer(rt.redis, rt.store, rt.record_error, consumer=f"test-{number}", retry_on=RETRY_ON)
        tasks += [
            asyncio.create_task(run_worker(ctx, queue, runner, stop=stop, retry_on=RETRY_ON)),
            asyncio.create_task(run_consumer(consumer, runner, stop=stop, retry_on=RETRY_ON)),
        ]
    try:
        yield rt
    finally:
        stop.set()
        await asyncio.wait(tasks, timeout=15)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await redis.flushdb()
        await redis.aclose()
