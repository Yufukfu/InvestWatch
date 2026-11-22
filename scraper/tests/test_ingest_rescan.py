"""What a re-scan of a web source reports: changed, unchanged, reverted, reappeared (spec `document-ingest`)."""

import json
import logging
from dataclasses import replace
from datetime import datetime, timezone

import pytest

from iw_scraper.ingest import pipeline
from iw_scraper.ingest.errors import record_error
from iw_scraper.ingest.pipeline import Ingestor
from iw_scraper.types import JobError, Reason

FETCHED_AT = datetime(2026, 11, 21, 15, 0, 0, tzinfo=timezone.utc)


def page(text: str) -> dict:
    return {"url": "https://alfa.example.com/konto", "text": text, "html": f"<p>{text}</p>"}


@pytest.fixture
def ingestor(pool, storage, redis_client, stream_name):
    return Ingestor(pool, storage, redis_client, stream=stream_name)


async def scan(ingestor, source, text):
    return await ingestor.ingest(page(text), source, fetched_at=FETCHED_AT, duration_ms=5, proxy=None)


def outcomes(caplog) -> list[dict]:
    lines = [json.loads(r.getMessage()) for r in caplog.records if r.name == "iw_scraper.ingest"]
    return [line for line in lines if line.get("event") == "rescan_outcome"]


async def row_snapshot(pool):
    async with pool.acquire() as conn:
        return [dict(r) for r in await conn.fetch("SELECT * FROM documents ORDER BY id")]


@pytest.fixture(autouse=True)
def log_level(caplog):
    caplog.set_level(logging.INFO, logger="iw_scraper.ingest")


async def test_first_collection_has_no_previous_document_and_no_outcome_line(ingestor, seeded_source, caplog):
    result = await scan(ingestor, seeded_source, "A")
    assert result.outcome == "inserted"
    assert result.previous_document_id is None
    assert outcomes(caplog) == []


async def test_edited_page_is_an_insert_that_names_the_previous_document(ingestor, seeded_source, caplog):
    first = await scan(ingestor, seeded_source, "A")
    second = await scan(ingestor, seeded_source, "B")
    assert second.outcome == "inserted"
    assert second.previous_document_id == first.document_id
    [line] = outcomes(caplog)
    assert line["outcome"] == "changed"
    assert line["source_id"] == seeded_source.id
    assert line["document_id"] == second.document_id


async def test_earlier_rows_keep_every_column_value_when_a_page_changes(pool, ingestor, seeded_source):
    await scan(ingestor, seeded_source, "A")
    before = await row_snapshot(pool)
    await scan(ingestor, seeded_source, "B")
    after = await row_snapshot(pool)
    assert [r for r in after if r["id"] == before[0]["id"]] == before
    assert len(after) == 2


async def test_fourth_version_names_the_third_and_publishes_one_event(ingestor, seeded_source, redis_client, stream_name):
    await scan(ingestor, seeded_source, "A")
    await scan(ingestor, seeded_source, "B")
    third = await scan(ingestor, seeded_source, "C")
    events_before = await redis_client.xlen(stream_name)
    fourth = await scan(ingestor, seeded_source, "D")
    assert fourth.previous_document_id == third.document_id
    assert await redis_client.xlen(stream_name) == events_before + 1


async def test_unchanged_page_inserts_and_publishes_nothing(pool, ingestor, seeded_source, redis_client, stream_name, caplog):
    await scan(ingestor, seeded_source, "A")
    events = await redis_client.xlen(stream_name)
    result = await scan(ingestor, seeded_source, "A")
    assert result.outcome == "duplicate"
    assert [l["outcome"] for l in outcomes(caplog)] == ["unchanged"]
    assert len(await row_snapshot(pool)) == 1
    assert await redis_client.xlen(stream_name) == events


async def test_page_returning_to_an_earlier_text_is_reverted(pool, ingestor, seeded_source, caplog):
    await scan(ingestor, seeded_source, "A")
    await scan(ingestor, seeded_source, "B")
    caplog.clear()
    result = await scan(ingestor, seeded_source, "A")
    assert result.outcome == "duplicate"
    assert [l["outcome"] for l in outcomes(caplog)] == ["reverted"]
    assert len(await row_snapshot(pool)) == 2


async def test_page_back_after_a_removal_is_reappeared(pool, ingestor, seeded_source, caplog):
    await scan(ingestor, seeded_source, "A")
    await record_error(pool, JobError(Reason.GONE, "HTTP 410", seeded_source.id, url=seeded_source.url))
    caplog.clear()
    result = await scan(ingestor, seeded_source, "A")
    assert result.outcome == "duplicate"
    assert [l["outcome"] for l in outcomes(caplog)] == ["reappeared"]


async def test_duplicate_after_losing_the_insert_race_is_classified_too(ingestor, seeded_source, caplog, monkeypatch):
    await scan(ingestor, seeded_source, "A")

    async def pre_check_misses(*_args):
        return False

    monkeypatch.setattr(pipeline, "is_duplicate", pre_check_misses)
    result = await scan(ingestor, seeded_source, "A")
    assert result.outcome == "duplicate"
    assert [l["outcome"] for l in outcomes(caplog)] == ["unchanged"]


async def test_failing_previous_lookup_keeps_the_insert(ingestor, seeded_source, caplog, monkeypatch):
    await scan(ingestor, seeded_source, "A")

    async def broken(*_args):
        raise OSError("connection reset")

    monkeypatch.setattr(pipeline, "previous_document", broken)
    caplog.clear()
    result = await scan(ingestor, seeded_source, "B")
    assert result.outcome == "inserted"
    assert result.previous_document_id is None
    assert result.error is None
    assert outcomes(caplog) == []
    assert any("rescan_lookup_failed" in r.getMessage() for r in caplog.records)


async def test_failing_removal_lookup_keeps_a_duplicate_a_duplicate(pool, ingestor, seeded_source, caplog, monkeypatch):
    await scan(ingestor, seeded_source, "A")

    async def broken(*_args):
        raise OSError("connection reset")

    monkeypatch.setattr(pipeline, "removal_state", broken)
    caplog.clear()
    result = await scan(ingestor, seeded_source, "A")
    assert result.outcome == "duplicate"
    assert result.error is None
    assert outcomes(caplog) == []
    async with pool.acquire() as conn:
        assert await conn.fetchval("SELECT count(*) FROM job_errors") == 0


async def test_rescan_state_is_none_when_the_lookup_fails(ingestor, seeded_source, monkeypatch):
    async def broken(*_args):
        raise OSError("connection reset")

    monkeypatch.setattr(pipeline, "removal_state", broken)
    assert await ingestor.rescan_state(seeded_source.id) is None


async def test_rescan_state_reports_the_stored_document_and_removal(pool, ingestor, seeded_source):
    first = await scan(ingestor, seeded_source, "A")
    state = await ingestor.rescan_state(seeded_source.id)
    assert (state.document_id, state.gone_is_newer) == (first.document_id, False)
    await record_error(pool, JobError(Reason.GONE, "HTTP 404", seeded_source.id, url=seeded_source.url))
    assert (await ingestor.rescan_state(seeded_source.id)).gone_is_newer is True


async def test_a_post_of_a_social_source_is_not_classified(ingestor, seeded_source, caplog):
    post_source = replace(seeded_source, platform="other")
    results = []
    for text in ("A", "B", "B"):
        results.append(
            await ingestor.ingest(
                {"url": "https://t.me/kanal/1", "text": text, "html": f"<p>{text}</p>"},
                post_source,
                fetched_at=FETCHED_AT,
                duration_ms=5,
                proxy=None,
            )
        )
    assert [r.outcome for r in results] == ["inserted", "inserted", "duplicate"]
    assert results[1].previous_document_id is None
    assert outcomes(caplog) == []


async def job_errors(pool):
    async with pool.acquire() as conn:
        return [dict(r) for r in await conn.fetch("SELECT source_id, url, reason, detail FROM job_errors")]


async def test_record_gone_stores_one_row_with_the_source_url_and_logs_gone(pool, ingestor, seeded_source, caplog):
    await ingestor.record_gone(seeded_source, 410)
    [row] = await job_errors(pool)
    assert (str(row["source_id"]), row["url"], row["reason"], row["detail"]) == (
        seeded_source.id, seeded_source.url, "gone", "HTTP 410",
    )
    assert [l["outcome"] for l in outcomes(caplog)] == ["gone"]


async def test_record_gone_again_logs_without_a_second_row(pool, ingestor, seeded_source, caplog):
    await ingestor.record_gone(seeded_source, 404, already_recorded=True)
    assert await job_errors(pool) == []
    assert [l["outcome"] for l in outcomes(caplog)] == ["gone"]


async def test_record_gone_redacts_the_source_url(pool, ingestor, seeded_source):
    secret_source = replace(seeded_source, url="https://user:hunter2@alfa.example.com/ad?token=abc123def")
    await ingestor.record_gone(secret_source, 404)
    [row] = await job_errors(pool)
    assert "hunter2" not in row["url"] and "abc123def" not in row["url"]


async def test_record_gone_never_raises_when_the_sink_fails(ingestor, seeded_source, monkeypatch):
    async def broken(*_args):
        raise OSError("connection reset")

    monkeypatch.setattr(pipeline, "record_error", broken)
    await ingestor.record_gone(seeded_source, 404)
