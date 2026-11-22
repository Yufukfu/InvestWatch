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

    assert reg.for_url("https://t.me/s/SubeTradingPL").parse is collector


def test_host_without_a_collector_returns_none():
    assert CollectorRegistry().for_url("https://t.me/s/SubeTradingPL") is None


def test_www_and_bare_host_are_one_host():
    reg = CollectorRegistry()
    reg.register("www.example.com", collector)

    assert reg.for_url("https://example.com/a").parse is collector


def test_duplicate_registration_is_refused():
    reg = CollectorRegistry()
    reg.register("t.me", collector)

    with pytest.raises(ValueError):
        reg.register("T.ME", other_collector)

    assert reg.for_url("https://t.me/s/x").parse is collector


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


def test_platform_the_collector_does_not_accept_is_not_collectable():
    assert source("https://t.me/s/SubeTradingPL", platform="facebook").collectable is False
    assert source("https://t.me/s/SubeTradingPL", platform="forum").collectable is False


async def flow(ctx):  # a stand-in; the registry never calls it
    raise AssertionError("not called")


def test_flow_registration_is_returned_with_its_home_ip_mode():
    reg = CollectorRegistry()
    reg.register("x.com", flow=flow, platform="x", home_ip=True)

    found = reg.for_url("https://x.com/uknf")
    assert (found.parse, found.flow, found.home_ip) == (None, flow, True)


@pytest.mark.parametrize("kwargs", [{}, {"parse": collector, "flow": flow}])
def test_registration_names_a_parser_or_a_flow_not_both_and_not_neither(kwargs):
    reg = CollectorRegistry()
    parse = kwargs.get("parse")
    with pytest.raises(ValueError, match="parser or a flow"):
        reg.register("x.com", parse, flow=kwargs.get("flow"))


def test_home_ip_mode_needs_a_flow():
    reg = CollectorRegistry()
    with pytest.raises(ValueError, match="home_ip"):
        reg.register("x.com", collector, home_ip=True)
