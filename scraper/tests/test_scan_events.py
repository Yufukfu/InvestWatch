import asyncio
import time
from datetime import UTC, datetime, timedelta

from conftest import Recorder, fast_settings, make_source
from iw_scraper.jobs import AttemptResult
from iw_scraper.types import Deferral, JobError, Reason

SRC = "33333333-3333-4333-8333-333333333333"
DOMAIN = "example.test"


async def wait_for(predicate, timeout=5.0):
    deadline = time.monotonic() + timeout
    while not predicate():
        assert time.monotonic() < deadline, "condition not reached in time"
        await asyncio.sleep(0.02)


async def run_job(redis, start_worker, run_source, *, requested=False, job_id="job-1", recorder=None):
    start_worker(run_source, recorder or Recorder(), fast_settings())
    job = await redis.enqueue_job("execute_job", SRC, DOMAIN, requested, _job_id=job_id)
    return await job.result(timeout=10, poll_delay=0.05)


def result_of(documents=0, reason=None, status=None):
    error = JobError(reason, "x", SRC) if reason else None
    return AttemptResult(documents=documents, error=error, http_status=status)


async def test_started_and_finished_are_published_once_per_job_despite_retries(redis, start_worker, store, events):
    attempts = []

    async def run_source(source_id, started=None):
        attempts.append(1)
        return result_of(reason=Reason.HTTP_ERROR, status=503) if len(attempts) < 3 else result_of(documents=2)

    outcome = await run_job(redis, start_worker, run_source)
    await wait_for(lambda: len(events) >= 2)
    await asyncio.sleep(0.2)

    assert outcome == "ok"
    assert [e["type"] for e in events] == ["scan.started", "scan.finished"]
    assert events[0]["data"] == {"source_id": SRC}
    assert events[1]["data"] == {"source_id": SRC, "documents": 2, "status": "ok"}


async def test_source_is_marked_running_while_the_job_runs_and_finished_after(redis, start_worker, store):
    seen = {}

    async def run_source(source_id, started):
        await started()
        seen["during"] = dict(store.status[SRC])
        return result_of(documents=3)

    await run_job(redis, start_worker, run_source)

    assert seen["during"] == {"last_run_status": "running"}
    after = store.status[SRC]
    assert (after["last_run_status"], after["documents_count"]) == ("ok", 3)
    assert abs((datetime.now(UTC) - after["last_run_at"]).total_seconds()) < 10


async def test_a_collector_can_announce_the_start_before_it_fetches(redis, start_worker, events):
    release = asyncio.Event()

    async def run_source(source_id, started):
        await started()
        await release.wait()
        return result_of(documents=1)

    start_worker(run_source, Recorder(), fast_settings())
    job = await redis.enqueue_job("execute_job", SRC, DOMAIN, False, _job_id="job-1")
    await wait_for(lambda: [e["type"] for e in events] == ["scan.started"])
    release.set()

    assert await job.result(timeout=5, poll_delay=0.05) == "ok"
    assert [e["type"] for e in events] == ["scan.started", "scan.finished"]


async def test_one_document_and_one_job_error_is_partial(redis, start_worker, store, events):
    outcome = await run_job(redis, start_worker, lambda s, started=None: _const(result_of(1, Reason.PARSE_ERROR)))
    await wait_for(lambda: len(events) >= 2)

    assert outcome == "partial"
    assert events[1]["data"]["status"] == "partial"
    assert store.status[SRC]["last_run_status"] == "partial"


async def test_a_block_with_no_document_is_failed_and_stamps_last_run_at(redis, start_worker, store, events):
    outcome = await run_job(redis, start_worker, lambda s, started=None: _const(result_of(0, Reason.BLOCKED)))
    await wait_for(lambda: len(events) >= 2)

    assert outcome == "failed"
    assert events[1]["data"] == {"source_id": SRC, "documents": 0, "status": "failed"}
    assert store.status[SRC]["last_run_at"] is not None


async def test_a_run_that_finds_only_duplicates_records_zero_documents(redis, start_worker, store):
    await run_job(redis, start_worker, lambda s, started=None: _const(result_of(documents=0)))

    assert store.status[SRC]["documents_count"] == 0
    assert store.status[SRC]["last_run_status"] == "ok"


async def test_a_deferred_job_publishes_nothing_until_it_runs(redis, start_worker, events):
    calls = []

    async def run_source(source_id, started=None):
        calls.append(1)
        if len(calls) == 1:
            return AttemptResult(deferral=Deferral(until=datetime.now(UTC) + timedelta(seconds=0.6)))
        return result_of(documents=1)

    start_worker(run_source, Recorder(), fast_settings())
    job = await redis.enqueue_job("execute_job", SRC, DOMAIN, False, _job_id="job-1")
    await asyncio.sleep(0.3)

    assert events == []
    assert await job.result(timeout=5, poll_delay=0.05) == "ok"
    await wait_for(lambda: len(events) >= 2)
    assert [e["type"] for e in events] == ["scan.started", "scan.finished"]


async def test_a_coalesced_job_publishes_nothing(redis, start_worker, events):
    release = asyncio.Event()

    async def run_source(source_id, started=None):
        await release.wait()
        return result_of(documents=1)

    start_worker(run_source, Recorder(), fast_settings())
    first = await redis.enqueue_job("execute_job", SRC, DOMAIN, False, _job_id="a")
    await asyncio.sleep(0.3)
    second = await redis.enqueue_job("execute_job", SRC, DOMAIN, True, _job_id="b")

    assert await second.result(timeout=5, poll_delay=0.05) == "coalesced"
    release.set()
    await first.result(timeout=5, poll_delay=0.05)
    await asyncio.sleep(0.2)
    assert [e["type"] for e in events] == ["scan.started", "scan.finished"]


async def test_a_requested_job_whose_source_was_deactivated_finishes_failed(redis, start_worker, store, events):
    store.sources[SRC] = make_source(SRC, active=False)
    calls = []

    async def run_source(source_id, started=None):
        calls.append(1)
        return result_of(documents=1)

    outcome = await run_job(redis, start_worker, run_source, requested=True)
    await wait_for(lambda: len(events) >= 1)
    await asyncio.sleep(0.2)

    assert (outcome, calls) == ("skipped", [])
    assert [(e["type"], e["data"]) for e in events] == [
        ("scan.finished", {"source_id": SRC, "documents": 0, "status": "failed"})
    ]


async def test_a_scheduled_job_whose_source_was_deactivated_stays_silent(redis, start_worker, store, events):
    store.sources[SRC] = make_source(SRC, active=False)

    outcome = await run_job(redis, start_worker, lambda s, started=None: _const(result_of(1)), requested=False)
    await asyncio.sleep(0.3)

    assert (outcome, events) == ("skipped", [])


async def test_a_run_that_crashes_after_starting_still_finishes_failed(redis, start_worker, events):
    async def run_source(source_id, started=None):
        await started()
        raise RuntimeError("collector bug")

    start_worker(run_source, Recorder(), fast_settings())
    await redis.enqueue_job("execute_job", SRC, DOMAIN, False, _job_id="job-1")
    await wait_for(lambda: len(events) >= 2)

    assert [e["type"] for e in events] == ["scan.started", "scan.finished"]
    assert events[1]["data"]["status"] == "failed"


async def test_a_run_that_crashes_before_starting_publishes_nothing(redis, start_worker, events):
    async def run_source(source_id, started=None):
        raise RuntimeError("collector bug")

    start_worker(run_source, Recorder(), fast_settings())
    job = await redis.enqueue_job("execute_job", SRC, DOMAIN, False, _job_id="job-1")
    await asyncio.gather(job.result(timeout=5, poll_delay=0.05), return_exceptions=True)
    await asyncio.sleep(0.3)

    assert events == []


async def test_a_source_deactivated_between_retries_still_gets_its_finished_event(redis, start_worker, store, events):
    calls = []

    async def run_source(source_id, started):
        await started()
        calls.append(1)
        store.sources[SRC] = make_source(SRC, active=False)
        return result_of(reason=Reason.HTTP_ERROR, status=503)

    start_worker(run_source, Recorder(), fast_settings())
    job = await redis.enqueue_job("execute_job", SRC, DOMAIN, False, _job_id="job-1")

    assert await job.result(timeout=10, poll_delay=0.05) == "skipped"
    await wait_for(lambda: len(events) >= 2)
    assert (len(calls), [e["type"] for e in events]) == (1, ["scan.started", "scan.finished"])
    assert events[1]["data"]["status"] == "failed"


async def _const(value):
    return value
