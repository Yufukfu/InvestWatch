"""A removed page (`gone`) reaches the queue as a result with no error: a success, never a failed run."""

import time

from conftest import Recorder, fast_settings
from iw_scraper.jobs import AttemptResult
from iw_scraper.types import JobError, Reason

SRC = "11111111-1111-4111-8111-111111111111"
DOMAIN = "example.test"
PAUSED = f"iw:scraper:domain:{DOMAIN}:paused"
FAILURES = f"iw:scraper:domain:{DOMAIN}:failures"


def gone() -> AttemptResult:
    return AttemptResult()  # what the collector returns after `Ingestor.record_gone`: no documents, no error


def server_error() -> AttemptResult:
    return AttemptResult(error=JobError(Reason.HTTP_ERROR, "HTTP 503", SRC), http_status=503)


async def run_jobs(redis, start_worker, results, settings, store=None):
    calls = []
    queue = list(results)

    async def run_source(source_id, started=None):
        calls.append(time.monotonic())
        return queue.pop(0) if len(queue) > 1 else queue[0]

    start_worker(run_source, Recorder(), settings)
    return calls


async def enqueue(redis, job_id):
    job = await redis.enqueue_job("execute_job", SRC, DOMAIN, _job_id=job_id)
    return await job.result(timeout=10, poll_delay=0.05)


async def test_a_gone_job_ends_ok_once_with_no_documents(redis, start_worker, store):
    calls = await run_jobs(redis, start_worker, [gone()], fast_settings(max_tries=3))

    assert await enqueue(redis, "job-1") == "ok"

    assert len(calls) == 1  # not requeued
    assert store.status[SRC]["last_run_status"] == "ok"
    assert await redis.exists("iw:scraper:attempts:job-1") == 0


async def test_a_gone_job_after_a_transient_failure_clears_the_attempt_counter(redis, start_worker, store):
    calls = await run_jobs(redis, start_worker, [server_error(), gone()], fast_settings(max_tries=3))

    assert await enqueue(redis, "job-1") == "ok"

    assert len(calls) == 2
    assert await redis.exists("iw:scraper:attempts:job-1") == 0
    assert store.status[SRC]["last_run_status"] == "ok"


async def test_five_gone_jobs_do_not_pause_the_domain(redis, start_worker):
    await run_jobs(redis, start_worker, [gone()], fast_settings(failure_threshold=5, domain_cooldown=5.0))

    for n in range(5):
        assert await enqueue(redis, f"g{n}") == "ok"

    assert await redis.exists(PAUSED) == 0
    assert int(await redis.get(FAILURES) or 0) == 0


async def test_gone_resets_the_failures_that_came_before_it(redis, start_worker):
    await run_jobs(redis, start_worker, [server_error(), server_error(), gone()], fast_settings(max_tries=1, failure_threshold=3))

    assert await enqueue(redis, "f1") == "failed"
    assert await enqueue(redis, "f2") == "failed"
    assert int(await redis.get(FAILURES)) == 2
    assert await enqueue(redis, "g1") == "ok"
    assert int(await redis.get(FAILURES) or 0) == 0


async def test_five_server_errors_still_pause_the_domain(redis, start_worker):
    await run_jobs(redis, start_worker, [server_error()], fast_settings(max_tries=1, failure_threshold=5, domain_cooldown=5.0))

    for n in range(5):
        assert await enqueue(redis, f"e{n}") == "failed"

    assert await redis.pttl(PAUSED) > 0
