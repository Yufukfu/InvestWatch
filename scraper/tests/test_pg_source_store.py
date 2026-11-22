"""`PgSourceStore` against the real `sources` table (the columns of `api/migrations` 0001)."""

import json
import uuid
from datetime import UTC, datetime

import pytest

from iw_scraper.pgstore import PgSourceStore


async def add(pool, *, platform="web", active=True, cron="0 * * * *", url="https://alfa.example.com/page"):
    source_id = uuid.uuid4()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO sources (id, name, platform, url, source_kind, target_modules, schedule_cron, active)"
            " VALUES ($1, 'Alfa', $2, $3, 'firm_own', ARRAY['M2','M3'], $4, $5)",
            source_id, platform, url, cron, active,
        )
    return str(source_id)


async def row(pool, source_id):
    async with pool.acquire() as conn:
        return await conn.fetchrow("SELECT last_run_at, last_run_status FROM sources WHERE id = $1", uuid.UUID(source_id))


async def test_get_returns_the_source_as_the_domain_type(pool):
    source_id = await add(pool)

    source = await PgSourceStore(pool).get(source_id)

    assert (source.id, source.platform, source.url, source.source_kind) == (
        source_id, "web", "https://alfa.example.com/page", "firm_own",
    )
    assert (source.target_modules, source.active, source.schedule_cron) == (("M2", "M3"), True, "0 * * * *")


async def test_get_returns_none_for_an_unknown_source(pool):
    assert await PgSourceStore(pool).get(str(uuid.uuid4())) is None


async def test_get_returns_none_for_an_id_that_is_not_a_uuid(pool):
    assert await PgSourceStore(pool).get("not-a-uuid") is None


async def test_mark_running_then_finished_writes_only_the_run_columns(pool):
    store = PgSourceStore(pool)
    source_id = await add(pool)
    at = datetime(2026, 11, 21, 12, 0, tzinfo=UTC)

    await store.mark_running(source_id)
    assert (await row(pool, source_id))["last_run_status"] == "running"

    await store.mark_finished(source_id, at=at, status="partial")
    after = await row(pool, source_id)
    assert (after["last_run_at"], after["last_run_status"]) == (at, "partial")


async def test_mark_finished_for_a_deleted_source_does_not_raise(pool):
    await PgSourceStore(pool).mark_finished(str(uuid.uuid4()), at=datetime.now(UTC), status="ok")


@pytest.mark.parametrize("flag", ["inactive", "other_platform"])
async def test_schedulable_lists_only_active_web_sources_with_a_cron(pool, flag):
    keep = await add(pool)
    await add(pool, active=flag != "inactive", platform="web" if flag == "inactive" else "x")
    await add(pool, cron=None)

    ids = {s.id for s in await PgSourceStore(pool).schedulable()}

    assert ids == {keep}


async def test_collectable_lists_active_web_sources_with_or_without_a_cron(pool):
    scheduled = await add(pool)
    manual = await add(pool, cron=None)
    await add(pool, active=False)
    await add(pool, platform="x")

    ids = {s.id for s in await PgSourceStore(pool).collectable()}

    assert ids == {scheduled, manual}


CHANNEL = "https://t.me/s/kdpwiadomosci"


async def test_a_telegram_channel_is_schedulable_and_collectable(pool):
    channel = await add(pool, platform="other", url=CHANNEL)
    web = await add(pool)

    store = PgSourceStore(pool)

    assert {s.id for s in await store.schedulable()} == {channel, web}
    assert {s.id for s in await store.collectable()} == {channel, web}


async def test_a_row_of_platform_other_on_a_host_without_a_collector_is_not_listed(pool):
    await add(pool, platform="other", url="https://example.com/s/kdpwiadomosci")

    store = PgSourceStore(pool)

    assert [s.id for s in await store.schedulable()] == []
    assert [s.id for s in await store.collectable()] == []


async def add_document(pool, url, *, transcript=None):
    meta = {} if transcript is None else {"scrape_meta": {"transcript": transcript}}
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO documents (id, platform, source_kind, url, fetched_at, text, payload)"
            " VALUES ($1, 'youtube', 'unknown', $2, now(), 'tekst', $3::jsonb)",
            uuid.uuid4(), url, json.dumps(meta),
        )


async def test_known_urls_returns_only_the_urls_that_have_a_stored_document(pool):
    stored, other = "https://www.youtube.com/watch?v=AAAAAAAAAAA", "https://www.youtube.com/watch?v=BBBBBBBBBBB"
    await add_document(pool, stored)

    known = await PgSourceStore(pool).known_urls([stored, other])

    assert known == {stored}


@pytest.mark.parametrize("transcript", ["failed", "none", "caption"])
async def test_a_stored_video_is_known_whatever_its_transcript_outcome(pool, transcript):
    url = "https://www.youtube.com/watch?v=CCCCCCCCCCC"
    await add_document(pool, url, transcript=transcript)

    assert await PgSourceStore(pool).known_urls([url]) == {url}


async def test_known_urls_of_nothing_is_empty_and_asks_nothing(pool):
    assert await PgSourceStore(pool).known_urls([]) == set()
