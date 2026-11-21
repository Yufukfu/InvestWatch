import asyncio
import json
import time
from datetime import UTC, datetime, timedelta

import asyncpg
import pytest

from conftest import Recorder, fast_settings
from iw_scraper.app import RETRY_ON
from iw_scraper.guards import DomainHealth
from iw_scraper.jobs import AttemptResult
from iw_scraper.types import Deferral, JobError, Reason

SRC = "11111111-1111-4111-8111-111111111111"
OTHER = "22222222-2222-4222-8222-222222222222"
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

    assert await redis.exists(f"iw:scraper:domain:{DOMAIN}:paused") == 0
    assert int(await redis.get(f"iw:scraper:domain:{DOMAIN}:failures")) == 1


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
    assert 0 < await redis.pttl(f"iw:scraper:domain:{DOMAIN}:paused") <= 600
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
    assert await redis.exists(f"iw:scraper:domain:{DOMAIN}:failures") == 0


async def test_domain_outcome_is_recorded_even_when_the_error_sink_fails(redis, start_worker):
    class BrokenSink(Recorder):
        async def record_error(self, error):
            raise RuntimeError("sink down")

    run = scripted([fail(Reason.BLOCKED)], [])
    start_worker(run, BrokenSink(), fast_settings())
    job = await redis.enqueue_job("execute_job", SRC, DOMAIN, _job_id="job-1")
    with pytest.raises(RuntimeError):
        await job.result(timeout=10, poll_delay=0.05)

    assert int(await redis.get(f"iw:scraper:domain:{DOMAIN}:failures")) == 1


async def test_an_error_the_collector_already_recorded_is_not_recorded_again(redis, start_worker):
    error = JobError(Reason.STORAGE_ERROR, "upload failed", SRC)
    run = scripted([AttemptResult(error=error, recorded=True)], [])

    outcome, recorder = await run_one(redis, start_worker, run, fast_settings())

    assert (outcome, recorder.errors) == ("failed", [])


async def test_a_huge_retry_after_is_cut_to_the_configured_maximum(redis, start_worker):
    calls = []
    run = scripted([fail(Reason.HTTP_ERROR, 503, retry_after=1e12), AttemptResult(documents=1)], calls)

    outcome, _ = await run_one(redis, start_worker, run, fast_settings(max_retry_after=0.4))

    assert outcome == "ok"
    assert 0.35 <= calls[1] - calls[0] < 3.0


async def test_job_state_keys_use_the_scraper_prefix(redis, start_worker):
    calls, seen = [], {}

    async def run_source(source_id, started=None):
        calls.append(1)
        await started()
        if len(calls) == 1:
            return fail(Reason.HTTP_ERROR, 503)
        seen["attempts"] = await redis.get("iw:scraper:attempts:job-1")
        seen["started"] = await redis.exists("iw:scraper:started:job-1")
        seen["lease"] = await redis.zcard(f"iw:scraper:sem:{DOMAIN}")
        return AttemptResult(documents=1)

    outcome, _ = await run_one(redis, start_worker, run_source, fast_settings())

    assert (outcome, seen) == ("ok", {"attempts": b"1", "started": 1, "lease": 1})


async def test_jobs_and_results_are_stored_as_json(redis, start_worker):
    await redis.enqueue_job("execute_job", SRC, DOMAIN, _job_id="queued", _defer_by=3600)
    assert json.loads(await redis.get("arq:job:queued"))["a"] == [SRC, DOMAIN]
    assert await redis.zscore("iw:scraper:queue", "queued") is not None

    outcome, _ = await run_one(redis, start_worker, scripted([AttemptResult(documents=1)], []), fast_settings())

    assert outcome == "ok"
    assert json.loads(await redis.get("arq:result:job-1"))["r"] == "ok"


def first_call_fails(result, calls):
    """run_source that answers `result` to its first call and a success afterwards, logging (source, time)."""
    state = {"first": True}

    async def run_source(source_id, started=None):
        calls.append((source_id, time.monotonic()))
        if state["first"]:
            state["first"] = False
            return result
        return AttemptResult(documents=1)

    return run_source


async def other_source_job(redis, job_id="job-2"):
    job = await redis.enqueue_job("execute_job", OTHER, DOMAIN, _job_id=job_id)
    return await job.result(timeout=10, poll_delay=0.05)


async def test_a_429_with_retry_after_keeps_other_sources_off_the_domain_until_it_ends(redis, start_worker):
    calls = []
    run = first_call_fails(fail(Reason.BLOCKED, 429, retry_after=0.8), calls)

    outcome, _ = await run_one(redis, start_worker, run, fast_settings())
    assert outcome == "failed"  # a block is not retried
    assert await other_source_job(redis) == "ok"

    assert [source for source, _ in calls] == [SRC, OTHER]
    assert calls[1][1] - calls[0][1] >= 0.75


async def test_a_503_retry_after_defers_the_whole_domain_and_not_only_the_failing_job(redis, start_worker):
    calls = []
    run = first_call_fails(fail(Reason.HTTP_ERROR, 503, retry_after=0.8), calls)
    start_worker(run, Recorder(), fast_settings(max_tries=3))

    first = await redis.enqueue_job("execute_job", SRC, DOMAIN, _job_id="job-1")
    await asyncio.sleep(0.2)  # the first attempt has failed and its job waits for its retry
    second = await redis.enqueue_job("execute_job", OTHER, DOMAIN, _job_id="job-2")
    assert await second.result(timeout=10, poll_delay=0.05) == "ok"
    assert await first.result(timeout=10, poll_delay=0.05) == "ok"

    other_started = next(at for source, at in calls if source == OTHER)
    assert other_started - calls[0][1] >= 0.75


async def test_a_retry_after_beyond_the_cap_defers_the_domain_for_the_cap_only(redis, start_worker):
    calls = []
    run = first_call_fails(fail(Reason.BLOCKED, 429, retry_after=86400), calls)

    await run_one(redis, start_worker, run, fast_settings(max_retry_after=0.5))

    assert 0 < await redis.pttl(f"iw:scraper:domain:{DOMAIN}:deferred") <= 500
    assert await other_source_job(redis) == "ok"
    assert calls[1][1] - calls[0][1] < 5


async def test_a_shorter_deferral_does_not_shorten_a_longer_one(redis):
    health = DomainHealth(redis, DOMAIN, threshold=5, cooldown=1.0)

    await health.defer(2.0)
    await health.defer(0.1)

    assert await health.deferred_for() > 1.5


async def test_a_lost_postgres_connection_before_the_run_requeues_the_job_without_a_failure(redis, start_worker, store, events):
    real_get, failures, calls = store.get, [], []

    async def flaky_get(source_id):
        if not failures:
            failures.append(1)
            raise asyncpg.ConnectionDoesNotExistError("connection was closed")
        return await real_get(source_id)

    store.get = flaky_get
    start_worker(scripted([AttemptResult(documents=1)], calls), Recorder(), fast_settings(max_tries=1), retry_on=RETRY_ON)
    job = await redis.enqueue_job("execute_job", SRC, DOMAIN, True, _job_id="job-1")

    assert await job.result(timeout=10, poll_delay=0.05) == "ok"
    await asyncio.sleep(0.2)

    assert len(calls) == 1
    assert [(e["type"], e["data"].get("status")) for e in events] == [("scan.started", None), ("scan.finished", "ok")]
    assert await redis.exists(f"iw:scraper:lock:{SRC}") == 0


async def test_a_lost_postgres_connection_mid_run_retries_without_consuming_an_attempt(redis, start_worker, events):
    calls = []

    async def run_source(source_id, started=None):
        calls.append(1)
        await started()
        if len(calls) == 1:
            raise asyncpg.InterfaceError("connection is closed")
        return AttemptResult(documents=2)

    recorder = Recorder()
    start_worker(run_source, recorder, fast_settings(max_tries=1), retry_on=RETRY_ON)
    job = await redis.enqueue_job("execute_job", SRC, DOMAIN, _job_id="job-1")

    assert await job.result(timeout=10, poll_delay=0.05) == "ok"
    await asyncio.sleep(0.2)

    assert (len(calls), recorder.errors) == (2, [])
    assert [(e["type"], e["data"].get("status")) for e in events] == [("scan.started", None), ("scan.finished", "ok")]
    assert await redis.exists("iw:scraper:attempts:job-1") == 0


async def test_the_run_lock_outlives_the_requeue_delay_after_a_lost_connection(redis, start_worker):
    settings = fast_settings(requeue_delay=1.5, lease_ttl=0.5)
    calls = []

    async def run_source(source_id, started=None):
        calls.append(1)
        if len(calls) == 1:
            raise asyncpg.InterfaceError("connection is closed")
        return AttemptResult(documents=1)

    start_worker(run_source, Recorder(), settings, retry_on=RETRY_ON)
    first = await redis.enqueue_job("execute_job", SRC, DOMAIN, _job_id="job-1")
    await asyncio.sleep(0.9)  # past the lease: only the extension for the requeue still holds the lock
    second = await redis.enqueue_job("execute_job", SRC, DOMAIN, _job_id="job-2")

    assert await second.result(timeout=10, poll_delay=0.05) == "coalesced"
    assert await first.result(timeout=10, poll_delay=0.05) == "ok"
