import asyncio
import logging
import os
import time
import uuid

import pytest
import redis.asyncio as aioredis
from redis.exceptions import ConnectionError as RedisConnectionError

from iw_scraper.config import rate_limit_settings
from iw_scraper.ratelimit import DomainLimiter, LocalLimiter, domain_key

INTERVAL = 0.5
SLACK = 0.05  # scheduler jitter allowed on a measured gap


@pytest.fixture
async def redis_url():
    url = os.environ.get("REDIS_URL")
    if not url:
        pytest.fail("REDIS_URL is not set: these tests need a Redis (see scraper/CLAUDE.md)")
    return url


@pytest.fixture
async def client(redis_url):
    connection = aioredis.from_url(redis_url)
    yield connection
    await connection.aclose()


@pytest.fixture
def prefix() -> str:
    return f"iw-test:{uuid.uuid4().hex}:"  # one namespace per test, so tests never see each other's slots


def worker(client, prefix: str, interval: float = INTERVAL) -> DomainLimiter:
    return DomainLimiter(client, interval, key_prefix=prefix)


async def test_the_first_request_for_a_domain_starts_at_once(client, prefix):
    waited = await worker(client, prefix).wait_turn("example.org")

    assert waited == 0


async def test_two_workers_share_one_slot_per_domain(client, prefix):
    one, two = worker(client, prefix), worker(client, prefix)
    started: list[float] = []

    async def go(limiter: DomainLimiter) -> None:
        await limiter.wait_turn("example.org")
        started.append(time.monotonic())

    await asyncio.gather(go(one), go(two))

    assert max(started) - min(started) >= INTERVAL - SLACK


async def test_the_wait_reported_is_the_time_slept(client, prefix):
    limiter = worker(client, prefix)
    await limiter.wait_turn("example.org")

    before = time.monotonic()
    waited = await limiter.wait_turn("example.org")

    assert INTERVAL - 0.15 < waited <= INTERVAL
    assert time.monotonic() - before >= waited - SLACK


async def test_different_domains_do_not_wait_for_each_other(client, prefix):
    limiter = worker(client, prefix)
    await limiter.wait_turn("one.example")

    assert await limiter.wait_turn("two.example") == 0


async def test_www_and_the_bare_domain_share_a_slot(client, prefix):
    limiter = worker(client, prefix)
    await limiter.wait_turn("example.org")

    assert await limiter.wait_turn("https://www.Example.org/page") > 0
    assert await limiter.wait_turn("WWW.example.org") > 0


async def test_a_gap_in_requests_leaves_no_debt(client, prefix):
    limiter = worker(client, prefix, interval=0.2)
    await limiter.wait_turn("example.org")
    await asyncio.sleep(0.3)

    assert await limiter.wait_turn("example.org") == 0


async def test_a_reserved_slot_outlives_a_pause_in_requests(client, prefix):
    limiter = worker(client, prefix)
    await limiter.wait_turn("example.org")
    await asyncio.sleep(0.15)

    assert await limiter.wait_turn("example.org") > 0.2  # the slot is still 0.35 s away, not forgotten


async def test_the_slot_key_expires_so_idle_domains_leave_nothing_behind(client, prefix):
    await worker(client, prefix).wait_turn("example.org")

    ttl = await client.pttl(prefix + "example.org")

    assert 0 < ttl <= 60_000


async def test_when_redis_is_unreachable_requests_are_still_spaced_locally_with_a_warning(caplog):
    broken = aioredis.from_url("redis://127.0.0.1:1/0", socket_connect_timeout=0.2)
    limiter = DomainLimiter(broken, 0.3)

    with caplog.at_level(logging.WARNING):
        first = await limiter.wait_turn("example.org")
        before = time.monotonic()
        second = await limiter.wait_turn("example.org")

    assert first == 0
    assert time.monotonic() - before >= 0.3 - SLACK
    assert 0.15 < second <= 0.3
    assert any("rate limit" in r.getMessage().lower() and "local" in r.getMessage().lower() for r in caplog.records)
    await broken.aclose()


async def test_the_fallback_warning_does_not_leak_the_redis_url(caplog):
    broken = aioredis.from_url("redis://user:hunter2@127.0.0.1:1/0", socket_connect_timeout=0.2)

    with caplog.at_level(logging.WARNING):
        await DomainLimiter(broken, 0.1).wait_turn("example.org")

    assert "hunter2" not in caplog.text
    await broken.aclose()


class Flaky:
    """A Redis client whose `eval` answers from a script: an exception to raise, or a wait in ms."""

    def __init__(self, *answers) -> None:
        self.answers = list(answers)

    async def eval(self, *args):
        answer = self.answers.pop(0)
        if isinstance(answer, BaseException):
            raise answer
        return answer


@pytest.mark.parametrize("error", [RedisConnectionError("down"), OSError("reset"), asyncio.TimeoutError()])
async def test_any_connection_level_failure_falls_back_to_the_local_limiter(error):
    limiter = DomainLimiter(Flaky(error, error), 0.1)

    assert await limiter.wait_turn("example.org") == 0
    assert 0 < await limiter.wait_turn("example.org") <= 0.1


async def test_the_fallback_warns_once_per_outage_and_again_after_a_recovery(caplog):
    down = RedisConnectionError("down")
    limiter = DomainLimiter(Flaky(down, down, down, 0, down), 0.01)

    with caplog.at_level(logging.WARNING):
        for _ in range(3):
            await limiter.wait_turn("example.org")
        assert len(caplog.records) == 1
        await limiter.wait_turn("example.org")  # Redis is back
        await limiter.wait_turn("example.org")  # and gone again

    assert len(caplog.records) == 2


class FakeTime:
    def __init__(self) -> None:
        self.now = 100.0
        self.slept: list[float] = []

    def clock(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


async def test_the_local_limiter_spaces_starts_one_interval_apart():
    fake = FakeTime()
    limiter = LocalLimiter(2.0, clock=fake.clock, sleep=fake.sleep)

    waits = [await limiter.wait_turn("example.org") for _ in range(3)]

    assert waits == [0, 2.0, 2.0]
    assert fake.slept == [2.0, 2.0]


async def test_concurrent_local_callers_each_get_their_own_slot():
    fake = FakeTime()

    async def frozen_sleep(seconds: float) -> None:  # callers wait without moving the clock
        fake.slept.append(seconds)

    limiter = LocalLimiter(2.0, clock=fake.clock, sleep=frozen_sleep)

    waits = sorted(await asyncio.gather(*(limiter.wait_turn("example.org") for _ in range(3))))

    assert waits == [0, 2.0, 4.0]


async def test_the_local_limiter_forgives_idle_time_and_keeps_domains_apart():
    fake = FakeTime()
    limiter = LocalLimiter(2.0, clock=fake.clock, sleep=fake.sleep)
    await limiter.wait_turn("example.org")
    fake.now += 10

    assert await limiter.wait_turn("example.org") == 0
    assert await limiter.wait_turn("other.example") == 0


@pytest.mark.parametrize("interval", [0, -1.0, float("inf"), float("nan")])
def test_an_interval_that_could_not_space_anything_is_refused(interval):
    with pytest.raises(ValueError, match="interval"):
        LocalLimiter(interval)
    with pytest.raises(ValueError, match="interval"):
        DomainLimiter(None, interval)


@pytest.mark.parametrize(
    "url, key",
    [
        ("https://www.knf.gov.pl/ostrzezenia", "knf.gov.pl"),
        ("http://KNF.gov.pl:8080/x", "knf.gov.pl"),
        ("https://sub.www.example.org/", "sub.www.example.org"),
        ("https://wwwexample.org/", "wwwexample.org"),
    ],
)
def test_the_domain_key_is_the_lowercase_host_without_a_leading_www(url, key):
    assert domain_key(url) == key


def test_the_settings_default_to_a_five_second_gap_and_a_local_redis(monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.delenv("DOMAIN_MIN_INTERVAL_SECONDS", raising=False)

    assert rate_limit_settings() == ("redis://localhost:6379/0", 5.0)


def test_the_settings_read_the_environment(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://cache:6380/2")
    monkeypatch.setenv("DOMAIN_MIN_INTERVAL_SECONDS", "1.5")

    assert rate_limit_settings() == ("redis://cache:6380/2", 1.5)


@pytest.mark.parametrize("value", ["0", "-2", "inf", "nan", "abc"])
def test_a_gap_that_is_not_positive_is_refused(monkeypatch, value):
    monkeypatch.setenv("DOMAIN_MIN_INTERVAL_SECONDS", value)

    with pytest.raises(ValueError, match="DOMAIN_MIN_INTERVAL_SECONDS"):
        rate_limit_settings()
