import asyncio
from datetime import UTC, datetime

import pytest
from arq.jobs import Job

from conftest import Recorder, make_source
from iw_scraper.scan_requests import ScanRequestConsumer, consumer_name
from iw_scraper.types import JobError, Reason

STREAM = "iw:scan-requests"
GROUP = "iw-scraper"
SRC = "44444444-4444-4444-8444-444444444444"


def request(source_id=SRC):
    return {"source_id": source_id, "requested_at": datetime.now(UTC).isoformat()}


async def make_consumer(redis, store, recorder, name="w1", claim_idle=0.2):
    consumer = ScanRequestConsumer(redis, store, recorder.record_error, consumer=name, claim_idle=claim_idle)
    await consumer.setup()
    return consumer


async def pending(redis) -> int:
    return (await redis.xpending(STREAM, GROUP))["pending"]


async def queued_jobs(redis):
    return [await Job(j.decode(), redis).info() for j in await redis.zrange("arq:queue", 0, -1)]


async def test_a_valid_request_enqueues_one_requested_job_and_is_acknowledged(redis, store):
    consumer = await make_consumer(redis, store, Recorder())
    await redis.xadd(STREAM, request())

    await consumer.poll(block=0.2)

    jobs = await queued_jobs(redis)
    assert [(j.function, j.args) for j in jobs] == [("execute_job", (SRC, "example.test", True))]
    assert await pending(redis) == 0


@pytest.mark.parametrize("kind", ["unknown", "inactive", "not_web"])
async def test_a_request_for_a_source_that_cannot_run_is_refused_visibly(redis, store, events, kind):
    store.permissive = False
    if kind == "inactive":
        store.sources[SRC] = make_source(SRC, active=False)
    if kind == "not_web":
        store.sources[SRC] = make_source(SRC, platform="facebook")
    recorder = Recorder()
    consumer = await make_consumer(redis, store, recorder)
    await redis.xadd(STREAM, request())

    await consumer.poll(block=0.2)
    await asyncio.sleep(0.2)

    assert await queued_jobs(redis) == []
    assert recorder.errors == [JobError(Reason.INVALID_REQUEST, recorder.errors[0].detail, SRC)]
    assert [(e["type"], e["data"]) for e in events] == [
        ("scan.finished", {"source_id": SRC, "documents": 0, "status": "failed"})
    ]
    assert await pending(redis) == 0


@pytest.mark.parametrize("fields", [{}, {"source_id": "not-a-uuid"}, {"source_id": "AAAAAAAA-AAAA-4AAA-8AAA-AAAAAAAAAAAA"}, {"requested_at": "x"}])
async def test_a_malformed_request_is_recorded_without_a_source_and_publishes_nothing(redis, store, events, fields):
    recorder = Recorder()
    consumer = await make_consumer(redis, store, recorder)
    await redis.xadd(STREAM, fields or {"junk": "1"})

    await consumer.poll(block=0.2)
    await asyncio.sleep(0.2)

    assert [(e.reason, e.source_id) for e in recorder.errors] == [(Reason.INVALID_REQUEST, None)]
    assert (await queued_jobs(redis), events) == ([], [])
    assert await pending(redis) == 0


async def test_a_message_left_pending_by_a_dead_consumer_is_claimed_and_enqueued(redis, store):
    dead = await make_consumer(redis, store, Recorder(), name="dead")
    await redis.xadd(STREAM, request())
    assert len(await redis.xreadgroup(GROUP, "dead", {STREAM: ">"}, count=10)) == 1
    assert await pending(redis) == 1

    alive = await make_consumer(redis, store, Recorder(), name="alive", claim_idle=0.2)
    await alive.poll(block=0.05)
    assert await queued_jobs(redis) == []  # not idle long enough yet
    await asyncio.sleep(0.3)
    await alive.poll(block=0.05)

    assert len(await queued_jobs(redis)) == 1
    assert await pending(redis) == 0


async def test_handling_the_same_message_twice_enqueues_one_job(redis, store):
    consumer = await make_consumer(redis, store, Recorder())
    fields = {k.encode(): v.encode() for k, v in request().items()}

    await consumer.handle("1700000000000-0", fields)
    await consumer.handle("1700000000000-0", fields)

    assert len(await queued_jobs(redis)) == 1


def test_the_consumer_name_is_stable_and_can_be_set(monkeypatch):
    monkeypatch.delenv("SCRAPER_CONSUMER", raising=False)
    assert consumer_name() == consumer_name() != ""

    monkeypatch.setenv("SCRAPER_CONSUMER", "worker-7")
    assert consumer_name() == "worker-7"


async def test_a_request_added_before_the_consumer_existed_is_still_handled(redis, store):
    await redis.xadd(STREAM, request())
    consumer = await make_consumer(redis, store, Recorder())

    await consumer.poll(block=0.2)

    assert len(await queued_jobs(redis)) == 1


async def test_a_field_that_is_not_valid_utf8_makes_the_request_malformed_and_does_not_block_the_next(redis, store):
    recorder = Recorder()
    consumer = await make_consumer(redis, store, recorder)
    await redis.xadd(STREAM, {"source_id": SRC, "requested_at": b"\xff\xfe"})
    await redis.xadd(STREAM, request())

    await consumer.poll(block=0.2)

    assert len(await queued_jobs(redis)) == 2
    assert await pending(redis) == 0


async def test_every_stale_pending_message_is_claimed_not_just_the_first_batch(redis, store):
    await make_consumer(redis, store, Recorder(), name="dead")
    for _ in range(120):
        await redis.xadd(STREAM, request())
    await redis.xreadgroup(GROUP, "dead", {STREAM: ">"}, count=500)
    alive = await make_consumer(redis, store, Recorder(), name="alive", claim_idle=0.1)
    await asyncio.sleep(0.2)

    assert await alive.poll(block=0.05) == 120
    assert await pending(redis) == 0
