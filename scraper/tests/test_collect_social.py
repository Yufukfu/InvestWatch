"""The social branch of `Collector.run_source` over stubbed stages and the real Telegram parser: URL form, robots,
paging bounds, early stop, failures and the shared fetch path. Pages are the saved real ones."""

import ast
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import pytest

from conftest import FakeSourceStore, make_source
from iw_scraper.collect import Collector, Stages
from iw_scraper.fetch import FetchFailure, FetchResult
from iw_scraper.ingest.store import IngestResult
from iw_scraper.robots import RobotsVerdict
from iw_scraper.targets import AddressGuard, UrlGuard
from iw_scraper.types import JobError, Reason
from test_telegram_parser import IMAGE_POST, channel_page, load, text_post

SRC = "6b0f7f8e-0000-4000-8000-000000000002"
KDP = "https://t.me/s/kdpwiadomosci"
KDP_OLDER = "https://t.me/s/kdpwiadomosci?before=5179"
SUBE = "https://t.me/s/SubeTradingPL"
NOW = datetime(2026, 11, 21, 12, 0, tzinfo=UTC)
HTML = "text/html; charset=utf-8"


def page(url: str, body: bytes, final_url: str | None = None) -> FetchResult:
    return FetchResult(final_url or url, 200, HTML, body, {}, "proxy-1")


@dataclass
class Harness:
    pages: dict  # requested url -> FetchResult or an exception to raise
    robots: RobotsVerdict = RobotsVerdict(True, "ok")
    existing: set = field(default_factory=set)  # permalinks ingest reports as duplicates
    failing: str | None = None  # a permalink whose ingest fails
    calls: list = field(default_factory=list)
    fetched: list = field(default_factory=list)  # (url, identity, proxy)
    fetch_kwargs: list = field(default_factory=list)  # the keyword arguments of each fetch
    ingested: list = field(default_factory=list)
    authors: list = field(default_factory=list)
    identity: object = field(default_factory=object)

    def stages(self) -> Stages:
        async def check_robots(url, identity, proxy, **kw):
            self.calls.append("robots")
            return self.robots

        async def fetch(url, identity, proxy, **kw):
            self.calls.append("fetch")
            self.fetched.append((url, identity, proxy))
            self.fetch_kwargs.append(kw)
            outcome = self.pages[url]
            if isinstance(outcome, Exception):
                raise outcome
            return outcome

        async def close(session):
            self.calls.append("close")

        return Stages(
            open_session=lambda identity: object(), close_session=close, check_robots=check_robots,
            fetch=fetch, draw_identity=lambda: self.identity,
        )

    async def ingest(self, page_dict, source, *, fetched_at, duration_ms, proxy, author=None):
        self.calls.append("ingest")
        self.ingested.append((page_dict, source, proxy))
        self.authors.append(author)
        url = page_dict["url"]
        if url == self.failing:
            return IngestResult("failed", error=JobError(Reason.STORAGE_ERROR, "upload failed", SRC))
        return IngestResult("duplicate" if url in self.existing else "inserted", document_id="d")

    @property
    def urls(self) -> list[str]:
        return [url for url, _, _ in self.fetched]


class Limiter:
    def __init__(self, calls):
        self.calls = calls

    async def wait_turn(self, domain):
        self.calls.append("wait")
        return 0.0


class Run:
    def deferral(self):
        return None


class Rotator:
    def __init__(self):
        self.run = Run()

    def start_run(self):
        return self.run


async def resolver(host):
    return ["149.154.167.99"]


def make(h: Harness, *, url=KDP, max_posts=40) -> Collector:
    store = FakeSourceStore()
    store.permissive = False
    store.sources[SRC] = make_source(SRC, platform="other", url=url)
    guard = UrlGuard(("t.me",))

    async def urls():
        return guard

    return Collector(
        store, type("I", (), {"ingest": h.ingest})(), urls=urls, addresses=AddressGuard(resolver), rotator=Rotator(),
        limiter=Limiter(h.calls), stages=h.stages(), clock=lambda: NOW, social_max_posts=max_posts,
    )


async def run(collector, h):
    async def started():
        h.calls.append("started")

    return await collector.run_source(SRC, started)


KDP_PAGES = {KDP: page(KDP, load("telegram_kdpwiadomosci.html"))}
NOT_A_CHANNEL = b"<html><body><p>Preview not available</p></body></html>"


async def test_valid_channel_url_requests_the_page_and_ingests_each_text_post():
    h = Harness(KDP_PAGES)

    result = await run(make(h, max_posts=20), h)

    assert (result.documents, result.error) == (18, None)  # 20 posts on the page, two without text
    assert h.urls == [KDP]
    assert h.ingested[0][0]["url"] == "https://t.me/kdpwiadomosci/5179"
    assert h.ingested[0][0]["scrape_meta"]["network"] == "telegram"
    assert h.ingested[0][1].id == SRC and h.ingested[0][2] == "proxy-1"


async def test_the_author_goes_to_ingest_as_the_trusted_argument_not_in_the_page():
    h = Harness(KDP_PAGES)

    await run(make(h, max_posts=20), h)

    assert all("author" not in page_dict for page_dict, _, _ in h.ingested)
    assert h.authors[0] == {
        "name": "KDP - Marek Stiller 🎯", "handle": "@kdpwiadomosci", "profile_url": "https://t.me/kdpwiadomosci",
        "followers": 45700,
    }
    assert all(a == h.authors[0] for a in h.authors)


@pytest.mark.parametrize("url", ["https://t.me/SubeTradingPL", "https://t.me/s/ab", "https://t.me/s/a-b-c-d-e"])
async def test_wrong_url_form_makes_no_request(url):
    h = Harness(KDP_PAGES)

    result = await run(make(h, url=url), h)

    assert result.error.reason is Reason.INVALID_REQUEST
    assert h.calls == []


async def test_robots_refusal_fetches_nothing():
    h = Harness(KDP_PAGES, robots=RobotsVerdict(False, "disallowed by robots.txt"))

    result = await run(make(h), h)

    assert (result.error.reason, result.documents) == (Reason.BLOCKED, 0)
    assert h.fetched == [] and h.ingested == []


async def test_default_cap_reads_two_pages_of_twenty():
    pages = {**KDP_PAGES, KDP_OLDER: page(KDP_OLDER, load("telegram_rarecryptosignals_before.html").replace(b"rarecryptosignals", b"kdpwiadomosci"))}
    h = Harness(pages)

    result = await run(make(h), h)

    assert h.urls == [KDP, KDP_OLDER]
    assert (result.documents, result.error) == (38, None)  # 18 + 20 posts with text, within the cap of 40


async def test_nothing_new_on_the_newest_page_requests_no_older_page():
    existing = {f"https://t.me/kdpwiadomosci/{i}" for i in range(5179, 5199)}
    h = Harness(KDP_PAGES, existing=existing)

    result = await run(make(h), h)

    assert h.urls == [KDP]
    assert (result.documents, result.error) == (0, None)


async def test_short_channel_requests_exactly_one_page():
    body = channel_page(posts=text_post(5, "Cześć"))
    h = Harness({SUBE: page(SUBE, body)})

    result = await run(make(h, url=SUBE), h)

    assert h.urls == [SUBE]
    assert result.documents == 1


async def test_preview_disabled_is_a_parse_error_and_is_not_retried():
    h = Harness({SUBE: page(SUBE, NOT_A_CHANNEL, final_url="https://t.me/SubeTradingPL")})

    result = await run(make(h, url=SUBE), h)

    assert h.urls == [SUBE]
    assert (result.error.reason, result.documents) == (Reason.PARSE_ERROR, 0)
    assert "no public preview" in result.error.detail


async def test_blocked_on_the_first_page_emits_nothing():
    h = Harness({KDP: FetchFailure(Reason.BLOCKED, "HTTP 429", http_status=429)})

    result = await run(make(h), h)

    assert (result.error.reason, result.documents, result.http_status) == (Reason.BLOCKED, 0, 429)


async def test_blocked_on_the_second_page_keeps_the_first_pages_documents():
    pages = {**KDP_PAGES, KDP_OLDER: FetchFailure(Reason.BLOCKED, "HTTP 403", http_status=403)}
    h = Harness(pages)

    result = await run(make(h), h)

    assert h.urls == [KDP, KDP_OLDER]
    assert (result.documents, result.error.reason) == (18, Reason.BLOCKED)


async def test_page_that_is_not_a_channel_is_a_parse_error():
    h = Harness({SUBE: page(SUBE, NOT_A_CHANNEL)})

    result = await run(make(h, url=SUBE), h)

    assert (result.error.reason, result.documents) == (Reason.PARSE_ERROR, 0)


async def test_empty_channel_ends_without_a_document_or_an_error():
    h = Harness({SUBE: page(SUBE, channel_page())})

    result = await run(make(h, url=SUBE), h)

    assert (result.documents, result.error) == (0, None)


async def test_page_of_image_only_posts_ends_without_a_document_or_an_error():
    h = Harness({SUBE: page(SUBE, channel_page(posts=IMAGE_POST))})

    result = await run(make(h, url=SUBE), h)

    assert (result.documents, result.error) == (0, None)


async def test_the_count_of_skipped_posts_is_logged(caplog):
    h = Harness(KDP_PAGES)

    with caplog.at_level(logging.INFO, logger="iw_scraper.collect"):
        await run(make(h, max_posts=20), h)

    assert any("2 skipped" in record.getMessage() for record in caplog.records)


async def test_a_failed_ingest_ends_the_run_and_keeps_what_was_stored():
    h = Harness(KDP_PAGES, failing="https://t.me/kdpwiadomosci/5181")

    result = await run(make(h), h)

    assert (result.documents, result.error.reason, result.recorded) == (2, Reason.STORAGE_ERROR, True)
    assert h.urls == [KDP]


# the shared fetch path ("Social collection uses the same fetch path as web pages")


async def test_both_pages_of_a_run_carry_the_one_identity_and_the_run_proxy():
    pages = {**KDP_PAGES, KDP_OLDER: page(KDP_OLDER, load("telegram_rarecryptosignals_before.html").replace(b"rarecryptosignals", b"kdpwiadomosci"))}
    h = Harness(pages)
    collector = make(h)

    await run(collector, h)

    assert len(h.fetched) == 2
    assert all(identity is h.identity for _, identity, _ in h.fetched)
    assert h.fetched[0][2] is h.fetched[1][2]  # the run's proxy handle: the rotation picks per request inside it


async def test_every_page_request_waits_its_turn_at_the_domain_limiter():
    pages = {**KDP_PAGES, KDP_OLDER: page(KDP_OLDER, load("telegram_rarecryptosignals_before.html").replace(b"rarecryptosignals", b"kdpwiadomosci"))}
    h = Harness(pages)

    await run(make(h), h)

    fetch_positions = [i for i, call in enumerate(h.calls) if call == "fetch"]
    assert len(fetch_positions) == 2
    assert all(h.calls[i - 1] == "wait" for i in fetch_positions)


def test_social_modules_import_no_http_client():
    forbidden = {"httpx", "requests", "aiohttp", "noble_tls", "urllib3", "http"}
    social = Path(__file__).parent.parent / "src" / "iw_scraper" / "social"
    imported = set()
    for path in social.glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                imported |= {alias.name.split(".")[0] for alias in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                imported.add(node.module.split(".")[0])
    assert imported & forbidden == set()


# links are pointers, never fetched


async def test_links_to_x_youtube_and_other_channels_are_kept_and_never_requested():
    text = (
        'Zobacz <a href="https://x.com/example/status/123">X</a>, '
        '<a href="https://youtu.be/ms4VIbaHo7Y">film</a> i <a href="https://t.me/otherchannel">kanał</a>'
    )
    h = Harness({SUBE: page(SUBE, channel_page(posts=text_post(5, text)))})

    result = await run(make(h, url=SUBE), h)

    assert result.documents == 1
    hrefs = [link["href"] for link in h.ingested[0][0]["links"]]
    assert hrefs == ["https://x.com/example/status/123", "https://youtu.be/ms4VIbaHo7Y", "https://t.me/otherchannel"]
    assert h.urls == [SUBE]  # only the channel page: no link was followed


async def test_an_older_link_to_another_host_is_never_requested():
    body = channel_page(posts=text_post(5, "Cześć"), older="https://evil.example/s/SubeTradingPL?before=5")
    h = Harness({SUBE: page(SUBE, body)})

    result = await run(make(h, url=SUBE), h)

    assert h.urls == [SUBE]
    assert (result.documents, result.error) == (1, None)


async def test_a_redirect_to_another_channel_is_not_a_public_preview():
    h = Harness({SUBE: page(SUBE, load("telegram_kdpwiadomosci.html"), final_url=KDP)})

    result = await run(make(h, url=SUBE), h)

    assert (result.error.reason, result.documents) == (Reason.PARSE_ERROR, 0)
    assert h.ingested == []


async def test_a_redirect_to_the_same_path_on_another_host_is_not_this_channel():
    h = Harness({SUBE: page(SUBE, load("telegram_kdpwiadomosci.html"), final_url="https://example.com/s/SubeTradingPL")})

    result = await run(make(h, url=SUBE), h)

    assert (result.error.reason, result.documents) == (Reason.PARSE_ERROR, 0)
    assert h.ingested == []
