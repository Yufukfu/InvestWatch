import asyncio

from conftest import Recorder, fast_settings
from iw_scraper.guards import LeaseSemaphore
from iw_scraper.jobs import AttemptResult

DOMAIN = "example.test"


def sources(n):
    return [f"00000000-0000-4000-8000-{i:012d}" for i in range(n)]


class Gauge:
    def __init__(self):
        self.running = 0
        self.peak = 0

    async def run_source(self, source_id, started=None):
        self.running += 1
        self.peak = max(self.peak, self.running)
        await asyncio.sleep(0.15)
        self.running -= 1
        return AttemptResult(documents=1)


async def test_at_most_the_cap_run_at_once_across_two_workers(redis, start_worker):
    gauge, recorder = Gauge(), Recorder()
    settings = fast_settings(domain_concurrency=2)
    start_worker(gauge.run_source, recorder, settings)
    start_worker(gauge.run_source, recorder, settings)

    jobs = [await redis.enqueue_job("execute_job", s, DOMAIN, _job_id=f"j{i}") for i, s in enumerate(sources(8))]
    results = [await j.result(timeout=15, poll_delay=0.05) for j in jobs]

    assert results == ["ok"] * 8
    assert gauge.peak == 2


async def test_different_domains_do_not_share_a_cap(redis, start_worker):
    gauge, recorder = Gauge(), Recorder()
    start_worker(gauge.run_source, recorder, fast_settings(domain_concurrency=1))

    jobs = [
        await redis.enqueue_job("execute_job", s, f"d{i}.test", _job_id=f"j{i}") for i, s in enumerate(sources(3))
    ]
    for j in jobs:
        await j.result(timeout=10, poll_delay=0.05)

    assert gauge.peak == 3


async def test_a_lease_left_by_a_crashed_worker_expires_on_its_own(redis):
    sem = LeaseSemaphore(redis, DOMAIN, cap=1)
    assert await sem.acquire("dead-worker", ttl=0.2) is True
    assert await sem.acquire("next", ttl=0.2) is False

    await asyncio.sleep(0.3)

    assert await sem.acquire("next", ttl=0.2) is True


async def test_released_lease_frees_the_slot_immediately(redis):
    sem = LeaseSemaphore(redis, DOMAIN, cap=1)
    await sem.acquire("a", ttl=30)
    await sem.release("a")

    assert await sem.acquire("b", ttl=30) is True


async def test_pending_jobs_survive_a_worker_stopping_and_run_on_the_next_worker(redis, start_worker):
    release = asyncio.Event()
    ran: list[str] = []

    async def blocked(source_id, started=None):
        await release.wait()
        return AttemptResult(documents=1)

    async def quick(source_id, started=None):
        ran.append(source_id)
        return AttemptResult(documents=1)

    first_worker = start_worker(blocked, Recorder(), fast_settings(domain_concurrency=10), max_jobs=1)
    ids = sources(3)
    jobs = [await redis.enqueue_job("execute_job", s, f"d{i}.test", _job_id=f"j{i}") for i, s in enumerate(ids)]
    await asyncio.sleep(0.3)
    first_worker.cancel()

    start_worker(quick, Recorder(), fast_settings(domain_concurrency=10))
    for j in jobs[1:]:
        assert await j.result(timeout=10, poll_delay=0.05) == "ok"

    assert sorted(ran) == sorted(ids[1:])


async def test_a_running_job_keeps_its_slot_past_the_lease_ttl(redis, start_worker):
    release, begun = asyncio.Event(), []

    async def run_source(source_id, started=None):
        begun.append(source_id)
        await release.wait()
        return AttemptResult(documents=1)

    start_worker(run_source, Recorder(), fast_settings(domain_concurrency=1, lease_ttl=0.9))
    first_id, second_id = sources(2)
    first = await redis.enqueue_job("execute_job", first_id, DOMAIN, _job_id="a")
    await asyncio.sleep(2.0)
    second = await redis.enqueue_job("execute_job", second_id, DOMAIN, _job_id="b")
    await asyncio.sleep(0.4)

    assert begun == [first_id]
    release.set()
    assert await first.result(timeout=5, poll_delay=0.05) == "ok"
    assert await second.result(timeout=5, poll_delay=0.05) == "ok"


async def test_a_finished_job_frees_its_slot_at_once(redis, start_worker):
    async def run_source(source_id, started=None):
        return AttemptResult(documents=1)

    start_worker(run_source, Recorder(), fast_settings(domain_concurrency=1, lease_ttl=30.0))
    first_id, second_id = sources(2)
    first = await redis.enqueue_job("execute_job", first_id, DOMAIN, _job_id="a")
    await first.result(timeout=5, poll_delay=0.05)
    second = await redis.enqueue_job("execute_job", second_id, DOMAIN, _job_id="b")

    assert await second.result(timeout=2, poll_delay=0.05) == "ok"


async def test_renewing_a_lease_at_full_cap_pushes_its_expiry_out(redis):
    sem = LeaseSemaphore(redis, DOMAIN, cap=1)
    assert await sem.acquire("a", ttl=0.6) is True
    await asyncio.sleep(0.4)

    assert await sem.acquire("a", ttl=0.6) is True
    await asyncio.sleep(0.4)

    assert await sem.acquire("b", ttl=0.6) is False
