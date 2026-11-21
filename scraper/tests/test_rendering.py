"""`PageRenderer` over a stub renderer: the order of calls, the shared guards, what a failure becomes."""

import base64
import random
from dataclasses import dataclass, field
from datetime import UTC, datetime

import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer

from iw_scraper.config import render_settings
from iw_scraper.identities import draw_identity, mobile_variant
from iw_scraper.proxy import ProxyChoice
from iw_scraper.rendering import PageRenderer, RenderBudget, RenderCallError, RenderReply, http_renderer, wants_render
from iw_scraper.types import Deferral, Reason
from conftest import make_source

SOURCE = make_source("6b0f7f8e-0000-4000-8000-000000000001", url="https://firm.example.com/oferta")
IDENTITY = draw_identity(random.Random(1))


@dataclass
class Log:
    events: list = field(default_factory=list)


class Limiter:
    def __init__(self, log):
        self.log = log

    async def wait_turn(self, domain):
        self.log.events.append(("wait", domain))


class Pause:
    def __init__(self, log, *, active=False, active_after=None):
        self.log, self.is_active, self.active_after, self.checks = log, active, active_after, 0

    async def active(self, domain):
        self.checks += 1
        self.log.events.append(("pause?", domain))
        return self.is_active or (self.active_after is not None and self.checks > self.active_after)

    async def defer(self, domain, header):
        self.log.events.append(("defer", domain, header))


class Budget:
    def __init__(self, log, *, allow=True):
        self.log, self.allow = log, allow

    async def take(self):
        self.log.events.append(("budget",))
        return self.allow


class Proxies:
    def __init__(self, log, choices=None):
        self.log, self.choices, self.penalized = log, list(choices or [None]), []

    def pick(self):
        return self.choices.pop(0) if len(self.choices) > 1 else self.choices[0]

    def penalize(self, choice):
        self.penalized.append(choice.identifier)


class Renderer:
    """Answers each viewport with a PNG; `fail` maps a viewport to the error it raises."""

    def __init__(self, log, fail=None):
        self.log, self.fail, self.payloads = log, fail or {}, []

    async def __call__(self, payload, timeout):
        self.payloads.append((payload, timeout))
        self.log.events.append(("call", payload["viewport"]))
        if payload["viewport"] in self.fail:
            raise self.fail[payload["viewport"]]
        return RenderReply(
            png=b"PNG-" + payload["viewport"].encode(), browser_version="147.0.1", truncated=False,
            blocks=({"viewport": payload["viewport"], "text": "t"},),
        )


def make(*, fail=None, pause=None, budget=None, proxies=None, clock=None, timeout=90.0, ports=(80, 443)):
    log = Log()
    renderer = Renderer(log, fail)
    page_renderer = PageRenderer(
        renderer, Limiter(log), pause or Pause(log), budget or Budget(log), timeout_seconds=timeout, ports=ports,
        **({"clock": clock} if clock else {}),
    )
    return page_renderer, renderer, log, proxies or Proxies(log)


async def test_one_call_per_viewport_in_order_each_after_the_rate_limit_and_the_pause_check():
    page_renderer, renderer, log, proxies = make()

    output = await page_renderer.render(SOURCE, SOURCE.url, IDENTITY, proxies)

    assert list(output.screenshots) == ["desktop", "mobile", "tablet"]
    assert output.screenshots["mobile"] == b"PNG-mobile"
    assert output.errors == () and output.skipped is None and output.browser_version == "147.0.1"
    assert [b["viewport"] for b in output.blocks] == ["desktop", "mobile", "tablet"]  # in call order
    host = "firm.example.com"
    assert log.events == [
        ("pause?", host), ("budget",),
        ("wait", host), ("pause?", host), ("call", "desktop"),
        ("wait", host), ("pause?", host), ("call", "mobile"),
        ("wait", host), ("pause?", host), ("call", "tablet"),
    ]


async def test_the_mobile_call_carries_the_mobile_variant_and_the_others_the_runs_identity():
    page_renderer, renderer, _, proxies = make()

    await page_renderer.render(SOURCE, SOURCE.url, IDENTITY, proxies)

    by_viewport = {payload["viewport"]: payload for payload, _ in renderer.payloads}
    assert by_viewport["desktop"]["headers"] == dict(IDENTITY.headers) == by_viewport["tablet"]["headers"]
    assert by_viewport["mobile"]["headers"] == dict(mobile_variant(IDENTITY).headers)
    assert by_viewport["desktop"]["source_host"] == "firm.example.com"
    assert by_viewport["desktop"]["url"] == SOURCE.url and by_viewport["desktop"]["ports"] == [80, 443]


async def test_each_call_uses_the_proxy_picked_for_it_and_never_names_it_elsewhere():
    log = Log()
    choices = [ProxyChoice("http://u:secret@p1:8080", "p1"), ProxyChoice("http://u:secret@p2:8080", "p2")]
    page_renderer, renderer, _, proxies = make(proxies=Proxies(log, choices))

    output = await page_renderer.render(SOURCE, SOURCE.url, IDENTITY, proxies)

    assert [payload["proxy"] for payload, _ in renderer.payloads] == [
        "http://u:secret@p1:8080", "http://u:secret@p2:8080", "http://u:secret@p2:8080",
    ]
    assert "secret" not in repr(output)


async def test_no_proxy_means_no_proxy_field():
    page_renderer, renderer, _, proxies = make()

    await page_renderer.render(SOURCE, SOURCE.url, IDENTITY, proxies)

    assert all("proxy" not in payload for payload, _ in renderer.payloads)


async def test_a_paused_domain_skips_the_render_without_an_error_or_a_budget_use():
    log = Log()
    page_renderer, renderer, log, proxies = make(pause=Pause(log, active=True))

    output = await page_renderer.render(SOURCE, SOURCE.url, IDENTITY, proxies)

    assert output.skipped == "paused" and output.errors == () and output.screenshots == {}
    assert renderer.payloads == [] and ("budget",) not in log.events


async def test_a_spent_budget_skips_the_render_without_an_error():
    log = Log()
    page_renderer, renderer, log, proxies = make(budget=Budget(log, allow=False))

    output = await page_renderer.render(SOURCE, SOURCE.url, IDENTITY, proxies)

    assert output.skipped == "budget" and output.errors == () and renderer.payloads == []


async def test_a_pause_that_starts_between_viewports_ends_the_render_and_keeps_nothing():
    log = Log()
    page_renderer, renderer, log, proxies = make(pause=Pause(log, active_after=2))

    output = await page_renderer.render(SOURCE, SOURCE.url, IDENTITY, proxies)

    assert output.skipped == "paused" and output.screenshots == {} and output.errors == ()
    assert [payload["viewport"] for payload, _ in renderer.payloads] == ["desktop"]


async def test_a_block_ends_the_render_records_blocked_and_passes_the_retry_after_on():
    log = Log()
    choices = [ProxyChoice("http://u:secret@p1:8080", "p1")]
    page_renderer, renderer, log, proxies = make(
        fail={"mobile": RenderCallError("blocked", "HTTP 429", retry_after="120")}, proxies=Proxies(log, choices)
    )

    output = await page_renderer.render(SOURCE, SOURCE.url, IDENTITY, proxies)

    assert [e.reason for e in output.errors] == [Reason.BLOCKED] and output.errors[0].detail == "HTTP 429"
    assert output.screenshots == {} and output.errors[0].source_id == SOURCE.id
    assert [payload["viewport"] for payload, _ in renderer.payloads] == ["desktop", "mobile"]  # tablet not tried
    assert ("defer", "firm.example.com", "120") in log.events and proxies.penalized == ["p1"]


@pytest.mark.parametrize(
    ("error", "reason"),
    [
        (RenderCallError("refused", "navigation away from the source site"), Reason.BLOCKED_TARGET),
        (RenderCallError("failed", "browser error: Error"), Reason.RENDER_FAILED),
        (RenderCallError("invalid_request", "field 'url' is not a readable URL"), Reason.RENDER_FAILED),
        (RenderCallError("unreachable", "renderer did not answer"), Reason.RENDER_FAILED),
    ],
)
async def test_other_failures_map_to_their_reason_and_cost_no_retry_after_or_proxy_penalty(error, reason):
    page_renderer, _, log, proxies = make(fail={"desktop": error})

    output = await page_renderer.render(SOURCE, SOURCE.url, IDENTITY, proxies)

    assert [e.reason for e in output.errors] == [reason] and output.screenshots == {}
    assert not [e for e in log.events if e[0] == "defer"] and proxies.penalized == []


async def test_each_call_gets_the_time_left_of_the_one_deadline():
    now = [100.0]

    class Slow(Renderer):
        async def __call__(self, payload, timeout):
            now[0] += 30.0
            return await super().__call__(payload, timeout)

    log = Log()
    renderer = Slow(log)
    page_renderer = PageRenderer(
        renderer, Limiter(log), Pause(log), Budget(log), timeout_seconds=90.0, ports=(80, 443), clock=lambda: now[0]
    )

    output = await page_renderer.render(SOURCE, SOURCE.url, IDENTITY, Proxies(log))

    assert [payload["timeout_seconds"] for payload, _ in renderer.payloads] == [90.0, 60.0, 30.0]
    assert list(output.screenshots) == ["desktop", "mobile", "tablet"]


async def test_a_spent_deadline_fails_the_render_before_the_next_call():
    now = [0.0]

    class Slow(Renderer):
        async def __call__(self, payload, timeout):
            now[0] += 100.0
            return await super().__call__(payload, timeout)

    log = Log()
    renderer = Slow(log)
    page_renderer = PageRenderer(
        renderer, Limiter(log), Pause(log), Budget(log), timeout_seconds=90.0, ports=(80,), clock=lambda: now[0]
    )

    output = await page_renderer.render(SOURCE, SOURCE.url, IDENTITY, Proxies(log))

    assert [e.reason for e in output.errors] == [Reason.RENDER_FAILED] and "time" in output.errors[0].detail
    assert [payload["viewport"] for payload, _ in renderer.payloads] == ["desktop"] and output.screenshots == {}


async def test_a_proxy_deferral_skips_the_render_as_paused():
    log = Log()
    deferral = Deferral(until=datetime(2030, 1, 1, tzinfo=UTC))
    page_renderer, renderer, _, proxies = make(proxies=Proxies(log, [deferral]))

    output = await page_renderer.render(SOURCE, SOURCE.url, IDENTITY, proxies)

    assert output.skipped == "paused" and renderer.payloads == []


class FakeRedis:
    def __init__(self):
        self.values, self.expiries = {}, {}

    async def set(self, key, value, ex=None, nx=False):
        if nx and key in self.values:
            return None
        self.values[key] = value
        self.expiries[key] = ex
        return True

    async def incr(self, key):
        self.values[key] = int(self.values.get(key, 0)) + 1
        return self.values[key]


async def test_the_budget_counts_per_utc_hour_and_refuses_beyond_the_limit():
    redis, hour = FakeRedis(), [datetime(2026, 11, 21, 12, 59, tzinfo=UTC)]
    budget = RenderBudget(redis, 2, clock=lambda: hour[0])

    assert [await budget.take() for _ in range(3)] == [True, True, False]
    hour[0] = datetime(2026, 11, 21, 13, 0, tzinfo=UTC)
    assert await budget.take() is True
    assert sorted(redis.values) == ["iw:scraper:render:2026112112", "iw:scraper:render:2026112113"]
    assert all(expiry >= 3600 for expiry in redis.expiries.values())


def test_settings_default_to_off_and_parse_booleans_explicitly(monkeypatch):
    for name in ("SCRAPER_RENDER_ENABLED", "SCRAPER_RENDER_MAX_PER_HOUR", "RENDERER_URL", "RENDER_TIMEOUT_SECONDS"):
        monkeypatch.delenv(name, raising=False)
    defaults = render_settings(attempt_timeout=60.0)
    assert (defaults.enabled, defaults.max_per_hour, defaults.url, defaults.timeout_seconds) == (
        False, 20, "http://renderer:8080", 90.0,
    )
    monkeypatch.setenv("SCRAPER_RENDER_ENABLED", "false")  # `bool("false")` is True: it must not be read that way
    assert render_settings(attempt_timeout=60.0).enabled is False
    monkeypatch.setenv("SCRAPER_RENDER_ENABLED", "TRUE")
    assert render_settings(attempt_timeout=200.0).enabled is True


def test_enabled_without_room_for_the_render_in_the_attempt_refuses_to_start(monkeypatch):
    monkeypatch.setenv("SCRAPER_RENDER_ENABLED", "true")
    monkeypatch.setenv("RENDER_TIMEOUT_SECONDS", "90")

    with pytest.raises(ValueError, match="SCRAPER_ATTEMPT_TIMEOUT.*RENDER_TIMEOUT_SECONDS"):
        render_settings(attempt_timeout=149.0)
    assert render_settings(attempt_timeout=150.0).enabled is True
    monkeypatch.setenv("SCRAPER_RENDER_ENABLED", "false")
    assert render_settings(attempt_timeout=10.0).enabled is False  # a disabled render needs no room


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("SCRAPER_RENDER_ENABLED", "maybe"),
        ("SCRAPER_RENDER_MAX_PER_HOUR", "-1"),
        ("SCRAPER_RENDER_MAX_PER_HOUR", "many"),
        ("RENDERER_URL", "file:///etc"),
        ("RENDERER_URL", "renderer:8080"),
        ("RENDERER_URL", "ftp://renderer:8080"),
        ("RENDER_TIMEOUT_SECONDS", "0"),
    ],
)
def test_unusable_settings_are_refused_without_echoing_the_value(monkeypatch, name, value):
    monkeypatch.setenv(name, value)

    with pytest.raises(ValueError, match=name) as refused:
        render_settings(attempt_timeout=300.0)
    assert value not in str(refused.value)


async def test_a_truncated_viewport_marks_the_whole_render_truncated():
    class Truncating(Renderer):
        async def __call__(self, payload, timeout):
            reply = await super().__call__(payload, timeout)
            return RenderReply(reply.png, reply.browser_version, payload["viewport"] == "mobile")

    log = Log()
    page_renderer = PageRenderer(
        Truncating(log), Limiter(log), Pause(log), Budget(log), timeout_seconds=90.0, ports=(80,)
    )

    output = await page_renderer.render(SOURCE, SOURCE.url, IDENTITY, Proxies(log))

    assert output.truncated is True


@pytest.mark.parametrize(
    ("fields", "expected"),
    [
        ({"source_kind": "firm_own", "target_modules": ("M2",)}, True),
        ({"source_kind": "firm_own", "target_modules": ("M2",), "active": False}, False),
        ({"source_kind": "firm_own", "target_modules": ("M2",), "platform": "youtube"}, False),
        ({"source_kind": "third_party", "target_modules": ("M2",)}, False),
        ({"source_kind": "firm_own", "target_modules": ("M1", "M3")}, False),
    ],
)
def test_wants_render_is_a_collectable_firm_own_m2_source(fields, expected):
    from dataclasses import replace

    assert wants_render(replace(SOURCE, **fields)) is expected


async def serve(handler):
    app = web.Application()
    app.add_routes([web.post("/render", handler)])
    server = TestServer(app)
    await server.start_server()
    return server


async def test_the_http_call_returns_the_decoded_picture():
    seen = []

    async def handler(request):
        seen.append(await request.json())
        return web.json_response(
            {
                "png_base64": base64.b64encode(b"PNG").decode(), "browser_version": "147.0.1", "truncated": True,
                "blocks": [{"text": "a"}],
            }
        )

    server = await serve(handler)
    try:
        reply = await http_renderer(f"http://127.0.0.1:{server.port}")({"viewport": "desktop"}, 5.0)
    finally:
        await server.close()

    assert reply == RenderReply(b"PNG", "147.0.1", True, ({"text": "a"},)) and seen == [{"viewport": "desktop"}]


@pytest.mark.parametrize(
    ("status", "body", "kind", "detail", "retry_after"),
    [
        (403, {"error": {"kind": "blocked", "detail": "HTTP 429", "retry_after": "120"}}, "blocked", "HTTP 429", "120"),
        (422, {"error": {"kind": "refused", "detail": "navigation away"}}, "refused", "navigation away", None),
        (502, {"error": {"kind": "failed", "detail": "browser error: Error"}}, "failed", "browser error: Error", None),
        (400, {"error": {"kind": "invalid_request", "detail": "bad field"}}, "invalid_request", "bad field", None),
        (500, {"unexpected": True}, "failed", "renderer answered HTTP 500", None),
        (200, {"png_base64": "!!!", "browser_version": "1", "truncated": False}, "failed", "renderer reply is malformed", None),
        (200, {"browser_version": "1"}, "failed", "renderer reply is malformed", None),
        (200, {"png_base64": "", "browser_version": "1", "truncated": False, "blocks": "no"}, "failed", "renderer reply is malformed", None),
        (200, {"png_base64": "", "browser_version": "1", "truncated": False, "blocks": ["no"]}, "failed", "renderer reply is malformed", None),
    ],
)
async def test_the_http_call_turns_an_error_answer_into_a_render_call_error(status, body, kind, detail, retry_after):
    async def handler(request):
        return web.json_response(body, status=status)

    server = await serve(handler)
    try:
        with pytest.raises(RenderCallError) as error:
            await http_renderer(f"http://127.0.0.1:{server.port}")({}, 5.0)
    finally:
        await server.close()

    assert (error.value.kind, error.value.detail, error.value.retry_after) == (kind, detail, retry_after)


async def test_a_renderer_that_is_down_or_answers_garbage_is_unreachable():
    async def garbage(request):
        return web.Response(text="<html>not json</html>")

    server = await serve(garbage)
    try:
        port = server.port
        with pytest.raises(RenderCallError) as garbled:
            await http_renderer(f"http://127.0.0.1:{port}")({}, 5.0)
    finally:
        await server.close()
    with pytest.raises(RenderCallError) as down:
        await http_renderer(f"http://127.0.0.1:{port}")({}, 5.0)  # nothing listens there now

    assert garbled.value.kind == down.value.kind == "unreachable"
    assert "127.0.0.1" not in down.value.detail


async def test_a_reply_larger_than_the_cap_is_refused_unread(monkeypatch):
    monkeypatch.setattr("iw_scraper.rendering.MAX_REPLY_BYTES", 50)

    async def handler(request):
        return web.json_response({"png_base64": "A" * 400, "browser_version": "1", "truncated": False})

    server = await serve(handler)
    try:
        with pytest.raises(RenderCallError, match="too large"):
            await http_renderer(f"http://127.0.0.1:{server.port}")({}, 5.0)
    finally:
        await server.close()


class Gate:
    def __init__(self, deferral=None):
        self.deferral, self.deferred = deferral, []

    async def check(self, domain):
        return self.deferral

    async def defer_for_retry_after(self, domain, header):
        self.deferred.append((domain, header))


class Health:
    def __init__(self, seconds):
        self.seconds = seconds

    async def paused_for(self):
        return self.seconds


@pytest.mark.parametrize(
    ("deferral", "cooldown", "active"),
    [(None, 0, False), (Deferral(until=datetime(2030, 1, 1, tzinfo=UTC)), 0, True), (None, 12.5, True)],
)
async def test_a_domain_is_paused_by_the_retry_after_gate_or_the_failure_cooldown(deferral, cooldown, active):
    from iw_scraper.rendering import DomainPause

    pause = DomainPause(Gate(deferral), lambda domain: Health(cooldown))

    assert await pause.active("firm.example.com") is active


async def test_a_retry_after_goes_to_the_gate():
    from iw_scraper.rendering import DomainPause

    gate = Gate()

    await DomainPause(gate, lambda domain: Health(0)).defer("firm.example.com", "120")

    assert gate.deferred == [("firm.example.com", "120")]
