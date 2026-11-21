"""Dedup and insert against a real PostgreSQL (throwaway schema)."""

import asyncio
import json
import uuid
from datetime import datetime, timezone

from iw_scraper.ingest.document import build_document, content_hash
from iw_scraper.ingest.store import insert_document, is_duplicate

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
    assert row["content_hash"] == content_hash("Zysk do 20%")
    assert row["stream_published_at"] is None
    assert json.loads(row["payload"])["text"] == "Zysk do 20%"


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
            "INSERT INTO sources (id, name, platform, url, source_kind) "
            "VALUES ($1, 'B', 'web', 'https://b.example.com/', 'firm_own')",
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
