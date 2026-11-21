"""The ingest pipeline end to end: PostgreSQL, MinIO and Redis are real, failures are injected."""

import asyncio
import uuid
from datetime import datetime, timedelta, timezone

import asyncpg
import pytest
import redis

from iw_scraper.ingest import pipeline, publisher
from iw_scraper.ingest.pipeline import Ingestor
from iw_scraper.ingest.publisher import sweep
from iw_scraper.ingest.storage import Storage
from iw_scraper.types import Reason

FETCHED_AT = datetime(2026, 11, 21, 15, 0, 0, tzinfo=timezone.utc)
PAGE = {"url": "https://alfa.example.com/konto", "text": "Zysk do 20%", "html": "<p>Zysk do 20%</p>"}


class BrokenStorage(Storage):
    async def put_html(self, document_id, html):
        raise OSError("minio unavailable")


class DownRedis:
    async def xadd(self, *args, **kwargs):
        raise redis.ConnectionError("redis unavailable")


class SpyRedis:
    """Records whether the row was already visible (committed) when the event was published."""

    def __init__(self, pool):
        self.pool = pool
        self.row_visible = []

    async def xadd(self, stream, fields):
        async with self.pool.acquire() as conn:
            self.row_visible.append(
                await conn.fetchval(
                    "SELECT EXISTS (SELECT 1 FROM documents WHERE id = $1)", uuid.UUID(fields["document_id"])
                )
            )


async def run(ingestor, source, page=PAGE):
    return await ingestor.ingest(page, source, fetched_at=FETCHED_AT, duration_ms=5, proxy=None)


async def reasons(pool):
    async with pool.acquire() as conn:
        return [r["reason"] for r in await conn.fetch("SELECT reason FROM job_errors ORDER BY occurred_at")]


async def doc_row(pool, document_id):
    async with pool.acquire() as conn:
        return await conn.fetchrow("SELECT * FROM documents WHERE id = $1", uuid.UUID(document_id))


async def doc_count(pool):
    async with pool.acquire() as conn:
        return await conn.fetchval("SELECT count(*) FROM documents")


async def test_html_is_stored_and_referenced(pool, storage, redis_client, stream_name, seeded_source):
    result = await run(Ingestor(pool, storage, redis_client, stream=stream_name), seeded_source)
    key = f"html/{result.document_id}.html"
    assert result.outcome == "inserted"
    assert await storage.exists(key)
    assert (await doc_row(pool, result.document_id))["html_object_key"] == key


async def test_event_is_published_with_the_contract_fields_and_marked(
    pool, storage, redis_client, stream_name, seeded_source
):
    result = await run(Ingestor(pool, storage, redis_client, stream=stream_name), seeded_source)
    entries = await redis_client.xrange(stream_name)
    assert [fields for _, fields in entries] == [{"document_id": result.document_id, "schema": "v1"}]
    assert (await doc_row(pool, result.document_id))["stream_published_at"] is not None


async def test_event_follows_the_commit(pool, storage, stream_name, seeded_source):
    spy = SpyRedis(pool)
    await run(Ingestor(pool, storage, spy, stream=stream_name), seeded_source)
    assert spy.row_visible == [True]


async def test_storage_failure_inserts_nothing_and_records_storage_error(
    pool, storage, redis_client, stream_name, seeded_source
):
    broken = BrokenStorage(storage.endpoint, storage.access_key, storage.secret_key, bucket=storage.bucket)
    result = await run(Ingestor(pool, broken, redis_client, stream=stream_name), seeded_source)
    assert result.outcome == "failed"
    assert result.error.reason is Reason.STORAGE_ERROR
    assert await doc_count(pool) == 0
    assert await reasons(pool) == ["storage_error"]
    assert await redis_client.xlen(stream_name) == 0


async def test_rerun_adds_no_object_and_no_second_event(pool, storage, redis_client, stream_name, seeded_source):
    ingestor = Ingestor(pool, storage, redis_client, stream=stream_name)
    await run(ingestor, seeded_source)
    second = await run(ingestor, seeded_source)
    assert second.outcome == "duplicate"
    assert len(await storage.list_keys()) == 1
    assert await redis_client.xlen(stream_name) == 1


async def test_known_duplicate_is_not_uploaded_at_all(pool, storage, redis_client, stream_name, seeded_source):
    uploads = []

    class CountingStorage(Storage):
        async def put_html(self, document_id, html):
            uploads.append(document_id)
            return await super().put_html(document_id, html)

    counting = CountingStorage(storage.endpoint, storage.access_key, storage.secret_key, bucket=storage.bucket)
    ingestor = Ingestor(pool, counting, redis_client, stream=stream_name)
    await run(ingestor, seeded_source)
    await run(ingestor, seeded_source)
    assert len(uploads) == 1


async def test_duplicate_found_only_at_insert_removes_the_uploaded_object(
    pool, storage, redis_client, stream_name, seeded_source, monkeypatch
):
    ingestor = Ingestor(pool, storage, redis_client, stream=stream_name)
    await run(ingestor, seeded_source)

    async def never_a_duplicate(*_args):
        return False

    monkeypatch.setattr(pipeline, "is_duplicate", never_a_duplicate)  # the race: the pre-check missed it
    second = await run(ingestor, seeded_source)
    assert second.outcome == "duplicate"
    assert len(await storage.list_keys()) == 1
    assert await redis_client.xlen(stream_name) == 1


async def test_insert_failure_removes_object_and_publishes_nothing(pool, storage, redis_client, stream_name, source):
    # `source` is not seeded, so the foreign key makes the insert fail
    result = await run(Ingestor(pool, storage, redis_client, stream=stream_name), source)
    assert result.outcome == "failed"
    assert await storage.list_keys() == []
    assert await doc_count(pool) == 0
    assert await redis_client.xlen(stream_name) == 0
    assert await reasons(pool) == ["storage_error"]


async def test_invalid_page_uploads_and_inserts_nothing(pool, storage, redis_client, stream_name, seeded_source):
    page = {"url": PAGE["url"], "html": PAGE["html"]}
    result = await run(Ingestor(pool, storage, redis_client, stream=stream_name), seeded_source, page)
    assert result.outcome == "failed"
    assert result.error.reason is Reason.SCHEMA_INVALID
    assert await storage.list_keys() == []
    assert await reasons(pool) == ["schema_invalid"]


async def test_redis_down_keeps_the_row_unpublished_and_records_publish_failed(
    pool, storage, stream_name, seeded_source
):
    result = await run(Ingestor(pool, storage, DownRedis(), stream=stream_name), seeded_source)
    assert result.outcome == "inserted"
    assert (await doc_row(pool, result.document_id))["stream_published_at"] is None
    assert await reasons(pool) == ["publish_failed"]


async def test_marker_failure_after_publish_is_republished_by_a_later_sweep(
    pool, storage, redis_client, stream_name, seeded_source, monkeypatch
):
    async def marker_down(*_args):
        raise OSError("db blip")

    monkeypatch.setattr(pipeline, "mark_published", marker_down)
    result = await run(Ingestor(pool, storage, redis_client, stream=stream_name), seeded_source)
    assert result.outcome == "inserted"
    monkeypatch.undo()
    assert await sweep(pool, redis_client, grace=timedelta(0), stream=stream_name) == 1
    assert await redis_client.xlen(stream_name) == 2  # at-least-once: consumers deduplicate by document_id


async def test_existing_bucket_passes_the_startup_check(storage):
    await storage.check_bucket()


async def test_missing_bucket_fails_clearly_and_is_not_created(storage):
    import asyncio

    from iw_scraper.ingest.storage import BucketMissing

    name = f"iw-raw-missing-{uuid.uuid4().hex[:10]}"
    missing = Storage(storage.endpoint, storage.access_key, storage.secret_key, bucket=name)
    with pytest.raises(BucketMissing, match=name):
        await missing.check_bucket()
    assert await asyncio.to_thread(missing._client.bucket_exists, name) is False  # checked, never created


class HungRedis:
    async def xadd(self, *args, **kwargs):
        await asyncio.Event().wait()  # never answers


@pytest.mark.parametrize(
    "failure",
    [ValueError("bad timestamp"), asyncpg.InterfaceError("pool closed"), asyncpg.DataError("bad argument"), asyncpg.UniqueViolationError("clash")],
)
async def test_a_failure_that_certainly_did_not_commit_removes_the_object_and_records_an_error(
    pool, storage, redis_client, stream_name, seeded_source, monkeypatch, failure
):
    async def failing_insert(*_args):
        raise failure

    monkeypatch.setattr(pipeline, "insert_document", failing_insert)
    result = await run(Ingestor(pool, storage, redis_client, stream=stream_name), seeded_source)
    assert result.outcome == "failed"
    assert await storage.list_keys() == []
    assert await reasons(pool) == ["storage_error"]


@pytest.mark.parametrize(
    "failure",
    [RuntimeError("boom"), OSError("reset"), ConnectionResetError("reset"), asyncpg.ConnectionDoesNotExistError("connection was closed"),
        asyncpg.QueryCanceledError("cancelled"), asyncpg.AdminShutdownError("shutting down")],
)
async def test_a_failure_that_may_have_committed_keeps_the_object_and_records_an_error(
    pool, storage, redis_client, stream_name, seeded_source, monkeypatch, failure
):
    async def failing_insert(*_args):
        raise failure

    monkeypatch.setattr(pipeline, "insert_document", failing_insert)
    result = await run(Ingestor(pool, storage, redis_client, stream=stream_name), seeded_source)
    assert result.outcome == "failed"
    assert len(await storage.list_keys()) == 1  # an orphan object is harmless; a dangling key is not
    assert await reasons(pool) == ["storage_error"]


@pytest.mark.parametrize("lost_reply", [ConnectionResetError("reply lost"), asyncio.CancelledError()])
async def test_a_lost_reply_after_the_commit_leaves_the_object_the_row_points_at(
    pool, storage, redis_client, stream_name, seeded_source, monkeypatch, lost_reply
):
    real_insert = pipeline.insert_document

    async def commit_then_lose_the_reply(pool_, doc):
        await real_insert(pool_, doc)
        raise lost_reply

    monkeypatch.setattr(pipeline, "insert_document", commit_then_lose_the_reply)
    try:
        await run(Ingestor(pool, storage, redis_client, stream=stream_name), seeded_source)
    except asyncio.CancelledError:
        pass
    async with pool.acquire() as conn:
        key = await conn.fetchval("SELECT html_object_key FROM documents")
    assert key is not None
    assert key in await storage.list_keys()


@pytest.mark.parametrize("html", [None, "", " \n\t "])
async def test_a_page_without_html_records_a_parse_error_and_stores_nothing(
    pool, storage, redis_client, stream_name, seeded_source, html
):
    page = {key: value for key, value in PAGE.items() if key != "html"} | ({} if html is None else {"html": html})
    result = await run(Ingestor(pool, storage, redis_client, stream=stream_name), seeded_source, page)
    assert result.outcome == "failed"
    assert await doc_count(pool) == 0
    assert await storage.list_keys() == []
    assert await reasons(pool) == ["parse_error"]


async def test_cancellation_during_the_insert_keeps_the_object(
    pool, storage, redis_client, stream_name, seeded_source, monkeypatch
):
    started = asyncio.Event()

    async def slow_insert(*_args):
        started.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(pipeline, "insert_document", slow_insert)
    task = asyncio.create_task(run(Ingestor(pool, storage, redis_client, stream=stream_name), seeded_source))
    await asyncio.wait_for(started.wait(), timeout=5)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert len(await storage.list_keys()) == 1  # the insert may already have committed


async def test_nul_character_in_text_fails_cleanly_after_the_upload(
    pool, storage, redis_client, stream_name, seeded_source
):
    page = {**PAGE, "text": "Zysk\x00do 20%"}  # PostgreSQL text cannot hold NUL
    result = await run(Ingestor(pool, storage, redis_client, stream=stream_name), seeded_source, page)
    assert result.outcome == "failed"
    assert await storage.list_keys() == []
    assert await doc_count(pool) == 0
    assert len(await reasons(pool)) == 1


async def test_hung_redis_is_bounded_by_the_publish_timeout(pool, storage, stream_name, seeded_source, monkeypatch):
    monkeypatch.setattr(publisher, "PUBLISH_TIMEOUT_S", 0.05)
    result = await asyncio.wait_for(run(Ingestor(pool, storage, HungRedis(), stream=stream_name), seeded_source), 5)
    assert result.outcome == "inserted"
    assert await reasons(pool) == ["publish_failed"]


async def test_failing_dedup_check_uploads_nothing_and_records_an_error(
    pool, storage, redis_client, stream_name, seeded_source, monkeypatch
):
    async def broken_check(*_args):
        raise asyncpg.InterfaceError("pool closed")

    monkeypatch.setattr(pipeline, "is_duplicate", broken_check)
    result = await run(Ingestor(pool, storage, redis_client, stream=stream_name), seeded_source)
    assert result.outcome == "failed"
    assert await storage.list_keys() == []
    assert await reasons(pool) == ["storage_error"]


@pytest.mark.parametrize("text", ["", "  \n\t "])
async def test_blank_text_records_empty_text_and_stores_nothing(pool, storage, redis_client, stream_name, seeded_source, text):
    result = await run(Ingestor(pool, storage, redis_client, stream=stream_name), seeded_source, {**PAGE, "text": text})
    assert result.outcome == "failed"
    assert result.error.reason is Reason.EMPTY_TEXT
    assert await storage.list_keys() == []
    assert await doc_count(pool) == 0
    assert await reasons(pool) == ["empty_text"]


async def test_returned_error_detail_is_redacted_too(pool, storage, redis_client, stream_name, seeded_source, monkeypatch):
    async def failing_insert(*_args):
        raise RuntimeError("connect to http://user:hunter2@10.0.0.1:5432 failed")

    monkeypatch.setattr(pipeline, "insert_document", failing_insert)
    result = await run(Ingestor(pool, storage, redis_client, stream=stream_name), seeded_source)
    assert "hunter2" not in result.error.detail  # a caller that logs result.error must not leak it


async def test_unexpected_publish_error_after_commit_is_recorded_not_raised(pool, storage, stream_name, seeded_source):
    class BuggyRedis:
        async def xadd(self, *args, **kwargs):
            raise TypeError("client bug")

    result = await run(Ingestor(pool, storage, BuggyRedis(), stream=stream_name), seeded_source)
    assert result.outcome == "inserted"  # the document is stored; the sweep announces it
    assert await reasons(pool) == ["publish_failed"]


async def test_text_that_cannot_be_encoded_is_a_recorded_schema_error(pool, storage, redis_client, stream_name, seeded_source):
    ingestor = Ingestor(pool, storage, redis_client, stream=stream_name)
    result = await run(ingestor, seeded_source, {**PAGE, "text": "abc\ud800"})
    assert result.outcome == "failed"
    assert result.error.reason is Reason.SCHEMA_INVALID
    assert await reasons(pool) == ["schema_invalid"]


async def test_a_lowercase_z_timestamp_the_schema_accepts_is_stored(pool, storage, redis_client, stream_name, seeded_source):
    page = PAGE | {"published_at": "2026-11-21T10:00:00z"}
    result = await run(Ingestor(pool, storage, redis_client, stream=stream_name), seeded_source, page)
    assert result.outcome == "inserted"
    assert (await doc_row(pool, result.document_id))["published_at"] == datetime(2026, 11, 21, 10, 0, tzinfo=timezone.utc)
