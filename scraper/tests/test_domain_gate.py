import asyncio
import os
import time
import uuid
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime

import pytest
import redis.asyncio as aioredis

from iw_scraper.domaingate import DomainGate
from iw_scraper.types import Deferral

START = datetime(2026, 11, 21, 12, 0, 0, tzinfo=timezone.utc)
CAP = 300.0
THRESHOLD = 5
PAUSE = 600.0


class Clock:
    def __init__(self) -> None:
        self.now = START

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += timedelta(seconds=seconds)


@pytest.fixture
async def client():
    url = os.environ.get("REDIS_URL")
    if not url:
        pytest.fail("REDIS_URL is not set: these tests need a Redis (see scraper/CLAUDE.md)")
    connection = aioredis.from_url(url)
    yield connection
    await connection.aclose()


@pytest.fixture
def prefix() -> str:
    return f"iw-test:{uuid.uuid4().hex}:"


@pytest.fixture
def clock() -> Clock:
    return Clock()


def gate(client, prefix, clock, **kwargs) -> DomainGate:
    options = {"max_retry_after": CAP, "failure_threshold": THRESHOLD, "pause_seconds": PAUSE}
    return DomainGate(client, clock=clock, key_prefix=prefix, **options | kwargs)


async def fail(g: DomainGate, times: int, domain: str = "example.org") -> None:
    for _ in range(times):
        await g.record_outcome(domain, success=False)


async def test_a_domain_nobody_has_complained_about_is_not_deferred(client, prefix, clock):
    assert await gate(client, prefix, clock).check("example.org") is None


async def test_retry_after_in_seconds_defers_the_domain_for_every_worker(client, prefix, clock):
    one, two = gate(client, prefix, clock), gate(client, prefix, clock)

    until = await one.defer_for_retry_after("example.org", "30")

    assert until == START + timedelta(seconds=30)
    assert await two.check("example.org") == Deferral(until=START + timedelta(seconds=30))


async def test_the_deferral_ends_when_the_wait_has_passed(client, prefix, clock):
    g = gate(client, prefix, clock)
    await g.defer_for_retry_after("example.org", "30")

    clock.advance(29)
    assert await g.check("example.org") is not None
    clock.advance(1)
    assert await g.check("example.org") is None


async def test_a_huge_retry_after_is_capped(client, prefix, clock):
    g = gate(client, prefix, clock)

    until = await g.defer_for_retry_after("example.org", "86400")

    assert until == START + timedelta(seconds=CAP)
    assert await g.check("example.org") == Deferral(until=START + timedelta(seconds=CAP))


async def test_an_absurdly_large_number_of_seconds_is_capped_not_an_error(client, prefix, clock):
    until = await gate(client, prefix, clock).defer_for_retry_after("example.org", "9" * 30)

    assert until == START + timedelta(seconds=CAP)


async def test_a_retry_after_of_thousands_of_digits_is_capped_not_a_crash(client, prefix, clock):
    until = await gate(client, prefix, clock).defer_for_retry_after("example.org", "9" * 5000)

    assert until == START + timedelta(seconds=CAP)


async def test_retry_after_as_an_http_date(client, prefix, clock):
    g = gate(client, prefix, clock)
    header = format_datetime(START + timedelta(seconds=20), usegmt=True)

    until = await g.defer_for_retry_after("example.org", header)

    assert until == START + timedelta(seconds=20)
    assert await g.check("example.org") == Deferral(until=START + timedelta(seconds=20))


async def test_a_date_far_in_the_future_is_capped_too(client, prefix, clock):
    header = format_datetime(START + timedelta(days=30), usegmt=True)

    until = await gate(client, prefix, clock).defer_for_retry_after("example.org", header)

    assert until == START + timedelta(seconds=CAP)


@pytest.mark.parametrize("header", [None, "", "  ", "soon", "-5", "30.5", "1e3", "0", "٣٠", "Mon, 99 Foo 2026"])
async def test_a_retry_after_that_asks_for_no_wait_defers_nothing(client, prefix, clock, header):
    g = gate(client, prefix, clock)

    assert await g.defer_for_retry_after("example.org", header) is None
    assert await g.check("example.org") is None


async def test_a_date_without_a_zone_is_read_as_utc(client, prefix, clock):
    g = gate(client, prefix, clock)

    until = await g.defer_for_retry_after("example.org", "Sat, 21 Nov 2026 12:00:20 -0000")

    assert until == START + timedelta(seconds=20)


async def test_a_date_in_the_past_defers_nothing(client, prefix, clock):
    header = format_datetime(START - timedelta(seconds=60), usegmt=True)
    g = gate(client, prefix, clock)

    assert await g.defer_for_retry_after("example.org", header) is None
    assert await g.check("example.org") is None


async def test_a_later_shorter_retry_after_never_shortens_the_deferral(client, prefix, clock):
    g = gate(client, prefix, clock)
    await g.defer_for_retry_after("example.org", "120")

    await g.defer_for_retry_after("example.org", "10")

    assert await g.check("example.org") == Deferral(until=START + timedelta(seconds=120))


async def test_a_longer_retry_after_extends_the_deferral(client, prefix, clock):
    g = gate(client, prefix, clock)
    await g.defer_for_retry_after("example.org", "10")

    await g.defer_for_retry_after("example.org", "120")

    assert await g.check("example.org") == Deferral(until=START + timedelta(seconds=120))


async def test_a_deferral_binds_only_its_own_domain_and_its_www_twin(client, prefix, clock):
    g = gate(client, prefix, clock)
    await g.defer_for_retry_after("example.org", "30")

    assert await g.check("www.example.org") is not None
    assert await g.check("https://www.example.org/page") is not None
    assert await g.check("other.example") is None


async def test_the_deferral_key_expires_so_old_deferrals_leave_nothing_behind(client, prefix, clock):
    await gate(client, prefix, clock).defer_for_retry_after("example.org", "30")

    keys = [k async for k in client.scan_iter(match=prefix + "*")]
    ttls = [await client.pttl(k) for k in keys]

    assert len(keys) == 1 and all(30_000 <= ttl <= 3_600_000 for ttl in ttls)  # outlives the 30 s it must hold


async def test_the_pause_key_expires_after_it_has_outlived_the_pause(client, prefix, clock):
    await fail(gate(client, prefix, clock), THRESHOLD)

    keys = [k async for k in client.scan_iter(match=prefix + "*")]
    ttls = [await client.pttl(k) for k in keys]

    assert len(keys) == 1 and all(int(PAUSE * 1000) <= ttl <= 3_600_000 for ttl in ttls)


async def test_fewer_failures_than_the_threshold_do_not_pause_the_domain(client, prefix, clock):
    g = gate(client, prefix, clock)

    await fail(g, THRESHOLD - 1)

    assert await g.check("example.org") is None


async def test_the_threshold_th_failure_in_a_row_pauses_the_domain_for_every_worker(client, prefix, clock):
    one, two = gate(client, prefix, clock), gate(client, prefix, clock)

    await fail(one, THRESHOLD - 1)
    await fail(two, 1)

    assert await one.check("example.org") == Deferral(until=START + timedelta(seconds=PAUSE))


async def test_the_pause_ends_after_the_cooldown(client, prefix, clock):
    g = gate(client, prefix, clock)
    await fail(g, THRESHOLD)

    clock.advance(PAUSE - 1)
    assert await g.check("example.org") is not None
    clock.advance(1)
    assert await g.check("example.org") is None


async def test_a_success_resets_the_failure_count(client, prefix, clock):
    g = gate(client, prefix, clock)
    await fail(g, THRESHOLD - 1)

    await g.record_outcome("example.org", success=True)
    await fail(g, THRESHOLD - 1)

    assert await g.check("example.org") is None


async def test_after_a_pause_the_count_starts_again_from_zero(client, prefix, clock):
    g = gate(client, prefix, clock)
    await fail(g, THRESHOLD)
    clock.advance(PAUSE)

    await fail(g, THRESHOLD - 1)
    assert await g.check("example.org") is None

    await fail(g, 1)
    assert await g.check("example.org") is not None


async def test_failures_are_counted_per_domain(client, prefix, clock):
    g = gate(client, prefix, clock)

    await fail(g, THRESHOLD - 1, "one.example")
    await fail(g, THRESHOLD - 1, "two.example")

    assert await g.check("one.example") is None
    assert await g.check("two.example") is None


async def test_a_success_does_not_lift_a_pause_that_is_running(client, prefix, clock):
    g = gate(client, prefix, clock)
    await fail(g, THRESHOLD)

    await g.record_outcome("example.org", success=True)

    assert await g.check("example.org") is not None


async def test_a_pause_never_shortens_a_longer_deferral(client, prefix, clock):
    g = gate(client, prefix, clock, pause_seconds=60.0)
    await g.defer_for_retry_after("example.org", "200")

    await fail(g, THRESHOLD)

    assert await g.check("example.org") == Deferral(until=START + timedelta(seconds=200))


async def test_check_reports_whichever_of_deferral_and_pause_ends_later(client, prefix, clock):
    g = gate(client, prefix, clock)
    await fail(g, THRESHOLD)  # paused until +600
    await g.defer_for_retry_after("example.org", "120")

    assert await g.check("example.org") == Deferral(until=START + timedelta(seconds=PAUSE))

    other = gate(client, prefix, clock, pause_seconds=60.0)
    await fail(other, THRESHOLD, "two.example")  # paused until +60
    await other.defer_for_retry_after("two.example", "120")

    assert await other.check("two.example") == Deferral(until=START + timedelta(seconds=120))


class Hung:
    async def mget(self, *args):
        await asyncio.sleep(3600)

    async def eval(self, *args):
        await asyncio.sleep(3600)


@pytest.mark.parametrize(
    "call",
    [
        lambda g: g.check("example.org"),
        lambda g: g.defer_for_retry_after("example.org", "30"),
        lambda g: g.record_outcome("example.org", success=False),
    ],
    ids=["check", "defer", "record"],
)
async def test_a_redis_that_never_answers_fails_the_call_instead_of_hanging(monkeypatch, clock, call):
    monkeypatch.setattr("iw_scraper.domaingate.REDIS_TIMEOUT_SECONDS", 0.2)
    hung = DomainGate(Hung(), clock=clock, max_retry_after=CAP, failure_threshold=THRESHOLD, pause_seconds=PAUSE)
    started = time.monotonic()

    with pytest.raises(TimeoutError):
        await asyncio.wait_for(call(hung), 2)  # the outer limit only stops a gate without its own timeout

    assert time.monotonic() - started < 1.5


@pytest.mark.parametrize(
    "kwargs",
    [
        {"max_retry_after": 0},
        {"max_retry_after": float("inf")},
        {"max_retry_after": float("nan")},
        {"failure_threshold": 0},
        {"pause_seconds": 0},
        {"pause_seconds": float("nan")},
        {"pause_seconds": float("inf")},
    ],
)
def test_a_gate_that_could_never_work_is_refused(kwargs):
    options = {"max_retry_after": CAP, "failure_threshold": THRESHOLD, "pause_seconds": PAUSE} | kwargs

    with pytest.raises(ValueError):
        DomainGate(None, **options)
