"""Dedup and insert against a real PostgreSQL (throwaway schema)."""

import asyncio
import json
import uuid
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from iw_scraper.ingest.document import build_document
from iw_scraper.ingest.errors import record_error
from iw_scraper.ingest.store import insert_document, is_duplicate, previous_document, removal_state
from iw_scraper.types import JobError, Reason

FETCHED_AT = datetime(2026, 11, 21, 15, 0, 0, tzinfo=timezone.utc)


def build(source, text="Zysk do 20%"):
    page = {"url": "https://alfa.example.com/konto", "text": text, "title": "Konto"}
    return build_document(page, source, fetched_at=FETCHED_AT, duration_ms=10, proxy=None)


async def count(pool):
    async with pool.acquire() as conn:
        return await conn.fetchval("SELECT count(*) FROM documents")


async def test_valid_document_is_inserted_with_payload(pool, seeded_source):
    doc = build(seeded_source)
    result = await insert_document(pool, doc)
    assert result.outcome == "inserted"
    assert result.document_id == doc["id"]
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM documents WHERE id = $1", uuid.UUID(doc["id"]))
    assert str(row["source_id"]) == seeded_source.id
    assert row["content_hash"] == "35864f838dfec0cd765ac334f77c5250f3283ccedbb2e7df3eaccf16e32ccf23"
    assert row["stream_published_at"] is None
    assert row["text"] == "Zysk do 20%"
    assert row["title"] == "Konto"
    # only the nested contract fields go into the payload (api/README.md)
    assert json.loads(row["payload"]) == {"scrape_meta": {"scraper": "httpx", "duration_ms": 10, "proxy": None}}


async def test_rerun_of_unchanged_page_is_a_duplicate(pool, seeded_source):
    await insert_document(pool, build(seeded_source))
    second = await insert_document(pool, build(seeded_source))
    assert second.outcome == "duplicate"
    assert second.document_id is None
    assert await count(pool) == 1


async def test_whitespace_only_difference_is_a_duplicate(pool, seeded_source):
    await insert_document(pool, build(seeded_source, "Zysk do 20%"))
    result = await insert_document(pool, build(seeded_source, "Zysk  do 20%\n"))
    assert result.outcome == "duplicate"


async def test_case_difference_is_a_new_row(pool, seeded_source):
    await insert_document(pool, build(seeded_source, "Zysk do 20%"))
    result = await insert_document(pool, build(seeded_source, "ZYSK DO 20%"))
    assert result.outcome == "inserted"
    assert await count(pool) == 2


async def test_changed_page_is_a_new_row_with_a_different_hash(pool, seeded_source):
    await insert_document(pool, build(seeded_source, "Zysk do 20%"))
    await insert_document(pool, build(seeded_source, "Zysk do 25%"))
    async with pool.acquire() as conn:
        hashes = await conn.fetchval("SELECT count(DISTINCT content_hash) FROM documents")
    assert hashes == 2


async def test_same_text_for_another_source_is_not_a_duplicate(pool, seeded_source):
    other = uuid.uuid4()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO sources (id, name, platform, url, source_kind, target_modules) "
            "VALUES ($1, 'B', 'web', 'https://b.example.com/', 'firm_own', ARRAY['M3'])",
            other,
        )
    await insert_document(pool, build(seeded_source))
    doc = build(seeded_source)
    doc["source_id"] = str(other)
    assert (await insert_document(pool, doc)).outcome == "inserted"


async def test_is_duplicate_checks_source_and_hash(pool, seeded_source):
    doc = build(seeded_source)
    assert await is_duplicate(pool, doc["source_id"], doc["content_hash"]) is False
    await insert_document(pool, doc)
    assert await is_duplicate(pool, doc["source_id"], doc["content_hash"]) is True


async def test_is_duplicate_is_scoped_to_the_source(pool, seeded_source):
    doc = build(seeded_source)
    await insert_document(pool, doc)
    assert await is_duplicate(pool, str(uuid.uuid4()), doc["content_hash"]) is False


async def test_parallel_inserts_of_the_same_page_yield_one_row(pool, seeded_source):
    results = await asyncio.gather(*(insert_document(pool, build(seeded_source)) for _ in range(5)))
    assert sorted(r.outcome for r in results) == ["duplicate"] * 4 + ["inserted"]
    assert await count(pool) == 1


def build_post(source, permalink, text="Zysk do 20%"):
    page = {"url": permalink, "canonical_url": permalink, "text": text}
    return build_document(page, replace(source, platform="other"), fetched_at=FETCHED_AT, duration_ms=10, proxy=None)


async def test_identical_text_in_two_posts_is_two_documents(pool, seeded_source):
    first = await insert_document(pool, build_post(seeded_source, "https://t.me/h/1"))
    second = await insert_document(pool, build_post(seeded_source, "https://t.me/h/2"))

    assert (first.outcome, second.outcome) == ("inserted", "inserted")
    assert await count(pool) == 2


async def test_same_post_collected_again_is_a_duplicate(pool, seeded_source):
    await insert_document(pool, build_post(seeded_source, "https://t.me/h/1"))

    again = await insert_document(pool, build_post(seeded_source, "https://t.me/h/1"))

    assert again.outcome == "duplicate"
    assert await count(pool) == 1


async def test_post_edited_between_runs_is_a_second_row_for_the_same_permalink(pool, seeded_source):
    await insert_document(pool, build_post(seeded_source, "https://t.me/h/1"))

    edited = await insert_document(pool, build_post(seeded_source, "https://t.me/h/1", text="Zysk do 30%"))

    assert edited.outcome == "inserted"
    async with pool.acquire() as conn:
        urls = await conn.fetchval("SELECT count(DISTINCT url) FROM documents")
    assert await count(pool) == 2 and urls == 1


T0 = datetime(2026, 11, 20, 10, 0, 0, tzinfo=timezone.utc)


def minutes(n: int) -> datetime:
    return T0 + timedelta(minutes=n)


async def stored(pool, source, text, at: datetime, doc_id: str | None = None) -> str:
    """Insert a version of the page and pin its server-side `created_at`."""
    doc = build(source, text)
    if doc_id is not None:
        doc["id"] = doc_id
    result = await insert_document(pool, doc)
    async with pool.acquire() as conn:
        await conn.execute("UPDATE documents SET created_at = $2 WHERE id = $1", uuid.UUID(result.document_id), at)
    return result.document_id


async def gone_at(pool, source, at: datetime) -> None:
    await record_error(pool, JobError(Reason.GONE, "HTTP 410", source.id, url=source.url))
    async with pool.acquire() as conn:
        await conn.execute("UPDATE job_errors SET occurred_at = $1 WHERE reason = 'gone'", at)


async def test_removal_state_of_a_source_with_no_document(pool, seeded_source):
    state = await removal_state(pool, seeded_source.id)
    assert state.document_id is None
    assert state.content_hash is None
    assert state.gone_is_newer is False


async def test_removal_state_names_the_newest_of_two_documents(pool, seeded_source):
    await stored(pool, seeded_source, "A", minutes(0))
    newest = await stored(pool, seeded_source, "B", minutes(5))
    state = await removal_state(pool, seeded_source.id)
    assert state.document_id == newest
    assert state.content_hash == build(seeded_source, "B")["content_hash"]


async def test_gone_older_than_the_newest_document_is_not_newer(pool, seeded_source):
    await gone_at(pool, seeded_source, minutes(1))
    await stored(pool, seeded_source, "A", minutes(5))
    assert (await removal_state(pool, seeded_source.id)).gone_is_newer is False


async def test_gone_newer_than_the_newest_document_is_newer(pool, seeded_source):
    await stored(pool, seeded_source, "A", minutes(0))
    await gone_at(pool, seeded_source, minutes(5))
    assert (await removal_state(pool, seeded_source.id)).gone_is_newer is True


async def test_gone_at_the_same_instant_as_the_newest_document_is_not_newer(pool, seeded_source):
    await stored(pool, seeded_source, "A", minutes(3))
    await gone_at(pool, seeded_source, minutes(3))
    assert (await removal_state(pool, seeded_source.id)).gone_is_newer is False


async def test_gone_of_another_source_does_not_count(pool, seeded_source):
    await stored(pool, seeded_source, "A", minutes(0))
    await record_error(pool, JobError(Reason.GONE, "HTTP 410", str(uuid.uuid4())))
    assert (await removal_state(pool, seeded_source.id)).gone_is_newer is False


async def test_only_gone_errors_count_as_removal(pool, seeded_source):
    await stored(pool, seeded_source, "A", minutes(0))
    await record_error(pool, JobError(Reason.HTTP_ERROR, "HTTP 503", seeded_source.id))
    assert (await removal_state(pool, seeded_source.id)).gone_is_newer is False


async def test_equal_created_at_makes_the_greater_id_the_newest(pool, seeded_source):
    low, high = "00000000-0000-4000-8000-000000000001", "00000000-0000-4000-8000-000000000002"
    await stored(pool, seeded_source, "A", minutes(0), doc_id=high)
    await stored(pool, seeded_source, "B", minutes(0), doc_id=low)
    assert (await removal_state(pool, seeded_source.id)).document_id == high


async def test_previous_document_is_the_newest_other_row_before_the_new_one(pool, seeded_source):
    await stored(pool, seeded_source, "A", minutes(0))
    second = await stored(pool, seeded_source, "B", minutes(5))
    new = await stored(pool, seeded_source, "C", minutes(10))
    assert await previous_document(pool, seeded_source.id, new) == second


async def test_previous_document_ignores_rows_created_after_the_new_one(pool, seeded_source):
    first = await stored(pool, seeded_source, "A", minutes(0))
    new = await stored(pool, seeded_source, "B", minutes(5))
    await stored(pool, seeded_source, "C", minutes(10))  # a concurrent worker was faster
    assert await previous_document(pool, seeded_source.id, new) == first


async def test_previous_document_of_the_first_row_is_none(pool, seeded_source):
    first = await stored(pool, seeded_source, "A", minutes(0))
    assert await previous_document(pool, seeded_source.id, first) is None


async def test_previous_document_breaks_a_tie_by_id(pool, seeded_source):
    low, high = "00000000-0000-4000-8000-000000000001", "00000000-0000-4000-8000-000000000002"
    await stored(pool, seeded_source, "A", minutes(0), doc_id=high)
    await stored(pool, seeded_source, "B", minutes(0), doc_id=low)
    assert await previous_document(pool, seeded_source.id, high) == low
    assert await previous_document(pool, seeded_source.id, low) is None


async def test_previous_document_is_scoped_to_the_source(pool, seeded_source):
    other = replace(seeded_source, id=str(uuid.uuid4()))
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO sources (id, name, platform, url, source_kind, target_modules) VALUES ($1, 'B', 'web', 'https://b.example.com/', 'unknown', $2)",
            uuid.UUID(other.id), ["M3"],
        )
    await stored(pool, other, "A", minutes(0))
    new = await stored(pool, seeded_source, "B", minutes(5))
    assert await previous_document(pool, seeded_source.id, new) is None
