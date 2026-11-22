"""The 404/410 branch of the web flow: a removed page is confirmed once, recorded once, and is not a failure."""

from dataclasses import dataclass, field
from datetime import UTC, datetime

import pytest

from conftest import FakeSourceStore, make_source
from iw_scraper.collect import Collector, Stages
from iw_scraper.fetch import FetchDeferred, FetchFailure, FetchResult
from iw_scraper.ingest.store import IngestResult, RemovalState
from iw_scraper.parsing import ParsedPage
from iw_scraper.robots import RobotsVerdict
from iw_scraper.targets import AddressGuard, UrlGuard
from iw_scraper.types import Deferral, Reason

SRC = "6b0f7f8e-0000-4000-8000-000000000003"
URL = "https://alfa.example.com/ad/1?utm=x"
NOW = datetime(2026, 11, 22, 12, 0, tzinfo=UTC)
OLD = datetime(2026, 11, 20, 12, 0, tzinfo=UTC)
NEWER = datetime(2026, 11, 21, 12, 0, tzinfo=UTC)

STORED = RemovalState("d-1", "a" * 64, OLD, None)
STORED_AND_GONE = RemovalState("d-1", "a" * 64, OLD, NEWER)
NEVER_STORED = RemovalState(None, None, None, None)


def answer(status: int, retry_after: str | None = None, reason: Reason | None = None) -> FetchFailure:
    default = Reason.BLOCKED if status in (403, 429) else Reason.HTTP_ERROR
    return FetchFailure(reason or default, f"HTTP {status}", "proxy-1", retry_after, status)


def ok_page() -> FetchResult:
    return FetchResult(URL, 200, "text/html; charset=utf-8", b"<html>hello</html>", {}, "proxy-1")


@dataclass
class Harness:
    answers: list  # what each fetch gives, in order: a FetchFailure/FetchDeferred to raise or a FetchResult
    state: RemovalState | None = STORED
    fetches: int = 0
    waits: int = 0
    state_asked: int = 0
    ingested: list = field(default_factory=list)
    gone: list = field(default_factory=list)  # (source, status, already_recorded)

    def stages(self) -> Stages:
        async def check_robots(url, identity, proxy, **kw):
            return RobotsVerdict(True, "ok")

        async def fetch(url, identity, proxy, **kw):
            outcome = self.answers[self.fetches]
            self.fetches += 1
            if isinstance(outcome, Exception):
                raise outcome
            return outcome

        async def close(session):
            pass

        return Stages(
            open_session=lambda identity: object(), close_session=close, check_robots=check_robots, fetch=fetch,
            parse=lambda body, content_type, final_url: ParsedPage("Title", URL, "hello", ()), draw_identity=lambda: object(),
        )

    async def ingest(self, page, source, *, fetched_at, duration_ms, proxy):
        self.ingested.append(source.id)
        return IngestResult("inserted", document_id="d-2")

    async def rescan_state(self, source_id):
        self.state_asked += 1
        return self.state

    async def record_gone(self, source, status, *, already_recorded=False):
        self.gone.append((source, status, already_recorded))


class Limiter:
    def __init__(self, harness):
        self.harness = harness

    async def wait_turn(self, domain):
        self.harness.waits += 1
        return 0.0


class Run:
    def deferral(self):
        return None


class Rotator:
    def start_run(self):
        return Run()


async def resolver(host):
    return ["93.184.216.34"]


async def collect(harness):
    store = FakeSourceStore()
    store.permissive = False
    store.sources[SRC] = make_source(SRC, url=URL)
    guard = UrlGuard(("alfa.example.com",))

    async def urls():
        return guard

    ingestor = type("I", (), {"ingest": harness.ingest, "rescan_state": harness.rescan_state, "record_gone": harness.record_gone})()
    collector = Collector(
        store, ingestor, urls=urls, addresses=AddressGuard(resolver), rotator=Rotator(), limiter=Limiter(harness),
        stages=harness.stages(), clock=lambda: NOW,
    )

    async def started():
        pass

    return await collector.run_source(SRC, started)


@pytest.mark.parametrize("status", [404, 410])
async def test_two_matching_answers_after_a_stored_document_are_gone(status):
    h = Harness([answer(status), answer(status)])
    result = await collect(h)
    assert (result.documents, result.error, result.deferral) == (0, None, None)
    assert [(s.id, st, again) for s, st, again in h.gone] == [(SRC, status, False)]
    assert h.fetches == 2
    assert h.waits == 3  # robots, the page, and the confirmation each wait for their own turn
    assert h.ingested == []


async def test_the_recorded_url_is_the_source_url():
    # `fetch` hides redirect hops, so a redirect to a removed page looks like a 404 on the source URL itself
    h = Harness([answer(404), answer(404)])
    await collect(h)
    assert h.gone[0][0].url == URL


async def test_a_410_confirmed_by_a_404_is_gone():
    h = Harness([answer(410), answer(404)])
    result = await collect(h)
    assert result.error is None
    assert len(h.gone) == 1


async def test_a_gone_page_that_is_still_gone_costs_one_request_and_no_new_row():
    h = Harness([answer(404)], state=STORED_AND_GONE)
    result = await collect(h)
    assert (result.documents, result.error) == (0, None)
    assert h.fetches == 1
    assert [(s.id, again) for s, _, again in h.gone] == [(SRC, True)]


async def test_a_page_replaced_after_a_removal_is_confirmed_and_recorded_again():
    replaced = RemovalState("d-3", "b" * 64, NOW, NEWER)  # the newest document is newer than the old `gone`
    h = Harness([answer(404), answer(404)], state=replaced)
    await collect(h)
    assert h.fetches == 2
    assert [again for _, _, again in h.gone] == [False]


async def test_a_page_that_never_stored_a_document_is_an_http_error_without_confirmation():
    h = Harness([answer(404)], state=NEVER_STORED)
    result = await collect(h)
    assert (result.error.reason, result.http_status) == (Reason.HTTP_ERROR, 404)
    assert h.fetches == 1
    assert h.gone == []


@pytest.mark.parametrize("status", [403, 500, 503])
async def test_other_statuses_are_never_gone_and_never_look_the_state_up(status):
    h = Harness([answer(status)])
    result = await collect(h)
    assert result.error.reason in (Reason.HTTP_ERROR, Reason.BLOCKED)
    assert result.http_status == status
    assert (h.gone, h.state_asked, h.fetches) == ([], 0, 1)


async def test_a_failing_state_lookup_falls_back_to_http_error():
    h = Harness([answer(404)], state=None)
    result = await collect(h)
    assert (result.error.reason, result.http_status) == (Reason.HTTP_ERROR, 404)
    assert h.fetches == 1
    assert h.gone == []


async def test_one_flaky_404_is_not_a_removal_when_the_confirmation_answers_200():
    h = Harness([answer(404), ok_page()])
    result = await collect(h)
    assert (result.documents, result.error) == (1, None)
    assert h.ingested == [SRC]
    assert h.gone == []


@pytest.mark.parametrize(
    "second, reason, status, retry_after",
    [(503, Reason.HTTP_ERROR, 503, 20.0), (429, Reason.BLOCKED, 429, 30.0)],
)
async def test_a_confirmation_that_answers_something_else_keeps_its_own_outcome(second, reason, status, retry_after):
    h = Harness([answer(404), answer(second, retry_after=str(int(retry_after)))])
    result = await collect(h)
    assert (result.error.reason, result.http_status, result.retry_after) == (reason, status, retry_after)
    assert h.gone == []


async def test_a_deferral_during_the_confirmation_is_passed_on():
    until = datetime(2026, 11, 22, 13, 0, tzinfo=UTC)
    h = Harness([answer(404), FetchDeferred(Deferral(until))])
    result = await collect(h)
    assert result.deferral == Deferral(until)
    assert h.gone == []
