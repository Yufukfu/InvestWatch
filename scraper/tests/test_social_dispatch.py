"""`Collector.run_source` dispatching a registration with no page parser to its flow by platform: a fetch-path flow
(identity, session, proxy and the robots check come from the shared layer) and a home-IP flow (none of them)."""

import pytest

from conftest import FakeSourceStore, make_source
from iw_scraper.collect import Collector
from iw_scraper.fetch import FetchFailure
from iw_scraper.jobs import AttemptResult
from iw_scraper.ratelimit import host_key
from iw_scraper.robots import RobotsVerdict
from iw_scraper.social.registry import Registration, registry
from iw_scraper.targets import AddressGuard, UrlGuard
from iw_scraper.types import Reason
from test_collect_social import NOW, SRC, Harness, Limiter, Rotator, page, resolver

HOST = "flows.example"
URL = f"https://{HOST}/some_handle"


class SpyRotator(Rotator):
    def __init__(self, calls):
        super().__init__()
        self.calls = calls

    def start_run(self):
        self.calls.append("rotation")
        return super().start_run()


def register(monkeypatch, flow, *, home_ip=False, platform="fakeplatform", valid_url=lambda url: True):
    monkeypatch.setitem(
        registry._by_host, host_key(HOST),
        Registration(parse=None, platform=platform, valid_url=valid_url, flow=flow, home_ip=home_ip),
    )


def make(h: Harness, *, platform="fakeplatform", url=URL, allowed=(HOST,)) -> Collector:
    store = FakeSourceStore()
    store.permissive = False
    store.sources[SRC] = make_source(SRC, platform=platform, url=url)
    guard = UrlGuard(allowed)

    async def urls():
        return guard

    return Collector(
        store, type("I", (), {"ingest": h.ingest})(), urls=urls, addresses=AddressGuard(resolver),
        rotator=SpyRotator(h.calls), limiter=Limiter(h.calls), stages=h.stages(), clock=lambda: NOW,
    )


async def run(collector, h):
    async def started():
        h.calls.append("started")

    return await collector.run_source(SRC, started)


async def test_fetch_path_flow_gets_the_runs_identity_session_proxy_and_robots_check(monkeypatch):
    h = Harness({URL: page(URL, b"<html>ok</html>")})
    seen = {}

    async def flow(ctx):
        assert await ctx.check_robots() is None
        result = await ctx.fetch(URL)
        seen.update(identity=ctx.identity, session=ctx.session, proxy=ctx.proxy, body=result.body)
        return AttemptResult(documents=1)

    register(monkeypatch, flow)

    result = await run(make(h), h)

    assert (result.documents, result.error) == (1, None)
    assert h.calls == ["rotation", "started", "wait", "robots", "wait", "fetch", "close"]
    assert seen["identity"] is h.identity and seen["session"] is not None and seen["proxy"] is not None
    assert seen["body"] == b"<html>ok</html>"


async def test_fetch_path_flow_robots_refusal_is_a_blocked_error_and_no_page_is_requested(monkeypatch):
    h = Harness({URL: page(URL, b"")}, robots=RobotsVerdict(False, "robots.txt disallows this path"))

    async def flow(ctx):
        if (refusal := await ctx.check_robots()) is not None:
            return refusal
        await ctx.fetch(URL)
        return AttemptResult(documents=1)

    register(monkeypatch, flow)

    result = await run(make(h), h)

    assert result.error.reason is Reason.BLOCKED and "robots" in result.error.detail
    assert "fetch" not in h.calls


async def test_fetch_path_flow_failure_is_mapped_and_the_session_is_closed(monkeypatch):
    h = Harness({})

    async def flow(ctx):
        raise FetchFailure(Reason.BLOCKED, "HTTP 429", None, "60", 429)

    register(monkeypatch, flow)

    result = await run(make(h), h)

    assert (result.error.reason, result.http_status, result.retry_after) == (Reason.BLOCKED, 429, 60.0)
    assert h.calls[-1] == "close"


async def test_home_ip_flow_skips_identity_session_robots_and_rotation_but_waits_one_turn(monkeypatch):
    h = Harness({})
    seen = {}

    async def flow(ctx):
        h.calls.append("flow")
        seen.update(identity=ctx.identity, session=ctx.session, proxy=ctx.proxy, source=ctx.source)
        return AttemptResult(documents=2)

    register(monkeypatch, flow, home_ip=True)
    collector = make(h)

    def forbidden(*_):
        raise AssertionError("a home-IP flow must not draw an identity or open a session")

    collector._stages = type(collector._stages)(
        open_session=forbidden, close_session=forbidden, check_robots=forbidden, fetch=forbidden,
        draw_identity=forbidden,
    )

    result = await run(collector, h)

    assert (result.documents, result.error) == (2, None)
    assert h.calls == ["started", "wait", "flow"]
    assert (seen["identity"], seen["session"], seen["proxy"]) == (None, None, None)
    assert seen["source"].url == URL


async def test_home_ip_flow_still_passes_the_url_guard(monkeypatch):
    h = Harness({})

    async def flow(ctx):
        h.calls.append("flow")
        return AttemptResult(documents=1)

    register(monkeypatch, flow, home_ip=True)

    result = await run(make(h, url=f"https://{HOST}:8080/some_handle"), h)

    assert result.error.reason is Reason.BLOCKED_TARGET and "port" in result.error.detail
    assert h.calls == []


async def test_home_ip_flow_refuses_a_host_that_resolves_to_an_internal_address(monkeypatch):
    h = Harness({})

    async def flow(ctx):
        h.calls.append("flow")
        return AttemptResult(documents=1)

    register(monkeypatch, flow, home_ip=True)
    collector = make(h)

    async def internal(host):
        return ["10.0.0.5"]

    collector._addresses = AddressGuard(internal)

    result = await run(collector, h)

    assert result.error.reason is Reason.BLOCKED_TARGET
    assert h.calls == []


async def test_home_ip_flow_block_is_reported_as_a_failure_with_its_reason(monkeypatch):
    h = Harness({})

    async def flow(ctx):
        raise FetchFailure(Reason.BLOCKED, "account restricted", None)

    register(monkeypatch, flow, home_ip=True)

    result = await run(make(h), h)

    assert result.error.reason is Reason.BLOCKED and result.error.detail == "account restricted"


@pytest.mark.parametrize("home_ip", [False, True])
async def test_wrong_url_form_is_invalid_request_with_no_request(monkeypatch, home_ip):
    h = Harness({})

    async def flow(ctx):
        h.calls.append("flow")
        return AttemptResult(documents=1)

    register(monkeypatch, flow, home_ip=home_ip, valid_url=lambda url: False)

    result = await run(make(h), h)

    assert result.error.reason is Reason.INVALID_REQUEST
    assert h.calls == []


async def test_platform_the_host_does_not_take_is_invalid_request_with_no_request(monkeypatch):
    h = Harness({})

    async def flow(ctx):
        h.calls.append("flow")
        return AttemptResult(documents=1)

    register(monkeypatch, flow, home_ip=True, platform="fakeplatform")

    result = await run(make(h, platform="other"), h)

    assert result.error.reason is Reason.INVALID_REQUEST
    assert h.calls == []
