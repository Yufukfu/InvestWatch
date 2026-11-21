"""The republish sweep (real PostgreSQL and Redis)."""

import asyncio
import uuid
from datetime import datetime, timedelta, timezone

import redis

from iw_scraper.ingest import publisher
from iw_scraper.ingest.document import build_document
from iw_scraper.ingest.publisher import mark_published, sweep
from iw_scraper.ingest.store import insert_document

FETCHED_AT = datetime(2026, 11, 21, 15, 0, 0, tzinfo=timezone.utc)
GRACE = timedelta(seconds=60)


async def add_document(pool, source, text, *, age_seconds=0):
    page = {"url": "https://alfa.example.com/konto", "text": text}
    doc = build_document(page, source, fetched_at=FETCHED_AT, duration_ms=1, proxy=None)
    await insert_document(pool, doc)
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE documents SET created_at = now() - make_interval(secs => $2) WHERE id = $1",
            uuid.UUID(doc["id"]),
            float(age_seconds),
        )
    return doc["id"]


async def published_at(pool, document_id):
    async with pool.acquire() as conn:
        return await conn.fetchval("SELECT stream_published_at FROM documents WHERE id = $1", uuid.UUID(document_id))


async def test_old_unpublished_document_is_published_and_marked(pool, redis_client, stream_name, seeded_source):
    document_id = await add_document(pool, seeded_source, "a", age_seconds=300)
    assert await sweep(pool, redis_client, grace=GRACE, stream=stream_name) == 1
    entries = await redis_client.xrange(stream_name)
    assert [fields for _, fields in entries] == [{"document_id": document_id, "schema": "v1"}]
    assert await published_at(pool, document_id) is not None


async def test_published_document_is_not_republished(pool, redis_client, stream_name, seeded_source):
    document_id = await add_document(pool, seeded_source, "a", age_seconds=300)
    await mark_published(pool, document_id)
    assert await sweep(pool, redis_client, grace=GRACE, stream=stream_name) == 0
    assert await redis_client.xlen(stream_name) == 0


async def test_second_sweep_finds_nothing_left(pool, redis_client, stream_name, seeded_source):
    await add_document(pool, seeded_source, "a", age_seconds=300)
    await sweep(pool, redis_client, grace=GRACE, stream=stream_name)
    assert await sweep(pool, redis_client, grace=GRACE, stream=stream_name) == 0
    assert await redis_client.xlen(stream_name) == 1


async def test_batch_limit_takes_the_oldest_rows_first(pool, redis_client, stream_name, seeded_source):
    ids_by_age = [await add_document(pool, seeded_source, f"doc {n}", age_seconds=1000 - n * 10) for n in range(8)]
    assert await sweep(pool, redis_client, grace=GRACE, batch=4, stream=stream_name) == 4
    published = [fields["document_id"] for _, fields in await redis_client.xrange(stream_name)]
    assert published == ids_by_age[:4]  # oldest first, so a backlog cannot starve its oldest rows


async def test_fresh_row_is_left_alone(pool, redis_client, stream_name, seeded_source):
    document_id = await add_document(pool, seeded_source, "a", age_seconds=5)
    assert await sweep(pool, redis_client, grace=GRACE, stream=stream_name) == 0
    assert await published_at(pool, document_id) is None


async def test_redis_down_leaves_rows_unpublished(pool, stream_name, seeded_source):
    class DownRedis:
        async def xadd(self, *args, **kwargs):
            raise redis.ConnectionError("redis unavailable")

    document_id = await add_document(pool, seeded_source, "a", age_seconds=300)
    assert await sweep(pool, DownRedis(), grace=GRACE, stream=stream_name) == 0
    assert await published_at(pool, document_id) is None
    async with pool.acquire() as conn:
        assert await conn.fetchval("SELECT reason FROM job_errors") == "publish_failed"


async def test_concurrent_sweep_skips_rows_claimed_by_a_running_one(pool, stream_name, seeded_source):
    """Sweep A is mid-publish holding the row lock; sweep B must return at once, not wait and not republish."""

    class GatedRedis:
        def __init__(self):
            self.inside = asyncio.Event()
            self.release = asyncio.Event()
            self.published = []

        async def xadd(self, stream, fields):
            self.published.append(fields["document_id"])
            self.inside.set()
            await self.release.wait()

    document_id = await add_document(pool, seeded_source, "a", age_seconds=300)
    gated = GatedRedis()
    first = asyncio.create_task(sweep(pool, gated, grace=GRACE, stream=stream_name))
    await asyncio.wait_for(gated.inside.wait(), timeout=5)

    try:
        second = await asyncio.wait_for(sweep(pool, gated, grace=GRACE, stream=stream_name), timeout=2)
    finally:
        gated.release.set()  # always, or a blocked sweep keeps its row lock and the pool never closes

    assert second == 0
    assert await first == 1
    assert gated.published == [document_id]


async def test_hung_redis_does_not_hold_the_sweep_forever(pool, stream_name, seeded_source, monkeypatch):
    class HungRedis:
        async def xadd(self, *args, **kwargs):
            await asyncio.Event().wait()

    monkeypatch.setattr(publisher, "PUBLISH_TIMEOUT_S", 0.05)
    document_id = await add_document(pool, seeded_source, "a", age_seconds=300)
    assert await asyncio.wait_for(sweep(pool, HungRedis(), grace=GRACE, stream=stream_name), 5) == 0
    assert await published_at(pool, document_id) is None


async def test_an_unexpected_publish_error_keeps_earlier_markers_and_is_recorded(pool, stream_name, seeded_source):
    class FlakyRedis:
        calls = 0

        async def xadd(self, *args, **kwargs):
            FlakyRedis.calls += 1
            if FlakyRedis.calls == 2:
                raise RuntimeError("client bug")

    first = await add_document(pool, seeded_source, "a", age_seconds=400)
    second = await add_document(pool, seeded_source, "b", age_seconds=300)
    assert await sweep(pool, FlakyRedis(), grace=GRACE, stream=stream_name) == 1
    assert await published_at(pool, first) is not None
    assert await published_at(pool, second) is None
    async with pool.acquire() as conn:
        assert await conn.fetchval("SELECT reason FROM job_errors") == "publish_failed"
