from datetime import datetime, timezone

import pytest

from iw_scraper.types import Deferral, JobError, Reason, Source

EXPECTED_REASONS = {
    "blocked",
    "blocked_target",
    "timeout",
    "http_error",
    "parse_error",
    "empty_text",
    "schema_invalid",
    "storage_error",
    "publish_failed",
    "invalid_request",
}


def test_reason_is_the_closed_set_from_the_spec():
    assert {r.value for r in Reason} == EXPECTED_REASONS


def test_job_error_carries_reason_detail_and_optional_source():
    err = JobError(reason=Reason.BLOCKED, detail="HTTP 403")

    assert err.reason is Reason.BLOCKED
    assert err.detail == "HTTP 403"
    assert err.source_id is None


def test_job_error_rejects_a_plain_string_reason():
    with pytest.raises(ValueError):
        JobError(reason="oops", detail="x")


def test_source_is_collectable_only_when_active_and_web():
    base = dict(
        id="11111111-1111-4111-8111-111111111111",
        name="KNF warnings",
        url="https://www.knf.gov.pl/dla_konsumenta/ostrzezenia_publiczne",
        source_kind="unknown",
        target_modules=("M3",),
        schedule_cron=None,
    )

    assert Source(platform="web", active=True, **base).collectable is True
    assert Source(platform="web", active=False, **base).collectable is False
    assert Source(platform="facebook", active=True, **base).collectable is False


def test_deferral_holds_the_time_it_ends():
    until = datetime(2026, 11, 21, 16, 0, tzinfo=timezone.utc)

    assert Deferral(until=until).until == until
