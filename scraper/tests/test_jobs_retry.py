import asyncio
import time
from datetime import UTC, datetime, timedelta

import pytest

from conftest import Recorder, fast_settings
from iw_scraper.jobs import AttemptResult
from iw_scraper.types import Deferral, JobError, Reason

SRC = "11111111-1111-4111-8111-111111111111"
DOMAIN = "example.test"


def scripted(results, calls):
    """run_source that returns the scripted results in order and records attempt times."""
    queue = list(results)

    async def run_source(source_id, started=None):
        calls.append(time.monotonic())
        return queue.pop(0) if len(queue) > 1 else queue[0]

    return run_source


def fail(reason, status=None, retry_after=None):
    return AttemptResult(error=JobError(reason, "x", SRC), http_status=status, retry_after=retry_after)


async def run_one(redis, start_worker, run_source, settings, recorder=None, job_id="job-1"):
    recorder = recorder or Recorder()
    start_worker(run_source, recorder, settings)
    job = await redis.enqueue_job("execute_job", SRC, DOMAIN, _job_id=job_id)
    return await job.result(timeout=10, poll_delay=0.05), recorder


async def test_transient_failure_is_retried_without_a_job_error(redis, start_worker):
    calls = []
    run = scripted([fail(Reason.HTTP_ERROR, 503), fail(Reason.TIMEOUT), AttemptResult(documents=1)], calls)

    outcome, recorder = await run_one(redis, start_worker, run, fast_settings(max_tries=3))

    assert (outcome, len(calls), recorder.errors) == ("ok", 3, [])


async def test_retry_after_pushes_the_next_attempt_out(redis, start_worker):
    calls = []
    run = scripted([fail(Reason.HTTP_ERROR, 503, retry_after=0.6), AttemptResult(documents=1)], calls)

    outcome, _ = await run_one(redis, start_worker, run, fast_settings())

    assert outcome == "ok"
    assert calls[1] - calls[0] >= 0.55  # Retry-After 0.6 s; arq rounds the defer to whole milliseconds


async def test_retry_cap_records_exactly_one_job_error_with_the_failing_reason(redis, start_worker):
    calls = []
    run = scripted([fail(Reason.HTTP_ERROR, 503)], calls)

    outcome, recorder = await run_one(redis, start_worker, run, fast_settings(max_tries=3))

    assert (outcome, len(calls)) == ("failed", 3)
    assert [e.reason for e in recorder.errors] == [Reason.HTTP_ERROR]


@pytest.mark.parametrize(
    ("reason", "status"),
    [(Reason.BLOCKED, None), (Reason.BLOCKED_TARGET, None), (Reason.HTTP_ERROR, 404)],
)
async def test_non_transient_failures_are_not_retried(redis, start_worker, reason, status):
    calls = []

    outcome, recorder = await run_one(redis, start_worker, scripted([fail(reason, status)], calls), fast_settings())

    assert (outcome, len(calls), [e.reason for e in recorder.errors]) == ("failed", 1, [reason])


async def test_attempt_over_its_timeout_counts_as_a_timeout_failure_and_is_retried(redis, start_worker):
    calls = []

    async def run_source(source_id, started=None):
        calls.append(1)
        await asyncio.sleep(30)

    outcome, recorder = await run_one(
        redis, start_worker, run_source, fast_settings(max_tries=2, attempt_timeout=0.1)
    )

    assert (outcome, len(calls)) == ("failed", 2)
    assert [e.reason for e in recorder.errors] == [Reason.TIMEOUT]


async def test_deferral_requeues_without_consuming_a_retry_or_recording_an_error(redis, start_worker):
    calls = []
    soon = lambda: AttemptResult(deferral=Deferral(until=datetime.now(UTC) + timedelta(seconds=0.2)))  # noqa: E731
    run = scripted([soon(), soon(), soon(), AttemptResult(documents=1)], calls)

    outcome, recorder = await run_one(redis, start_worker, run, fast_settings(max_tries=1))

    assert (outcome, len(calls), recorder.errors) == ("ok", 4, [])


async def test_a_job_failing_through_all_retries_counts_as_one_domain_failure(redis, start_worker):
    calls = []
    settings = fast_settings(max_tries=3, failure_threshold=2, domain_cooldown=5.0)

    await run_one(redis, start_worker, scripted([fail(Reason.HTTP_ERROR, 503)], calls), settings)

    assert await redis.exists(f"iw:domain:{DOMAIN}:paused") == 0
    assert int(await redis.get(f"iw:domain:{DOMAIN}:failures")) == 1


async def test_consecutive_failed_jobs_pause_the_domain_and_the_next_job_waits(redis, start_worker):
    calls = []
    settings = fast_settings(failure_threshold=2, domain_cooldown=0.6)
    run = scripted([fail(Reason.BLOCKED), fail(Reason.BLOCKED), AttemptResult(documents=1)], calls)
    recorder = Recorder()
    start_worker(run, recorder, settings)

    for n in (1, 2):
        job = await redis.enqueue_job("execute_job", SRC, DOMAIN, _job_id=f"f{n}")
        assert await job.result(timeout=10, poll_delay=0.05) == "failed"
    paused_at = time.monotonic()
    third = await redis.enqueue_job("execute_job", SRC, DOMAIN, _job_id="f3")

    assert await third.result(timeout=10, poll_delay=0.05) == "ok"
    assert calls[2] - paused_at >= 0.4
    assert len(recorder.errors) == 2


async def test_a_successful_job_resets_the_domain_failure_count(redis, start_worker):
    calls = []
    settings = fast_settings(failure_threshold=3)
    run = scripted([fail(Reason.BLOCKED), AttemptResult(documents=1)], calls)

    await run_one(redis, start_worker, run, settings, job_id="a")
    outcome, _ = await run_one(redis, start_worker, run, settings, job_id="b")

    assert outcome == "ok"
    assert await redis.exists(f"iw:domain:{DOMAIN}:failures") == 0


async def test_domain_outcome_is_recorded_even_when_the_error_sink_fails(redis, start_worker):
    class BrokenSink(Recorder):
        async def record_error(self, error):
            raise RuntimeError("sink down")

    run = scripted([fail(Reason.BLOCKED)], [])
    start_worker(run, BrokenSink(), fast_settings())
    job = await redis.enqueue_job("execute_job", SRC, DOMAIN, _job_id="job-1")
    with pytest.raises(RuntimeError):
        await job.result(timeout=10, poll_delay=0.05)

    assert int(await redis.get(f"iw:domain:{DOMAIN}:failures")) == 1


async def test_an_error_the_collector_already_recorded_is_not_recorded_again(redis, start_worker):
    error = JobError(Reason.STORAGE_ERROR, "upload failed", SRC)
    run = scripted([AttemptResult(error=error, recorded=True)], [])

    outcome, recorder = await run_one(redis, start_worker, run, fast_settings())

    assert (outcome, recorder.errors) == ("failed", [])
