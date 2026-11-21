"""The job_errors sink (real PostgreSQL)."""

import uuid

import pytest

from iw_scraper.ingest.errors import record_error
from iw_scraper.types import JobError, Reason


async def rows(pool):
    async with pool.acquire() as conn:
        return await conn.fetch("SELECT source_id, reason, detail FROM job_errors")


@pytest.mark.parametrize("reason", list(Reason))
async def test_each_reason_is_stored(pool, reason):
    await record_error(pool, JobError(reason, "something happened", str(uuid.uuid4())))
    stored = await rows(pool)
    assert [r["reason"] for r in stored] == [reason.value]


async def test_source_id_may_be_null_or_unknown(pool):
    await record_error(pool, JobError(Reason.INVALID_REQUEST, "no such source", None))
    await record_error(pool, JobError(Reason.INVALID_REQUEST, "unknown source", str(uuid.uuid4())))
    assert len(await rows(pool)) == 2


@pytest.mark.parametrize(
    "detail,secret",
    [
        ("proxy http://user:hunter2@10.0.0.1:8080 refused", "hunter2"),
        ("request failed password=hunter2 retrying", "hunter2"),
        ("auth token=abc123def failed", "abc123def"),
        ("api_key=k-999 rejected", "k-999"),
    ],
)
async def test_credentials_are_not_recorded(pool, detail, secret):
    await record_error(pool, JobError(Reason.BLOCKED, detail, None))
    stored = await rows(pool)
    assert secret not in stored[0]["detail"]


async def test_plain_detail_is_kept_verbatim(pool):
    await record_error(pool, JobError(Reason.HTTP_ERROR, "status 503 from alfa.example.com", None))
    assert (await rows(pool))[0]["detail"] == "status 503 from alfa.example.com"
