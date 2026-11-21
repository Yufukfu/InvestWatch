import asyncio
import time

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError

from iw_scraper.supervise import run_until_stopped, supervise


async def until(condition, timeout=5.0):
    deadline = time.monotonic() + timeout
    while not condition():
        assert time.monotonic() < deadline, "condition not reached in time"
        await asyncio.sleep(0.02)


async def test_a_connection_failure_is_retried_with_growing_delays_until_it_works():
    stamps = []

    async def factory():
        stamps.append(time.monotonic())
        if len(stamps) < 4:
            raise RedisConnectionError("down")

    stop = asyncio.Event()
    task = asyncio.create_task(supervise(factory, name="t", stop=stop, base=0.1, cap=5.0))
    await until(lambda: len(stamps) >= 4)
    stop.set()
    await asyncio.wait_for(task, 2)

    gaps = [b - a for a, b in zip(stamps, stamps[1:])]
    assert gaps[0] >= 0.05 and gaps[2] >= 0.2


async def test_an_os_error_is_retried_too():
    calls = []

    async def factory():
        calls.append(1)
        if len(calls) == 1:
            raise OSError("connection refused")

    stop = asyncio.Event()
    task = asyncio.create_task(supervise(factory, name="t", stop=stop, base=0.05, cap=0.5))
    await until(lambda: len(calls) >= 2)
    stop.set()
    await asyncio.wait_for(task, 2)


async def test_a_redis_response_error_is_a_bug_and_is_not_retried():
    from redis.exceptions import ResponseError

    async def factory():
        raise ResponseError("WRONGTYPE Operation against a key holding the wrong kind of value")

    with pytest.raises(ResponseError):
        await asyncio.wait_for(supervise(factory, name="t", stop=asyncio.Event(), base=0.05, cap=0.5), 2)


async def test_the_error_types_to_retry_can_be_extended_for_another_dependency():
    class DatabaseDown(Exception):
        pass

    calls = []

    async def factory():
        calls.append(1)
        if len(calls) == 1:
            raise DatabaseDown()

    await asyncio.wait_for(
        supervise(factory, name="t", stop=asyncio.Event(), base=0.05, cap=0.5, retry_on=(DatabaseDown,)), 3
    )

    assert len(calls) == 2


async def test_any_other_exception_ends_the_supervisor_instead_of_looping():
    async def factory():
        raise ValueError("a bug")

    with pytest.raises(ValueError):
        await supervise(factory, name="t", stop=asyncio.Event(), base=0.05, cap=0.5)


async def test_setting_stop_during_a_backoff_wait_ends_it_at_once():
    async def factory():
        raise RedisConnectionError("down")

    stop = asyncio.Event()
    task = asyncio.create_task(supervise(factory, name="t", stop=stop, base=30.0, cap=30.0))
    await asyncio.sleep(0.2)
    started = time.monotonic()
    stop.set()
    await asyncio.wait_for(task, 2)

    assert time.monotonic() - started < 1


async def test_run_until_stopped_cancels_the_coroutine_when_stop_is_set():
    cancelled = []

    async def forever():
        try:
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            cancelled.append(1)
            raise

    stop = asyncio.Event()
    task = asyncio.create_task(run_until_stopped(forever, stop=stop))
    await asyncio.sleep(0.1)
    stop.set()
    await asyncio.wait_for(task, 2)

    assert cancelled == [1]


async def test_it_returns_when_the_work_returns():
    calls = []

    async def factory():
        calls.append(1)
        await asyncio.sleep(0)

    await asyncio.wait_for(supervise(factory, name="t", stop=asyncio.Event(), base=0.05, cap=0.5), 2)

    assert calls == [1]


async def test_the_backoff_starts_over_after_a_long_healthy_run(monkeypatch):
    import iw_scraper.supervise as module

    class Top:
        def uniform(self, low, high):
            return high

    monkeypatch.setattr(module, "_rng", Top())
    stamps = []

    async def factory():
        stamps.append(time.monotonic())
        if len(stamps) == 1:
            raise RedisConnectionError("first outage")
        if len(stamps) == 2:
            await asyncio.sleep(0.4)  # healthy for longer than the cap
            raise RedisConnectionError("a new outage")

    stop = asyncio.Event()
    task = asyncio.create_task(supervise(factory, name="t", stop=stop, base=0.2, cap=0.3))
    await until(lambda: len(stamps) >= 3)
    stop.set()
    await asyncio.wait_for(task, 2)

    assert stamps[2] - (stamps[1] + 0.4) < 0.27  # the first-failure delay (0.2 s), not the second's (0.3 s)


async def test_run_until_stopped_raises_what_the_work_raised():
    async def broken():
        raise ValueError("a bug")

    with pytest.raises(ValueError):
        await run_until_stopped(broken, stop=asyncio.Event())
