"""The YouTube collector: the channel URL form, the list and watch parsers over the saved real pages, one document
per playable video, the author, the bounds, skips and every failure. Pages are the saved real ones."""

import json
import logging
from datetime import UTC, datetime
from pathlib import Path

import pytest

from conftest import make_source
from iw_scraper.fetch import FetchFailure, FetchResult
from iw_scraper.ingest.store import IngestResult
from iw_scraper.jobs import AttemptResult
from iw_scraper.parsing import ParseFailure
from iw_scraper.social import youtube
from iw_scraper.social.model import FlowContext
from iw_scraper.types import JobError, Reason

SRC = "6b0f7f8e-0000-4000-8000-000000000004"
URL = "https://www.youtube.com/@UKNFpolska"
LIST_URL = URL + "/videos"
CHANNEL_ID = "UCOl3TxOXP1mwP2nydX_9K2Q"
NOW = datetime(2026, 11, 22, 12, 0, tzinfo=UTC)
FIXTURES = Path(__file__).parent / "fixtures"
CHANNEL_PAGE = (FIXTURES / "youtube_channel_uknf.html").read_bytes()
WATCH_PAGE = (FIXTURES / "youtube_watch_uknf.html").read_bytes()
FIRST_ID = "JLShF0trXZI"
UNSET = object()


def watch_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"


def player(**changes) -> dict:
    """The saved watch page's player data with `changes` applied (a dotted key sets a nested one; UNSET removes it)."""
    text = WATCH_PAGE.decode()
    data = json.JSONDecoder().raw_decode(text[text.index("{"):])[0]
    for dotted, value in changes.items():
        *path, last = dotted.split(".")
        node = data
        for key in path:
            node = node[key]
        if value is UNSET:
            node.pop(last, None)
        else:
            node[last] = value
    return data


def watch_body(video_id=FIRST_ID, **changes) -> bytes:
    data = player(**{"videoDetails.videoId": video_id, **changes})
    return f"<html><script>var ytInitialPlayerResponse = {json.dumps(data)};</script></html>".encode()


def page(url: str, body: bytes, status: int = 200) -> FetchResult:
    return FetchResult(url, status, "text/html; charset=utf-8", body, {}, "proxy-1")


class Harness:
    """A `FlowContext` over scripted pages: `pages` maps a requested URL to a body, or to an exception to raise."""

    def __init__(self, pages=None, *, known=(), robots_refusal=None):
        self.pages = {LIST_URL: CHANNEL_PAGE} if pages is None else pages
        self.known, self.robots_refusal = set(known), robots_refusal
        self.fetched, self.cookies, self.ingested, self.authors, self.events = [], [], [], [], []
        self.known_asked = []

    async def fetch(self, url, cookie=None):
        self.fetched.append(url)
        self.cookies.append(cookie)
        self.events.append("list" if url == LIST_URL else "watch")
        outcome = self.pages[url]
        if isinstance(outcome, Exception):
            raise outcome
        return page(url, outcome)

    async def check_robots(self):
        self.events.append("robots")
        return self.robots_refusal

    async def known_urls(self, urls):
        self.known_asked.append(list(urls))
        return {u for u in urls if u in self.known}

    async def ingest(self, page_dict, source, *, fetched_at, duration_ms, proxy, author=None):
        self.events.append("ingest")
        self.ingested.append(page_dict)
        self.authors.append(author)
        return IngestResult("inserted", document_id="d")

    async def wait_turn(self):
        return None

    def context(self, url=URL) -> FlowContext:
        return FlowContext(
            source=make_source(SRC, platform="youtube", url=url), domain="www.youtube.com", ingest=self.ingest,
            clock=lambda: NOW, wait_turn=self.wait_turn, identity=object(), session=object(), proxy=object(),
            check_robots=self.check_robots, fetch=self.fetch, known_urls=self.known_urls,
        )

    async def run(self, *, max_videos=10, url=URL):
        flow = youtube.make_flow(max_videos=lambda: max_videos)
        return await flow(self.context(url))


def channel_ids() -> list[str]:
    return list(youtube.parse_channel(CHANNEL_PAGE).video_ids)


def with_watch_pages(ids, body=None):
    pages = {LIST_URL: CHANNEL_PAGE}
    for video_id in ids:
        pages[watch_url(video_id)] = body or watch_body(video_id)
    return pages


# --- the channel URL -------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url", ["https://www.youtube.com/@UKNFpolska", "https://www.youtube.com/@abc", "https://www.youtube.com/@a.b-c_d9", "https://www.youtube.com/@" + "a" * 30]
)
def test_a_channel_url_is_accepted(url):
    assert youtube.valid_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "https://www.youtube.com/watch?v=JLShF0trXZI", "https://www.youtube.com/results?search_query=btc",
        "https://www.youtube.com/@ab", "https://www.youtube.com/@" + "a" * 31, "http://www.youtube.com/@UKNFpolska",
        "https://www.youtube.com/@UKNFpolska/videos", "https://www.youtube.com/@UKNFpolska/", "https://www.youtube.com/@",
        "https://www.youtube.com/channel/" + CHANNEL_ID, "https://youtu.be/JLShF0trXZI", "https://www.youtube.com/@bad handle",
    ],
)
async def test_any_other_url_is_refused_before_any_request(url):
    h = Harness()
    assert not youtube.valid_url(url)

    with pytest.raises(ParseFailure) as refused:
        await h.run(url=url)

    assert refused.value.reason is Reason.INVALID_REQUEST and h.fetched == [] and h.events == []


# --- the parsers over the saved pages ------------------------------------------------------------------------------


def test_the_channel_page_gives_the_channel_id_and_the_video_ids_newest_first():
    parsed = youtube.parse_channel(CHANNEL_PAGE)

    assert parsed.channel_id == CHANNEL_ID
    assert len(parsed.video_ids) == 30 and len(set(parsed.video_ids)) == 30
    assert parsed.video_ids[:3] == (FIRST_ID, "XwFVTcvPouk", "mkzkGyd5E9A")


@pytest.mark.parametrize(
    "body",
    [
        b"<html><body>Zanim przejdziesz do YouTube</body></html>",  # the consent interstitial
        b"",
        b"<html><script>var ytInitialData = {};</script></html>",
        b"<html><script>var ytInitialData = {not json</script></html>",
    ],
)
def test_a_page_with_no_video_list_is_one_parse_error(body):
    with pytest.raises(ParseFailure) as failure:
        youtube.parse_channel(body)

    assert (failure.value.reason, failure.value.detail) == (Reason.PARSE_ERROR, "no readable video list")


def test_the_watch_page_gives_the_video_the_collector_needs():
    video = youtube.parse_watch(WATCH_PAGE)

    assert video.video_id == FIRST_ID and video.channel_id == CHANNEL_ID
    assert video.title.startswith("Film jubileuszowy z okazji 20-lecia Komisji Nadzoru")
    assert video.description.startswith("Zachęcamy do obejrzenia filmu jubileuszowego")
    assert video.published_at == "2026-09-24T09:20:08+00:00"
    assert video.channel_name == "Urząd Komisji Nadzoru Finansowego"
    assert [(t.language, t.kind) for t in video.tracks] == [("pl", "asr")]


@pytest.mark.parametrize(
    "body, expected",
    [
        (watch_body(**{"playabilityStatus.status": "UNPLAYABLE"}), "unplayable"),
        (watch_body(**{"playabilityStatus.status": "LOGIN_REQUIRED"}), "unplayable"),
        (watch_body(**{"playabilityStatus.status": "ERROR"}), "unplayable"),
        (b"<html><body>nothing here</body></html>", "unreadable"),
        (b"<html><script>var ytInitialPlayerResponse = {broken</script></html>", "unreadable"),
        (watch_body(**{"videoDetails.title": ""}), "unreadable"),
        (watch_body(**{"videoDetails": UNSET}), "unreadable"),
    ],
)
def test_a_watch_page_that_gives_no_video_is_unplayable_or_unreadable(body, expected):
    assert youtube.parse_watch(body) == expected


def test_a_publish_date_without_a_zone_is_taken_as_utc_midnight():
    video = youtube.parse_watch(watch_body(**{"microformat.playerMicroformatRenderer.publishDate": "2026-09-24"}))

    assert video.published_at == "2026-09-24T00:00:00+00:00"


def test_a_video_with_no_publish_date_still_parses_with_none():
    renderer = "microformat.playerMicroformatRenderer."
    video = youtube.parse_watch(watch_body(**{renderer + "publishDate": UNSET, renderer + "uploadDate": UNSET}))

    assert video.published_at is None


def test_a_video_with_no_caption_track_parses_with_no_tracks():
    video = youtube.parse_watch(watch_body(captions=UNSET))

    assert video.tracks == ()


# --- the flow: documents ---------------------------------------------------------------------------------------------


async def test_a_run_requests_the_list_then_one_watch_page_per_video_and_ingests_each():
    ids = channel_ids()[:2]
    h = Harness(with_watch_pages(ids))

    result = await h.run(max_videos=2)

    assert (result.documents, result.error) == (2, None)
    assert h.fetched == [LIST_URL, watch_url(ids[0]), watch_url(ids[1])]
    assert h.events == ["robots", "list", "watch", "ingest", "watch", "ingest"]  # one at a time, in order


async def test_a_video_becomes_a_document_with_title_description_and_no_transcript_yet():
    h = Harness(with_watch_pages([FIRST_ID], WATCH_PAGE))

    await h.run(max_videos=1)

    doc = h.ingested[0]
    video = youtube.parse_watch(WATCH_PAGE)
    assert doc["url"] == doc["canonical_url"] == watch_url(FIRST_ID)
    assert doc["title"] == video.title and doc["lang"] is None and doc["http_status"] == 200
    assert doc["text"] == f"{video.title}\n\n{video.description}"
    assert doc["published_at"] == "2026-09-24T09:20:08+00:00"
    assert doc["scrape_meta"]["video_id"] == FIRST_ID and doc["scrape_meta"]["transcript"] == "none"
    assert doc["links"] == []


async def test_a_video_with_an_empty_description_is_the_title_alone():
    h = Harness(with_watch_pages([FIRST_ID], watch_body(**{"videoDetails.shortDescription": ""})))

    await h.run(max_videos=1)

    assert h.ingested[0]["text"] == youtube.parse_watch(WATCH_PAGE).title


def keys_of(node):
    if isinstance(node, dict):
        for key, value in node.items():
            yield key
            yield from keys_of(value)
    elif isinstance(node, list):
        for item in node:
            yield from keys_of(item)


async def test_the_stored_html_is_the_players_details_without_tokens_or_signed_urls():
    h = Harness(with_watch_pages([FIRST_ID], WATCH_PAGE))

    await h.run(max_videos=1)

    stored = json.loads(h.ingested[0]["html"])
    assert {"videoDetails", "microformat", "captionTracks"} <= set(stored)
    assert "visitorData" not in set(keys_of(stored)) and "baseUrl" not in set(keys_of(stored))
    assert "timedtext" not in h.ingested[0]["html"]
    assert stored["captionTracks"] == [{"languageCode": "pl", "kind": "asr"}]


async def test_every_page_request_carries_the_consent_cookie():
    h = Harness(with_watch_pages(channel_ids()[:2]))

    await h.run(max_videos=2)

    assert h.cookies == ["SOCS=CAI", "SOCS=CAI", "SOCS=CAI"]


# --- the author ------------------------------------------------------------------------------------------------------


async def test_the_author_comes_from_the_url_and_the_channel_name_is_the_players():
    h = Harness(with_watch_pages([FIRST_ID], WATCH_PAGE))

    await h.run(max_videos=1)

    assert h.authors == [{
        "name": "Urząd Komisji Nadzoru Finansowego", "handle": "@UKNFpolska",
        "profile_url": "https://www.youtube.com/@UKNFpolska", "followers": None,
    }]
    assert "author" not in h.ingested[0]


async def test_a_video_of_another_channel_is_skipped_and_counted(caplog):
    ids = channel_ids()[:2]
    pages = with_watch_pages(ids[:1], WATCH_PAGE)
    pages[watch_url(ids[1])] = watch_body(ids[1], **{"videoDetails.channelId": "UCotherchannelotherchan1"})
    h = Harness(pages)
    caplog.set_level(logging.INFO, logger="iw_scraper.social.youtube")

    result = await h.run(max_videos=2)

    assert result.documents == 1 and [d["scrape_meta"]["video_id"] for d in h.ingested] == [ids[0]]
    assert "1 of another channel" in caplog.text


# --- the flow: bounds and skips --------------------------------------------------------------------------------------


@pytest.mark.parametrize("cap", [1, 3, 10])
async def test_at_most_the_capped_newest_videos_are_requested(cap):
    ids = channel_ids()
    h = Harness(with_watch_pages(ids))

    await h.run(max_videos=cap)

    assert h.fetched == [LIST_URL, *[watch_url(i) for i in ids[:cap]]]


async def test_videos_that_already_have_a_document_are_not_requested():
    ids = channel_ids()[:3]
    h = Harness(with_watch_pages(ids), known={watch_url(ids[0]), watch_url(ids[2])})

    result = await h.run(max_videos=3)

    assert h.fetched == [LIST_URL, watch_url(ids[1])] and result.documents == 1
    assert h.known_asked == [[watch_url(i) for i in ids]]


async def test_when_every_listed_video_is_stored_no_watch_page_is_requested():
    ids = channel_ids()[:3]
    h = Harness(with_watch_pages(ids), known={watch_url(i) for i in ids})

    result = await h.run(max_videos=3)

    assert (result.documents, result.error) == (0, None) and h.fetched == [LIST_URL]


async def test_an_unplayable_video_is_skipped_and_counted_and_is_not_an_error(caplog):
    ids = channel_ids()[:2]
    pages = with_watch_pages(ids[1:])
    pages[watch_url(ids[0])] = watch_body(ids[0], **{"playabilityStatus.status": "LOGIN_REQUIRED"})
    h = Harness(pages)
    caplog.set_level(logging.INFO, logger="iw_scraper.social.youtube")

    result = await h.run(max_videos=2)

    assert (result.documents, result.error) == (1, None)
    assert "1 unplayable" in caplog.text


async def test_one_unreadable_watch_page_is_skipped_and_the_run_goes_on(caplog):
    ids = channel_ids()[:3]
    pages = with_watch_pages(ids)
    pages[watch_url(ids[0])] = b"<html>no player data</html>"
    h = Harness(pages)
    caplog.set_level(logging.INFO, logger="iw_scraper.social.youtube")

    result = await h.run(max_videos=3)

    assert result.documents == 2 and h.fetched[-1] == watch_url(ids[2])
    assert "1 unreadable" in caplog.text


async def test_when_every_watch_page_is_unreadable_the_run_is_one_parse_error():
    ids = channel_ids()[:2]
    h = Harness(with_watch_pages(ids, b"<html>no player data</html>"))

    with pytest.raises(ParseFailure) as failure:
        await h.run(max_videos=2)

    assert failure.value.reason is Reason.PARSE_ERROR and h.ingested == []


async def test_a_mix_of_unreadable_and_unplayable_pages_is_not_a_parse_error():
    ids = channel_ids()[:2]
    pages = with_watch_pages(ids[1:], b"<html>no player data</html>")
    pages[watch_url(ids[0])] = watch_body(ids[0], **{"playabilityStatus.status": "UNPLAYABLE"})

    result = await Harness(pages).run(max_videos=2)

    assert (result.documents, result.error) == (0, None)


# --- the flow: failures ----------------------------------------------------------------------------------------------


async def test_a_robots_refusal_is_returned_and_nothing_is_requested():
    refusal = AttemptResult(error=JobError(Reason.BLOCKED, "robots.txt disallows this path", SRC))
    h = Harness(robots_refusal=refusal)

    result = await h.run()

    assert result is refusal and h.fetched == []


async def test_a_consent_redirect_on_the_list_ends_the_run_as_blocked_target_with_no_watch_page():
    h = Harness({LIST_URL: FetchFailure(Reason.BLOCKED_TARGET, "host not allowed: consent.youtube.com")})

    with pytest.raises(FetchFailure) as failure:
        await h.run()

    assert failure.value.reason is Reason.BLOCKED_TARGET and h.fetched == [LIST_URL] and h.ingested == []


async def test_a_list_page_with_no_video_ids_is_one_parse_error_and_no_watch_page():
    h = Harness({LIST_URL: b"<html><body>consent</body></html>"})

    with pytest.raises(ParseFailure) as failure:
        await h.run()

    assert failure.value.detail == "no readable video list" and h.fetched == [LIST_URL]


async def test_a_block_on_the_first_watch_page_ends_the_run_with_the_fetch_error():
    ids = channel_ids()[:3]
    pages = with_watch_pages(ids)
    pages[watch_url(ids[0])] = FetchFailure(Reason.BLOCKED, "HTTP 429", None, "60", 429)
    h = Harness(pages)

    with pytest.raises(FetchFailure) as failure:
        await h.run(max_videos=3)

    assert failure.value.reason is Reason.BLOCKED and h.fetched == [LIST_URL, watch_url(ids[0])]


async def test_a_block_on_a_later_watch_page_keeps_the_stored_documents_and_requests_no_more():
    ids = channel_ids()[:4]
    pages = with_watch_pages(ids)
    pages[watch_url(ids[2])] = FetchFailure(Reason.BLOCKED, "HTTP 429", None, "60", 429)
    h = Harness(pages)

    result = await h.run(max_videos=4)

    assert result.documents == 2 and result.error.reason is Reason.BLOCKED and result.http_status == 429
    assert h.fetched == [LIST_URL, *[watch_url(i) for i in ids[:3]]]


@pytest.mark.parametrize(
    "failure",
    [
        FetchFailure(Reason.BLOCKED, "HTTP 429", None, "60", 429),
        FetchFailure(Reason.HTTP_ERROR, "HTTP 503", None, "60", 503),
    ],
)
async def test_a_retry_after_on_a_later_watch_page_reaches_the_queue_so_it_defers_the_domain(failure):
    ids = channel_ids()[:3]
    pages = with_watch_pages(ids)
    pages[watch_url(ids[1])] = failure
    h = Harness(pages)

    result = await h.run(max_videos=3)

    assert result.documents == 1 and result.retry_after == 60.0 and result.http_status == failure.http_status


async def test_a_later_watch_page_failure_without_retry_after_leaves_it_unset():
    ids = channel_ids()[:3]
    pages = with_watch_pages(ids)
    pages[watch_url(ids[1])] = FetchFailure(Reason.BLOCKED, "HTTP 403", None, None, 403)

    result = await Harness(pages).run(max_videos=3)

    assert result.documents == 1 and result.retry_after is None


async def test_an_ingest_failure_ends_the_run_with_the_recorded_error():
    ids = channel_ids()[:3]

    class Failing(Harness):
        async def ingest(self, page_dict, source, **kw):
            if page_dict["scrape_meta"]["video_id"] == ids[1]:
                return IngestResult("failed", error=JobError(Reason.STORAGE_ERROR, "upload failed", SRC))
            return await super().ingest(page_dict, source, **kw)

    h = Failing(with_watch_pages(ids))

    result = await h.run(max_videos=3)

    assert (result.documents, result.recorded) == (1, True) and result.error.reason is Reason.STORAGE_ERROR
    assert h.fetched[-1] == watch_url(ids[1])
