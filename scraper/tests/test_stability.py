import asyncio
import os

import pytest
from arq.jobs import JobStatus

from conftest import Recorder, fast_settings
from iw_scraper.jobs import AttemptResult
from iw_scraper.worker import RunnerSettings, run_worker

SRC = "88888888-8888-4888-8888-888888888888"
DOMAIN = "example.test"
LOCK_KEY = f"iw:lock:{SRC}"


@pytest.fixture
async def start_runner(store):
    """Run the supervised worker like the process does; tests stop it through the `stop` event."""
    running: list[tuple[asyncio.Task, asyncio.Event]] = []

    def start(run_source, *, deadline=5.0, max_jobs=10, url=None, queue=None):
        stop = asyncio.Event()
        ctx = {"run_source": run_source, "record_error": Recorder().record_error, "sources": store}
        runner = RunnerSettings(
            redis_url=url or os.environ["REDIS_URL"],
            max_jobs=max_jobs,
            shutdown_deadline=deadline,
            reconnect_base=0.1,
            reconnect_cap=0.5,
            poll_delay=0.02,
        )
        task = asyncio.create_task(run_worker(ctx, queue or fast_settings(), runner, stop=stop))
        running.append((task, stop))
        return task, stop

    yield start
    for task, stop in running:
        stop.set()
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def test_sigterm_lets_a_running_job_finish_within_the_deadline(redis, start_runner):
    began = asyncio.Event()

    async def run_source(source_id, started=None):
        began.set()
        await asyncio.sleep(0.5)
        return AttemptResult(documents=1)

    task, stop = start_runner(run_source, deadline=10.0)
    job = await redis.enqueue_job("execute_job", SRC, DOMAIN, False, _job_id="job-1")
    await asyncio.wait_for(began.wait(), 5)
    stop.set()
    await asyncio.wait_for(task, 10)

    assert await job.result(timeout=2, poll_delay=0.05) == "ok"


async def test_sigterm_requeues_a_job_that_outlives_the_deadline_and_another_worker_finishes_it(
    redis, start_runner, events
):
    began = asyncio.Event()

    async def stuck(source_id, started):
        await started()
        began.set()
        await asyncio.sleep(60)

    first, stop = start_runner(stuck, deadline=0.3)
    job = await redis.enqueue_job("execute_job", SRC, DOMAIN, False, _job_id="job-1")
    await asyncio.wait_for(began.wait(), 5)
    stop.set()
    await asyncio.wait_for(first, 10)

    assert await job.status() == JobStatus.queued
    await asyncio.sleep(1.3)  # longer than the lock's own lease: it was extended for the requeue
    assert await redis.get(LOCK_KEY) == b"job-1"  # kept for the requeued job, not freed for another one

    ran = []

    async def quick(source_id, started=None):
        ran.append(source_id)
        return AttemptResult(documents=1)

    start_runner(quick)

    assert await job.result(timeout=10, poll_delay=0.05) == "ok"
    await asyncio.sleep(0.3)
    assert ran == [SRC]
    assert [e["type"] for e in events] == ["scan.started", "scan.finished"]


async def test_a_stopping_worker_takes_no_new_jobs_and_none_are_lost(redis, start_runner):
    began = asyncio.Event()
    ran = []

    async def run_source(source_id, started=None):
        ran.append(source_id)
        began.set()
        await asyncio.sleep(0.5)
        return AttemptResult(documents=1)

    other = "99999999-9999-4999-8999-999999999999"
    task, stop = start_runner(run_source, deadline=10.0, max_jobs=1)
    first = await redis.enqueue_job("execute_job", SRC, "a.test", False, _job_id="j1")
    second = await redis.enqueue_job("execute_job", other, "b.test", False, _job_id="j2")
    await asyncio.wait_for(began.wait(), 5)
    stop.set()
    await asyncio.wait_for(task, 10)

    assert await first.result(timeout=2, poll_delay=0.05) == "ok"
    assert await second.status() == JobStatus.queued
    start_runner(run_source, max_jobs=1)
    assert await second.result(timeout=10, poll_delay=0.05) == "ok"


async def test_a_job_that_times_out_through_all_its_retries_frees_its_lock_and_slot(redis, start_runner):
    async def run_source(source_id, started=None):
        await asyncio.sleep(30)

    start_runner(run_source, queue=fast_settings(max_tries=2, attempt_timeout=0.1))
    job = await redis.enqueue_job("execute_job", SRC, DOMAIN, False, _job_id="job-1")

    assert await job.result(timeout=10, poll_delay=0.05) == "failed"
    assert await redis.exists(LOCK_KEY) == 0
    assert await redis.zcard(f"iw:sem:{DOMAIN}") == 0


async def test_the_worker_survives_a_redis_outage_and_resumes_when_it_returns(redis, start_runner, proxy):
    async def run_source(source_id, started=None):
        return AttemptResult(documents=1)

    task, _ = start_runner(run_source, url=proxy.url)
    first = await redis.enqueue_job("execute_job", SRC, DOMAIN, False, _job_id="job-1")
    assert await first.result(timeout=10, poll_delay=0.05) == "ok"

    await proxy.stop()
    await asyncio.sleep(1.5)
    during = await redis.enqueue_job("execute_job", SRC, DOMAIN, False, _job_id="job-2")
    assert not task.done()
    await proxy.start()

    assert await during.result(timeout=30, poll_delay=0.1) == "ok"
    assert not task.done()


async def test_the_requeue_is_not_interrupted_by_the_close_that_follows_the_deadline(redis, start_runner, monkeypatch):
    from iw_scraper.guards import RunLock

    real_extend = RunLock.extend

    async def slow_extend(self, ttl):
        await asyncio.sleep(0.4)
        print('EXTEND slept', flush=True)  # a slow Redis: the cancelled job is still extending its lock when close() runs
        return await real_extend(self, ttl)

    began = asyncio.Event()

    async def stuck(source_id, started):
        began.set()
        await asyncio.sleep(60)

    first, stop = start_runner(stuck, deadline=0.3)
    await redis.enqueue_job("execute_job", SRC, DOMAIN, False, _job_id="job-1")
    await asyncio.wait_for(began.wait(), 5)
    monkeypatch.setattr(RunLock, "extend", slow_extend)
    stop.set()
    await asyncio.wait_for(first, 10)
    await asyncio.sleep(1.3)

    assert await redis.get(LOCK_KEY) == b"job-1"


async def test_a_worker_that_stops_without_being_asked_is_restarted(redis, start_runner, monkeypatch):
    from arq.worker import Worker

    real = Worker.async_run
    lives = []

    async def stops_at_once_the_first_time(self):
        lives.append(1)
        if len(lives) == 1:
            return
        await real(self)

    monkeypatch.setattr(Worker, "async_run", stops_at_once_the_first_time)

    async def run_source(source_id, started=None):
        return AttemptResult(documents=1)

    task, _ = start_runner(run_source)
    job = await redis.enqueue_job("execute_job", SRC, DOMAIN, False, _job_id="job-1")

    assert await job.result(timeout=15, poll_delay=0.05) == "ok"
    assert len(lives) == 2
    assert not task.done()


async def test_cancelling_the_runner_itself_is_not_swallowed(redis, start_runner):
    async def run_source(source_id, started=None):
        return AttemptResult(documents=1)

    task, _ = start_runner(run_source)
    await asyncio.sleep(0.5)
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)

    assert task.cancelled()


async def test_the_consumer_loop_handles_requests_until_stopped(redis, store):
    from iw_scraper.scan_requests import ScanRequestConsumer
    from iw_scraper.worker import run_consumer

    consumer = ScanRequestConsumer(redis, store, Recorder().record_error, consumer="w1", claim_idle=5.0)
    runner = RunnerSettings(redis_url=os.environ["REDIS_URL"], consumer_block=0.1, reconnect_base=0.1, reconnect_cap=0.5)
    stop = asyncio.Event()
    task = asyncio.create_task(run_consumer(consumer, runner, stop=stop))
    await asyncio.sleep(0.3)
    await redis.xadd("iw:scan-requests", {"source_id": SRC, "requested_at": "2026-11-21T10:00:00Z"})
    for _ in range(100):
        if await redis.zcard("arq:queue"):
            break
        await asyncio.sleep(0.05)
    stop.set()
    await asyncio.wait_for(task, 5)

    assert await redis.zcard("arq:queue") == 1


async def test_closing_a_worker_whose_redis_is_a_black_hole_gives_up_after_the_close_timeout(monkeypatch):
    import iw_scraper.worker as module

    monkeypatch.setattr(module, "CLOSE_TIMEOUT", 0.2)

    class Hung:
        def __init__(self):
            self.tasks = {"job": asyncio.ensure_future(asyncio.sleep(60))}

        async def close(self):
            await asyncio.sleep(60)

    worker = Hung()
    started = asyncio.get_running_loop().time()
    await asyncio.wait_for(module._close(worker), 2)
    worker.tasks["job"].cancel()

    assert asyncio.get_running_loop().time() - started < 1
