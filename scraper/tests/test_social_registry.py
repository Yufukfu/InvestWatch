import pytest

from iw_scraper.social.registry import CollectorRegistry, registry
from iw_scraper.types import Source


def collector(body, final_url):  # a stand-in; the registry never calls it
    raise AssertionError("not called")


def other_collector(body, final_url):
    raise AssertionError("not called")


def source(url: str, *, platform: str = "other", active: bool = True) -> Source:
    return Source(
        id="11111111-1111-4111-8111-111111111111",
        name="s",
        platform=platform,
        url=url,
        source_kind="unknown",
        target_modules=("M3",),
        active=active,
        schedule_cron="15 */6 * * *",
    )


def test_host_with_a_collector_returns_it():
    reg = CollectorRegistry()
    reg.register("t.me", collector)

    assert reg.for_url("https://t.me/s/SubeTradingPL") is collector


def test_host_without_a_collector_returns_none():
    assert CollectorRegistry().for_url("https://t.me/s/SubeTradingPL") is None


def test_www_and_bare_host_are_one_host():
    reg = CollectorRegistry()
    reg.register("www.example.com", collector)

    assert reg.for_url("https://example.com/a") is collector


def test_duplicate_registration_is_refused():
    reg = CollectorRegistry()
    reg.register("t.me", collector)

    with pytest.raises(ValueError):
        reg.register("T.ME", other_collector)

    assert reg.for_url("https://t.me/s/x") is collector


def test_telegram_is_registered_by_default():
    assert registry.for_url("https://t.me/s/SubeTradingPL") is not None


def test_social_source_with_a_collector_is_collectable():
    assert source("https://t.me/s/SubeTradingPL").collectable is True


def test_inactive_social_source_is_not_collectable():
    assert source("https://t.me/s/SubeTradingPL", active=False).collectable is False


def test_non_web_source_without_a_collector_is_not_collectable():
    assert source("https://example.pl/profile").collectable is False
    assert source("https://example.pl/profile", platform="facebook").collectable is False


def test_web_source_stays_collectable_on_any_host():
    assert source("https://example.pl/", platform="web").collectable is True
