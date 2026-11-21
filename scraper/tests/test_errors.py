"""The job_errors sink (real PostgreSQL)."""

import time
import uuid

import pytest

from iw_scraper.ingest.errors import record_error, redact
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
        ("proxy http://u:p@ss@10.0.0.1:8080 refused", "ss@"),
        ("proxy http://u:pa/ss@10.0.0.1:8080 refused", "pa/ss"),
        ("proxy user:hunter2@10.0.0.1:8080 refused", "hunter2"),
        ("request failed password=hunter2 retrying", "hunter2"),
        ("auth token=abc123def failed", "abc123def"),
        ("GET /x?access_token=abc123def failed", "abc123def"),
        ("api_key=k-999 rejected", "k-999"),
        ("client_secret=s3cr3t rejected", "s3cr3t"),
        ("X-Amz-Signature=sig-4242 rejected", "sig-4242"),
        ("sessionid=sess-777 expired", "sess-777"),
        ('body {"password": "hunter2"} rejected', "hunter2"),
        ("Authorization: Bearer tok-9999", "tok-9999"),
        ("Proxy-Authorization: Basic dXNlcjpwdw==", "dXNlcjpwdw"),
        ("Cookie: sid=abc-5555; theme=dark", "abc-5555"),
    ],
)
async def test_credentials_are_not_recorded(pool, detail, secret):
    await record_error(pool, JobError(Reason.BLOCKED, detail, None))
    stored = await rows(pool)
    assert secret not in stored[0]["detail"]


async def test_long_detail_is_capped(pool):
    await record_error(pool, JobError(Reason.HTTP_ERROR, "word " * 1000, None))
    assert len((await rows(pool))[0]["detail"]) == 300


async def test_a_source_id_that_is_not_a_uuid_is_kept_in_the_detail_not_lost(pool):
    await record_error(pool, JobError(Reason.INVALID_REQUEST, "unknown source", "not-a-uuid"))
    stored = (await rows(pool))[0]
    assert stored["source_id"] is None
    assert "not-a-uuid" in stored["detail"]


async def test_plain_detail_is_kept_verbatim(pool):
    await record_error(pool, JobError(Reason.HTTP_ERROR, "status 503 from alfa.example.com", None))
    assert (await rows(pool))[0]["detail"] == "status 503 from alfa.example.com"


@pytest.mark.parametrize(
    "hostile",
    ["key" * 2000, "session" * 1500, "a" * 20000, "token=" * 3000, "x:" * 5000, "http://" + "u:p@" * 3000, "-" * 20000],
)
def test_redaction_stays_fast_on_hostile_input(hostile):
    # detail can carry page or proxy text; a backtracking regex must not block the event loop
    started = time.perf_counter()
    redact(hostile)
    assert time.perf_counter() - started < 0.5


@pytest.mark.parametrize(
    "detail,secret",
    [
        ("proxy user:p@ss@10.0.0.1:8080 refused", "ss@"),
        ("sent Bearer abc123xyz to proxy", "abc123xyz"),
        ("sess_id=sid-31337 expired", "sid-31337"),
        ("credential=cred-8080 rejected", "cred-8080"),
        ("passphrase=correct-horse rejected", "correct-horse"),
        ("pass=hunter2 rejected", "hunter2"),
        ("pw=abc-pw rejected", "abc-pw"),
        ("auth=abc123 rejected", "abc123"),
        ("sent Basic dXNlcjpwYXNz to proxy", "dXNlcjpwYXNz"),
        ("proxy http://:hunter2@10.0.0.1:8080 refused", "hunter2"),
    ],
)
def test_residual_credential_shapes_are_redacted(detail, secret):
    assert secret not in redact(detail)


def test_plain_details_survive_redaction():
    for detail in ["status 503 from alfa.example.com", "connect to host:5432 timed out", "Key (source_id)=(x) already exists"]:
        assert redact(detail) == detail


async def test_long_detail_still_keeps_a_non_uuid_source_id(pool):
    await record_error(pool, JobError(Reason.INVALID_REQUEST, "x" * 5000, "not-a-uuid"))
    stored = (await rows(pool))[0]
    assert stored["source_id"] is None
    assert "not-a-uuid" in stored["detail"]
    assert len(stored["detail"]) <= 300


async def test_log_line_does_not_carry_a_secret_source_id(pool, caplog):
    # a scan request can name any string as the source; it reaches the log as well as the table
    with caplog.at_level("WARNING", logger="iw_scraper.ingest"):
        await record_error(pool, JobError(Reason.INVALID_REQUEST, "unknown source", "password=hunter2"))
    assert "job_error" in caplog.text
    assert "hunter2" not in caplog.text


@pytest.mark.parametrize(
    "detail,secret",
    [
        ("(source_id=password=hunter2) unknown source", "hunter2"),
        ("GET /p?a=1&password=hunter2&b=2 failed", "hunter2"),
        ("a=b;token=abc999 rejected", "abc999"),
        ("x=y,secret=s3cr3t-9 rejected", "s3cr3t-9"),
        ("level=warn msg=failed api_key=k-4242", "k-4242"),
    ],
)
def test_a_secret_nested_after_a_harmless_pair_is_still_redacted(detail, secret):
    assert secret not in redact(detail)


@pytest.mark.parametrize(
    "detail",
    [
        "https://user:" + "p" * 2100 + "@host",  # no whitespace at all
        "ab\tuser:" + "p" * 1995 + "\t@host",  # tab, not a space
        "ok user:" + "p" * 2100 + "@host",  # the marker lies past the bound
    ],
)
def test_a_secret_cut_by_the_input_bound_does_not_survive_as_a_fragment(detail):
    assert "ppp" not in redact(detail)


async def test_a_userinfo_cut_in_a_long_source_id_does_not_leak(pool):
    source_id = "user:hunter2" + "x" * 100 + "@host.example"
    await record_error(pool, JobError(Reason.INVALID_REQUEST, "d", source_id))
    assert "hunter2" not in (await rows(pool))[0]["detail"]


async def test_a_userinfo_cut_in_a_long_source_id_does_not_leak_into_the_log(pool, caplog):
    with caplog.at_level("WARNING", logger="iw_scraper.ingest"):
        await record_error(pool, JobError(Reason.INVALID_REQUEST, "d", "user:hunter2" + "x" * 100 + "@host.example"))
    assert "hunter2" not in caplog.text


def test_text_before_a_cut_token_is_kept():
    assert redact("status 503 " + "y" * 3000) == "status 503"


async def test_log_line_has_a_null_source_id_when_there_is_none(pool, caplog):
    with caplog.at_level("WARNING", logger="iw_scraper.ingest"):
        await record_error(pool, JobError(Reason.INVALID_REQUEST, "no source", None))
    assert '"source_id": null' in caplog.text


async def test_a_huge_non_uuid_source_id_does_not_push_the_detail_out(pool):
    await record_error(pool, JobError(Reason.INVALID_REQUEST, "real-detail-text", "s" * 1000))
    stored = (await rows(pool))[0]
    assert "real-detail-text" in stored["detail"]
