"""`Collector.run_source` over stubbed stages: the order of guards, `started()`, robots, fetch, parse and ingest,
and how each failure becomes an `AttemptResult` (the queue decides what to do with it)."""

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta

import pytest

from iw_scraper.collect import Collector, Stages, retry_after_seconds
from iw_scraper.fetch import FetchDeferred, FetchFailure, FetchResult
from iw_scraper.ingest.store import IngestResult
from iw_scraper.parsing import ParsedPage, ParseFailure
from iw_scraper.robots import RobotsVerdict
from iw_scraper.targets import AddressGuard, UrlGuard
from iw_scraper.types import Deferral, JobError, Reason
from conftest import FakeSourceStore, make_source

SRC = "6b0f7f8e-0000-4000-8000-000000000001"
URL = "https://alfa.example.com/page"
NOW = datetime(2026, 11, 21, 12, 0, tzinfo=UTC)


class Calls(list):
    def __call__(self, name):
        self.append(name)


@dataclass
class Harness:
    calls: Calls = field(default_factory=Calls)
    robots: RobotsVerdict = RobotsVerdict(True, "ok")
    fetch_raises: Exception | None = None
    parse_raises: Exception | None = None
    ingest_result: IngestResult = IngestResult("inserted", document_id="d1")
    ingested: list = field(default_factory=list)
    closed: int = 0

    def stages(self) -> Stages:
        async def check_robots(url, identity, proxy, **kw):
            self.calls("robots")
            return self.robots

        async def fetch(url, identity, proxy, **kw):
            self.calls("fetch")
            if self.fetch_raises:
                raise self.fetch_raises
            return FetchResult(URL, 200, "text/html; charset=utf-8", b"<html>hello</html>", {}, "proxy-1")

        def parse(body, content_type, final_url):
            self.calls("parse")
            if self.parse_raises:
                raise self.parse_raises
            return ParsedPage("Title", URL, "hello", ("https://alfa.example.com/x",))

        async def close(session):
            self.closed += 1

        return Stages(
            open_session=lambda identity: object(), close_session=close, check_robots=check_robots,
            fetch=fetch, parse=parse, draw_identity=lambda: object(),
        )

    async def ingest(self, page, source, *, fetched_at, duration_ms, proxy):
        self.calls("ingest")
        self.ingested.append((page, source, proxy))
        return self.ingest_result


class Limiter:
    def __init__(self, calls):
        self.calls, self.domains = calls, []

    async def wait_turn(self, domain):
        self.calls("wait")
        self.domains.append(domain)
        return 0.0


class Run:
    def __init__(self, deferral):
        self._deferral = deferral

    def deferral(self):
        return self._deferral


class Rotator:
    def __init__(self, deferral=None):
        self.deferral = deferral

    def start_run(self):
        return Run(self.deferral)


async def resolver(host):
    return ["93.184.216.34"]


def static_urls(hosts):
    guard = UrlGuard(hosts)

    async def urls():
        return guard

    return urls


def make(harness, *, source_url=URL, hosts=("alfa.example.com",), source=True, rotator=None):
    store = FakeSourceStore()
    store.permissive = False
    if source:
        store.sources[SRC] = make_source(SRC, url=source_url)
    ingestor = type("I", (), {"ingest": harness.ingest})()
    limiter = Limiter(harness.calls)
    collector = Collector(
        store, ingestor, urls=static_urls(hosts), addresses=AddressGuard(resolver), rotator=rotator or Rotator(),
        limiter=limiter, stages=harness.stages(), clock=lambda: NOW,
    )
    return collector, limiter


async def run(collector, harness):
    async def started():
        harness.calls("started")

    return await collector.run_source(SRC, started)


async def test_a_page_becomes_a_document_in_the_documented_order():
    h = Harness()
    collector, limiter = make(h)

    result = await run(collector, h)

    assert (result.documents, result.error) == (1, None)
    assert h.calls == ["started", "wait", "robots", "wait", "fetch", "parse", "ingest"]
    assert limiter.domains == ["alfa.example.com", "alfa.example.com"]
    page, source, proxy = h.ingested[0]
    assert (page["text"], page["title"], page["http_status"], page["html"]) == ("hello", "Title", 200, "<html>hello</html>")
    assert (source.id, proxy) == (SRC, "proxy-1")


async def test_a_duplicate_page_is_ok_with_no_document_and_no_error():
    h = Harness(ingest_result=IngestResult("duplicate"))
    collector, _ = make(h)

    result = await run(collector, h)

    assert (result.documents, result.error) == (0, None)


async def test_a_failed_ingest_reports_the_error_the_ingestor_already_recorded():
    error = JobError(Reason.STORAGE_ERROR, "upload failed", SRC)
    h = Harness(ingest_result=IngestResult("failed", error=error))
    collector, _ = make(h)

    result = await run(collector, h)

    assert (result.documents, result.error, result.recorded) == (0, error, True)


async def test_a_robots_refusal_is_blocked_and_nothing_is_fetched():
    h = Harness(robots=RobotsVerdict(False, "disallowed by robots.txt"))
    collector, _ = make(h)

    result = await run(collector, h)

    assert (result.error.reason, result.error.source_id) == (Reason.BLOCKED, SRC)
    assert "fetch" not in h.calls and "ingest" not in h.calls
    assert h.calls[0] == "started"


async def test_a_refused_source_url_stops_before_started_and_any_request():
    h = Harness()
    collector, _ = make(h, source_url="ftp://alfa.example.com/page")

    result = await run(collector, h)

    assert result.error.reason is Reason.BLOCKED_TARGET
    assert h.calls == []


@pytest.mark.parametrize("change", [{"active": False}, {"platform": "x"}])
async def test_a_source_that_is_not_collectable_is_an_invalid_request(change):
    h = Harness()
    collector, _ = make(h)
    collector._store.sources[SRC] = replace(collector._store.sources[SRC], **change)

    result = await run(collector, h)

    assert result.error.reason is Reason.INVALID_REQUEST
    assert h.calls == []


async def test_a_missing_source_is_an_invalid_request():
    h = Harness()
    collector, _ = make(h, source=False)

    result = await run(collector, h)

    assert result.error.reason is Reason.INVALID_REQUEST
    assert h.calls == []


async def test_a_server_error_carries_its_status_and_retry_after_seconds():
    h = Harness(fetch_raises=FetchFailure(Reason.HTTP_ERROR, "HTTP 503", "proxy-1", "120", http_status=503))
    collector, _ = make(h)

    result = await run(collector, h)

    assert (result.error.reason, result.http_status, result.retry_after) == (Reason.HTTP_ERROR, 503, 120.0)
    assert "ingest" not in h.calls


async def test_a_timeout_is_reported_without_a_status():
    h = Harness(fetch_raises=FetchFailure(Reason.TIMEOUT, "request timed out"))
    collector, _ = make(h)

    result = await run(collector, h)

    assert (result.error.reason, result.http_status, result.retry_after) == (Reason.TIMEOUT, None, None)


async def test_every_proxy_cooling_is_a_deferral_not_an_error():
    until = NOW + timedelta(seconds=30)
    h = Harness(fetch_raises=FetchDeferred(Deferral(until)))
    collector, _ = make(h)

    result = await run(collector, h)

    assert (result.deferral, result.error) == (Deferral(until), None)


async def test_a_parse_failure_keeps_its_reason():
    h = Harness(parse_raises=ParseFailure(Reason.EMPTY_TEXT, "no text"))
    collector, _ = make(h)

    result = await run(collector, h)

    assert (result.error.reason, result.error.detail) == (Reason.EMPTY_TEXT, "no text")
    assert "ingest" not in h.calls


@pytest.mark.parametrize("failure", [FetchFailure(Reason.BLOCKED, "HTTP 403"), ParseFailure(Reason.PARSE_ERROR, "x")])
async def test_the_session_is_closed_after_a_failure(failure):
    h = Harness(fetch_raises=failure if isinstance(failure, FetchFailure) else None,
                parse_raises=failure if isinstance(failure, ParseFailure) else None)
    collector, _ = make(h)

    await run(collector, h)

    assert h.closed == 1


async def test_the_session_is_closed_after_success():
    h = Harness()
    collector, _ = make(h)

    await run(collector, h)

    assert h.closed == 1


@pytest.mark.parametrize(
    "header, expected",
    [
        ("120", 120.0),
        ("0", 0.0),
        ("Sat, 21 Nov 2026 12:01:30 GMT", 90.0),
        ("Sat, 21 Nov 2026 11:00:00 GMT", 0.0),
        ("soon", None),
        ("-5", None),
        ("²", None),  # str.isdigit() is true, int() refuses it
        ("9" * 15, 999999999999999.0),
        ("9" * 16, None),
        (None, None),
    ],
)
def test_retry_after_is_read_as_seconds_or_an_http_date(header, expected):
    assert retry_after_seconds(header, NOW) == expected


async def test_every_proxy_cooling_defers_before_started_and_before_any_request():
    until = NOW + timedelta(seconds=30)
    h = Harness()
    collector, _ = make(h, rotator=Rotator(Deferral(until)))

    result = await run(collector, h)

    assert (result.deferral, result.error) == (Deferral(until), None)
    assert h.calls == []  # no `scan.started`, no request, no robots


class RenderSpy:
    def __init__(self):
        self.calls = []

    async def render(self, source, url, identity, proxy):
        self.calls.append((source.id, url))
        return "output"


def render_make(harness, spy, **source_fields):
    collector, limiter = make(harness)
    collector._store.sources[SRC] = replace(make_source(SRC, url=URL), **source_fields)
    collector._renderer = spy
    return collector


async def started():
    return None


@pytest.mark.parametrize(
    ("fields", "renders"),
    [
        ({"source_kind": "firm_own", "target_modules": ("M2",)}, True),
        ({"source_kind": "firm_own", "target_modules": ("M1", "M2")}, True),
        ({"source_kind": "third_party", "target_modules": ("M2",)}, False),
        ({"source_kind": "unknown", "target_modules": ("M2",)}, False),
        ({"source_kind": "firm_own", "target_modules": ("M1",)}, False),
    ],
)
async def test_only_a_firms_own_m2_page_gets_a_render_step(fields, renders):
    harness, spy = Harness(), RenderSpy()
    collector = render_make(harness, spy, **fields)

    await collector.run_source(SRC, started)

    (page, _, _), = harness.ingested
    assert ("render" in page) is renders
    if renders:
        assert await page["render"]() == "output" and spy.calls == [(SRC, URL)]
    else:
        assert spy.calls == []


async def test_without_a_renderer_no_document_carries_a_render_step():
    harness = Harness()
    collector, _ = make(harness)
    collector._store.sources[SRC] = replace(make_source(SRC, url=URL), target_modules=("M2",))

    await collector.run_source(SRC, started)

    (page, _, _), = harness.ingested
    assert "render" not in page


async def test_a_robots_refusal_ends_the_run_before_any_render_step():
    harness, spy = Harness(robots=RobotsVerdict(False, "disallowed")), RenderSpy()
    collector = render_make(harness, spy, target_modules=("M2",))

    await collector.run_source(SRC, started)

    assert harness.ingested == [] and spy.calls == [] and "fetch" not in harness.calls
