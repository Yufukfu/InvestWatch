"""Keep a long-running loop alive through dependency outages without hiding real bugs."""

import asyncio
import logging
import random
import time
from collections.abc import Awaitable, Callable

from redis.exceptions import BusyLoadingError
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError

from iw_scraper.retry import backoff_delay

logger = logging.getLogger(__name__)
_rng = random.Random()

# Lost-connection errors only. A ResponseError (WRONGTYPE, ...) is a bug and must not be retried forever.
CONNECTION_ERRORS: tuple[type[BaseException], ...] = (RedisConnectionError, RedisTimeoutError, BusyLoadingError, OSError)


async def supervise(
    factory: Callable[[], Awaitable[None]],
    *,
    name: str,
    stop: asyncio.Event,
    base: float,
    cap: float,
    retry_on: tuple[type[BaseException], ...] = CONNECTION_ERRORS,
) -> None:
    """Run `factory()` until it returns or `stop` is set.

    A lost connection (`retry_on`: Redis and the network by default; the PostgreSQL store adds its own
    errors) is retried with exponential backoff and jitter; any other exception is a bug and ends the
    supervisor, so the process exits instead of looping on it.
    """
    failures = 0
    while not stop.is_set():
        started = time.monotonic()
        try:
            await factory()
            return
        except retry_on:
            if time.monotonic() - started > cap:
                failures = 0  # it ran for a while: this is a new outage, not the same one
            failures += 1
            delay = backoff_delay(failures, base=base, cap=cap, retry_after=None, rng=_rng)
            logger.warning("%s lost its connection, retrying in %.1fs", name, delay, exc_info=True)
            await _wait(stop, delay)


async def run_until_stopped(factory: Callable[[], Awaitable[None]], *, stop: asyncio.Event) -> None:
    """Run `factory()` and cancel it as soon as `stop` is set."""
    work = asyncio.create_task(factory())
    stopper = asyncio.create_task(stop.wait())
    try:
        await asyncio.wait({work, stopper}, return_when=asyncio.FIRST_COMPLETED)
    finally:
        stopper.cancel()
        if not work.done():
            work.cancel()
        await asyncio.gather(work, stopper, return_exceptions=True)
    if work.done() and not work.cancelled() and work.exception():
        raise work.exception()


async def _wait(stop: asyncio.Event, seconds: float) -> None:
    try:
        await asyncio.wait_for(stop.wait(), seconds)
    except TimeoutError:
        pass
