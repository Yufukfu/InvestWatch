import asyncio
from datetime import UTC, datetime

from conftest import Recorder, make_source
from iw_scraper.scheduler import Scheduler
from iw_scraper.types import Reason

A = "55555555-5555-4555-8555-555555555555"
B = "66666666-6666-4666-8666-666666666666"
SLOT = datetime(2026, 11, 21, 12, 5, 20, tzinfo=UTC)


def scheduler(redis, store, recorder=None, **kwargs):
    return Scheduler(redis, store, (recorder or Recorder()).record_error, **kwargs)


async def queued(redis) -> int:
    return await redis.zcard("arq:queue")


async def test_a_due_source_gets_one_job(redis, store):
    store.sources[A] = make_source(A, cron="*/5 * * * *")

    assert await scheduler(redis, store).tick(SLOT) == 1
    assert await queued(redis) == 1


async def test_a_source_that_is_not_due_gets_none(redis, store):
    store.sources[A] = make_source(A, cron="*/5 * * * *")

    await scheduler(redis, store).tick(SLOT.replace(minute=6))

    assert await queued(redis) == 0


async def test_two_schedulers_enqueue_a_due_job_exactly_once(redis, store):
    store.sources[A] = make_source(A, cron="*/5 * * * *")

    enqueued = await asyncio.gather(scheduler(redis, store).tick(SLOT), scheduler(redis, store).tick(SLOT))

    assert (await queued(redis), sum(enqueued)) == (1, 1)


async def test_the_next_slot_gets_its_own_job(redis, store):
    store.sources[A] = make_source(A, cron="* * * * *")
    s = scheduler(redis, store)

    await s.tick(SLOT)
    await s.tick(SLOT.replace(minute=6))

    assert await queued(redis) == 2


async def test_manual_only_inactive_and_non_web_sources_are_not_scheduled(redis, store):
    store.sources[A] = make_source(A, cron=None)
    store.sources[B] = make_source(B, cron="* * * * *", active=False)
    store.sources["77777777-7777-4777-8777-777777777777"] = make_source(
        "77777777-7777-4777-8777-777777777777", cron="* * * * *", platform="facebook"
    )

    await scheduler(redis, store).tick(SLOT)

    assert await queued(redis) == 0


async def test_an_edited_cron_applies_on_the_next_tick(redis, store):
    store.sources[A] = make_source(A, cron="0 3 * * *")
    s = scheduler(redis, store)
    await s.tick(SLOT)
    assert await queued(redis) == 0

    store.sources[A] = make_source(A, cron="*/5 * * * *")
    await s.tick(SLOT.replace(minute=10))

    assert await queued(redis) == 1


async def test_an_invalid_cron_is_recorded_once_and_not_scheduled(redis, store):
    store.sources[A] = make_source(A, cron="not a cron")
    recorder = Recorder()
    s = scheduler(redis, store, recorder)

    await s.tick(SLOT)
    await s.tick(SLOT.replace(minute=6))
    await scheduler(redis, store, recorder).tick(SLOT.replace(minute=7))

    assert [(e.reason, e.source_id) for e in recorder.errors] == [(Reason.INVALID_REQUEST, A)]
    assert await queued(redis) == 0


async def test_a_fixed_cron_is_scheduled_and_a_new_invalid_value_is_recorded_again(redis, store):
    store.sources[A] = make_source(A, cron="nope")
    recorder = Recorder()
    s = scheduler(redis, store, recorder)
    await s.tick(SLOT)

    store.sources[A] = make_source(A, cron="*/5 * * * *")
    await s.tick(SLOT.replace(minute=10))
    store.sources[A] = make_source(A, cron="nope")
    await s.tick(SLOT.replace(minute=11))

    assert len(recorder.errors) == 2
    assert await queued(redis) == 1


async def test_a_slot_missed_by_a_late_tick_is_still_enqueued(redis, store):
    store.sources[A] = make_source(A, cron="*/5 * * * *")
    s = scheduler(redis, store)
    await s.tick(SLOT.replace(minute=4, second=59))

    await s.tick(SLOT.replace(minute=6, second=0))

    assert await queued(redis) == 1


async def test_the_sweep_runs_on_its_interval_without_a_trigger(redis, store):
    sweeps = []

    async def sweep():
        sweeps.append(1)

    s = scheduler(redis, store, sweep=sweep, tick_interval=0.05, sweep_interval=0.15)
    task = asyncio.create_task(s.run())
    await asyncio.sleep(0.8)
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)

    assert len(sweeps) >= 3


async def test_a_long_gap_replays_only_the_last_few_minutes(redis, store):
    store.sources[A] = make_source(A, cron="* * * * *")
    s = scheduler(redis, store)
    await s.tick(SLOT)

    await s.tick(SLOT.replace(hour=15))

    assert await queued(redis) == 1 + 5


async def test_a_failing_tick_does_not_stop_the_loop(redis, store):
    sweeps, calls = [], []

    async def sweep():
        sweeps.append(1)

    class FlakyStore:
        async def schedulable(self):
            calls.append(1)
            if len(calls) == 1:
                raise ConnectionError("database restarting")
            return []

    s = scheduler(redis, FlakyStore(), sweep=sweep, tick_interval=0.05, sweep_interval=0.05)
    task = asyncio.create_task(s.run())
    await asyncio.sleep(0.5)
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)

    assert len(calls) > 2 and len(sweeps) >= 2


async def test_a_tick_that_fails_midway_is_caught_up_by_the_next_one(redis, store):
    store.sources[A] = make_source(A, cron="*/5 * * * *")
    real_schedulable, failures = store.schedulable, []

    async def flaky():
        if not failures:
            failures.append(1)
            raise ConnectionError("database restarting")
        return await real_schedulable()

    store.schedulable = flaky
    s = scheduler(redis, store)
    try:
        await s.tick(SLOT)
    except ConnectionError:
        pass

    await s.tick(SLOT.replace(minute=6))

    assert await queued(redis) == 1


async def test_a_non_utc_clock_is_converted_to_utc_slots(redis, store):
    from datetime import timedelta, timezone

    store.sources[A] = make_source(A, cron="5 12 * * *")
    warsaw = timezone(timedelta(hours=1))

    await scheduler(redis, store).tick(datetime(2026, 11, 21, 13, 5, 20, tzinfo=warsaw))

    assert await queued(redis) == 1
    assert [j.decode() for j in await redis.zrange("arq:queue", 0, -1)] == [f"sched-{A}-20261121T1205Z"]


async def test_a_failing_sweep_does_not_stop_ticks_and_a_failing_tick_does_not_stop_the_sweep(redis, store):
    ticks, sweeps = [], []

    async def broken_sweep():
        sweeps.append(1)
        raise ConnectionError("sweep failed")

    class BrokenStore:
        async def schedulable(self):
            ticks.append(1)
            raise ConnectionError("database down")

    s = scheduler(redis, BrokenStore(), sweep=broken_sweep, tick_interval=0.05, sweep_interval=0.05)
    task = asyncio.create_task(s.run())
    await asyncio.sleep(0.5)
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)

    assert len(ticks) > 2 and len(sweeps) > 2
