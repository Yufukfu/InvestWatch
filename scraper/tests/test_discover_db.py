"""Discovery against the real `sources` and `documents` tables (columns of `api/migrations` 0001)."""

import json
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from iw_scraper.discover import Candidate, discover, insert_candidate

NOW = datetime(2026, 11, 21, 12, 0, tzinfo=UTC)


async def add_source(pool, url, *, active=True, modules=("M2",), name="Alfa", cron="0 * * * *"):
    source_id = uuid.uuid4()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO sources (id, name, platform, url, source_kind, target_modules, schedule_cron, active)"
            " VALUES ($1, $2, 'web', $3, 'firm_own', $4, $5, $6)",
            source_id, name, url, list(modules), cron, active,
        )
    return source_id


async def add_document(pool, source_id, links, *, age=timedelta(hours=1), payload=None):
    """A stored document; `links` is a list of hrefs, or `payload` is used as the raw payload."""
    body = payload if payload is not None else {"links": [{"href": href} for href in links]}
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO documents (id, source_id, platform, source_kind, url, fetched_at, text, payload)"
            " VALUES ($1, $2, 'web', 'firm_own', $3, $4, 'tekst', $5::jsonb)",
            uuid.uuid4(), source_id, f"https://doc.example/{uuid.uuid4()}", NOW - age, json.dumps(body),
        )


async def sources(pool):
    async with pool.acquire() as conn:
        return await conn.fetch("SELECT * FROM sources ORDER BY url")


async def run(pool, **kw):
    return await discover(pool, since_hours=kw.pop("since_hours", 168), limit=kw.pop("limit", 20), now=NOW, **kw)


async def test_a_recent_documents_link_becomes_an_inactive_manual_candidate(pool):
    parent = await add_source(pool, "https://alfa.example/")
    await add_document(pool, parent, ["https://finfluencer.example/oferta?utm_source=x"])

    report = await run(pool)

    rows = [r for r in await sources(pool) if r["id"] != parent]
    assert len(rows) == 1
    row = rows[0]
    assert (row["name"], row["platform"], row["url"], row["source_kind"]) == (
        "[candidate] finfluencer.example", "web", "https://finfluencer.example/oferta", "unknown",
    )
    assert (row["active"], row["schedule_cron"], list(row["target_modules"])) == (False, None, ["M2"])
    assert report.inserted == 1


async def test_an_old_document_is_ignored_and_the_since_boundary_is_inclusive(pool):
    parent = await add_source(pool, "https://alfa.example/")
    await add_document(pool, parent, ["https://old.example/"], age=timedelta(hours=24, seconds=1))
    await add_document(pool, parent, ["https://edge.example/"], age=timedelta(hours=24))

    report = await run(pool, since_hours=24)

    assert [r["url"] for r in await sources(pool) if r["id"] != parent] == ["https://edge.example/"]
    assert report.inserted == 1


async def test_malformed_stored_links_are_skipped_and_the_rest_are_processed(pool):
    parent = await add_source(pool, "https://alfa.example/")
    await add_document(pool, parent, [], payload={"links": "https://not-a-list.example/"})
    await add_document(pool, parent, [], payload={})
    await add_document(pool, parent, [], payload={"links": None})
    await add_document(pool, parent, [], payload={"links": [
        {"href": 5}, "https://bare-string.example/", None, {"nohref": 1}, {"href": "https://ok.example/"},
    ]})

    report = await run(pool)

    assert [r["url"] for r in await sources(pool) if r["id"] != parent] == ["https://ok.example/"]
    assert report.links_read == 1


async def test_a_document_without_a_source_gives_the_fallback_modules(pool):
    await add_document(pool, None, ["https://orphan.example/"])

    await run(pool)

    assert [list(r["target_modules"]) for r in await sources(pool)] == [["M1"]]


async def test_modules_are_the_union_over_the_sources_that_link_to_the_host(pool):
    m2 = await add_source(pool, "https://alfa.example/", modules=("M2",))
    m3 = await add_source(pool, "https://beta.example/", modules=("M3",))
    await add_document(pool, m2, ["https://shared.example/a"])
    await add_document(pool, m3, ["https://shared.example/b"])

    await run(pool)

    row = next(r for r in await sources(pool) if "shared" in r["url"])
    assert list(row["target_modules"]) == ["M2", "M3"]


async def test_a_second_run_over_the_same_data_inserts_nothing(pool):
    parent = await add_source(pool, "https://alfa.example/")
    await add_document(pool, parent, ["https://new.example/"])

    first = await run(pool)
    second = await run(pool)

    assert (first.inserted, second.inserted) == (1, 0)
    assert len(await sources(pool)) == 2


@pytest.mark.parametrize("active", [True, False])
async def test_a_host_any_source_uses_is_not_proposed_again(pool, active):
    parent = await add_source(pool, "https://alfa.example/")
    await add_source(pool, "https://www.known.example/page", active=active)
    await add_document(pool, parent, ["https://known.example/other"])

    report = await run(pool)

    assert report.inserted == 0
    assert len(await sources(pool)) == 2


@pytest.mark.parametrize("registered", ["https://known.example./x", "https://KNOWN.Example/x", "http://www.known.example:80/x"])
async def test_a_registered_url_is_matched_by_host_however_it_is_written(pool, registered):
    parent = await add_source(pool, "https://alfa.example/")
    await add_source(pool, registered, active=False)
    await add_document(pool, parent, ["https://known.example/other"])

    report = await run(pool)

    assert report.inserted == 0


async def test_a_source_row_with_an_unparseable_url_does_not_stop_the_run(pool):
    parent = await add_source(pool, "https://alfa.example/")
    await add_source(pool, "http://[abc")
    await add_document(pool, parent, ["https://new.example/"])

    report = await run(pool)

    assert report.inserted == 1


async def test_existing_sources_and_documents_are_left_untouched(pool):
    parent = await add_source(pool, "https://alfa.example/")
    await add_document(pool, parent, ["https://new.example/"])
    async with pool.acquire() as conn:
        before_docs = await conn.fetch("SELECT * FROM documents ORDER BY id")
    before_sources = [dict(r) for r in await sources(pool)]

    await run(pool)

    async with pool.acquire() as conn:
        after_docs = await conn.fetch("SELECT * FROM documents ORDER BY id")
    after_sources = [dict(r) for r in await sources(pool) if r["id"] == parent]
    assert [dict(r) for r in after_docs] == [dict(r) for r in before_docs]
    assert after_sources == before_sources


async def test_a_dry_run_reports_the_candidates_and_writes_nothing(pool):
    parent = await add_source(pool, "https://alfa.example/")
    await add_document(pool, parent, ["https://new.example/"])

    report = await run(pool, dry_run=True)

    assert [c.url for c in report.candidates] == ["https://new.example/"]
    assert report.inserted == 0
    assert len(await sources(pool)) == 1


async def test_the_cap_inserts_the_most_linked_hosts_and_reports_the_rest(pool):
    parent = await add_source(pool, "https://alfa.example/")
    await add_document(pool, parent, ["https://a.example/", "https://a.example/", "https://a.example/",
                                      "https://b.example/", "https://b.example/", "https://c.example/"])

    report = await run(pool, limit=2)

    assert sorted(r["url"] for r in await sources(pool) if r["id"] != parent) == ["https://a.example/", "https://b.example/"]
    assert (report.inserted, report.skipped_by_cap, report.hosts_considered, report.links_read) == (2, 1, 3, 6)


async def test_the_insert_itself_refuses_a_url_that_a_source_already_has(pool):
    await add_source(pool, "https://taken.example/")

    inserted = await insert_candidate(pool, Candidate(url="https://taken.example/", host="taken.example",
                                                      modules=("M1",), links=1))

    assert inserted is False
    assert len(await sources(pool)) == 1
