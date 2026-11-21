import asyncio

from conftest import Recorder, fast_settings
from iw_scraper.guards import RunLock
from iw_scraper.jobs import AttemptResult
from iw_scraper.types import JobError, Reason

SRC = "22222222-2222-4222-8222-222222222222"
DOMAIN = "example.test"
LOCK_KEY = f"iw:lock:{SRC}"


async def test_overlapping_jobs_for_one_source_coalesce(redis, start_worker):
    release, calls = asyncio.Event(), []

    async def run_source(source_id):
        calls.append(source_id)
        await release.wait()
        return AttemptResult(documents=1)

    recorder = Recorder()
    start_worker(run_source, recorder, fast_settings())
    first = await redis.enqueue_job("execute_job", SRC, DOMAIN, _job_id="a")
    await asyncio.sleep(0.2)
    second = await redis.enqueue_job("execute_job", SRC, DOMAIN, _job_id="b")

    assert await second.result(timeout=5, poll_delay=0.05) == "coalesced"
    release.set()
    assert await first.result(timeout=5, poll_delay=0.05) == "ok"
    assert (calls, recorder.errors) == ([SRC], [])


async def test_lock_is_held_while_a_job_waits_out_its_retry_backoff(redis, start_worker):
    calls = []

    async def run_source(source_id):
        calls.append(1)
        if len(calls) == 1:
            return AttemptResult(error=JobError(Reason.HTTP_ERROR, "x", SRC), http_status=503, retry_after=0.8)
        return AttemptResult(documents=1)

    start_worker(run_source, Recorder(), fast_settings(lease_ttl=0.3))
    first = await redis.enqueue_job("execute_job", SRC, DOMAIN, _job_id="a")
    await asyncio.sleep(0.5)
    second = await redis.enqueue_job("execute_job", SRC, DOMAIN, _job_id="b")

    assert await second.result(timeout=5, poll_delay=0.05) == "coalesced"
    assert await first.result(timeout=10, poll_delay=0.05) == "ok"
    assert len(calls) == 2


async def test_lock_is_renewed_while_the_job_lives_longer_than_its_ttl(redis, start_worker):
    release, calls = asyncio.Event(), []

    async def run_source(source_id):
        calls.append(1)
        await release.wait()
        return AttemptResult(documents=1)

    start_worker(run_source, Recorder(), fast_settings(lease_ttl=0.3))
    first = await redis.enqueue_job("execute_job", SRC, DOMAIN, _job_id="a")
    await asyncio.sleep(0.9)
    second = await redis.enqueue_job("execute_job", SRC, DOMAIN, _job_id="b")

    assert await second.result(timeout=5, poll_delay=0.05) == "coalesced"
    release.set()
    await first.result(timeout=5, poll_delay=0.05)
    assert len(calls) == 1


async def test_lock_is_released_after_the_final_outcome(redis, start_worker):
    async def run_source(source_id):
        return AttemptResult(error=JobError(Reason.BLOCKED, "x", SRC))

    start_worker(run_source, Recorder(), fast_settings())
    job = await redis.enqueue_job("execute_job", SRC, DOMAIN, _job_id="a")
    await job.result(timeout=5, poll_delay=0.05)

    assert await redis.exists(LOCK_KEY) == 0


async def test_lock_is_released_when_the_run_raises(redis, start_worker):
    async def run_source(source_id):
        raise RuntimeError("boom")

    start_worker(run_source, Recorder(), fast_settings())
    job = await redis.enqueue_job("execute_job", SRC, DOMAIN, _job_id="a")
    try:
        await job.result(timeout=5, poll_delay=0.05)
    except RuntimeError:
        pass

    assert await redis.exists(LOCK_KEY) == 0


async def test_a_stale_lock_from_a_crashed_worker_expires_and_the_next_job_runs(redis, start_worker):
    calls = []

    async def run_source(source_id):
        calls.append(1)
        return AttemptResult(documents=1)

    await redis.set(LOCK_KEY, "dead-job", px=400)
    start_worker(run_source, Recorder(), fast_settings())

    early = await redis.enqueue_job("execute_job", SRC, DOMAIN, _job_id="a")
    assert await early.result(timeout=5, poll_delay=0.05) == "coalesced"
    await asyncio.sleep(0.5)
    later = await redis.enqueue_job("execute_job", SRC, DOMAIN, _job_id="b")

    assert await later.result(timeout=5, poll_delay=0.05) == "ok"
    assert len(calls) == 1


async def test_only_the_owner_can_release_the_lock(redis):
    mine, other = RunLock(redis, SRC, "mine"), RunLock(redis, SRC, "other")
    assert await mine.acquire(ttl=30) is True

    await other.release()

    assert await redis.get(LOCK_KEY) == b"mine"
    assert await other.acquire(ttl=30) is False


async def test_a_non_owner_cannot_extend_the_lock(redis):
    await redis.set(LOCK_KEY, "someone", px=200)

    assert await RunLock(redis, SRC, "me").extend(ttl=30) is False

    assert await redis.pttl(LOCK_KEY) <= 200
