"""The X collector: the account URL form, the mapping of the library's posts to documents, the author, the bounds,
every restriction marker, and the adapter over `Scweet` (a fake client). The posts are the saved real ones."""

import asyncio
import json
import logging
import traceback
from datetime import UTC, datetime
from pathlib import Path

import pytest
from Scweet import AccountPoolExhausted, AuthError, NetworkError, RateLimitError, RunFailed

from conftest import make_source
from iw_scraper.fetch import FetchFailure
from iw_scraper.ingest.store import IngestResult
from iw_scraper.parsing import ParseFailure
from iw_scraper.social import x
from iw_scraper.social.model import FlowContext
from iw_scraper.types import JobError, Reason

SRC = "6b0f7f8e-0000-4000-8000-000000000003"
URL = "https://x.com/uknf"
NOW = datetime(2026, 11, 22, 12, 0, tzinfo=UTC)
COOKIES = ("0f3a9c51d2b84e67a1c05d9e8b7f4a62c3d1e0f9", "7c2e91ab4d6f08351e9a2b7c4d8f1036a5e9c2b1d7f4a08e")
FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "x_timeline_uknf.json").read_text(encoding="utf-8"))


def post(post_id="1972944761934790806", text="Treść wpisu", created="Tue Sep 30 08:41:01 +0000 2025", **kw):
    fields = dict(post_id=post_id, text=text, created_at=created, lang="pl", is_repost=False, media_count=0)
    return x.XPost(**{**fields, **kw})


class Harness:
    def __init__(self, posts=(), *, name="Urząd KNF", followers=26773, existing=(), timeline_error=None, followers_error=None):
        self.posts, self.name, self.follower_count = tuple(posts), name, followers
        self.existing, self.timeline_error, self.followers_error = set(existing), timeline_error, followers_error
        self.calls, self.ingested, self.authors, self.waits = [], [], [], 0

    async def timeline(self, handle, limit, cookies):
        self.calls.append(("timeline", handle, limit, cookies))
        if self.timeline_error:
            raise self.timeline_error
        return x.Timeline(name=self.name, posts=self.posts)

    async def followers(self, handle, cookies):
        self.calls.append(("followers", handle, cookies))
        if self.followers_error:
            raise self.followers_error
        return self.follower_count

    async def ingest(self, page, source, *, fetched_at, duration_ms, proxy, author=None):
        self.ingested.append(page)
        self.authors.append(author)
        return IngestResult("duplicate" if page["url"] in self.existing else "inserted", document_id="d")

    async def wait_turn(self):
        self.waits += 1

    def context(self, *, max_posts=40, url=URL) -> FlowContext:
        return FlowContext(
            source=make_source(SRC, platform="x", url=url), domain="x.com", ingest=self.ingest,
            clock=lambda: NOW, wait_turn=self.wait_turn, max_posts=max_posts,
        )

    async def run(self, *, cookies=COOKIES, **ctx):
        flow = x.make_flow(timeline=self.timeline, followers=self.followers, cookies=lambda: cookies)
        return await flow(self.context(**ctx))


# --- the account URL -------------------------------------------------------------------------------------------


@pytest.mark.parametrize("url", ["https://x.com/uknf", "https://x.com/Some_Handle1", "https://x.com/a", "https://x.com/" + "a" * 15])
def test_an_account_url_is_accepted(url):
    assert x.valid_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "https://x.com/uknf/status/123", "https://x.com/search?q=btc", "https://x.com/", "https://x.com/" + "a" * 16,
        "http://x.com/uknf", "https://x.com/uk-nf", "https://twitter.com/uknf", "https://x.com/uknf/",
        "https://x.com/uknf?lang=pl", "https://x.com/@uknf",
    ],
)
async def test_any_other_url_is_refused_before_any_request(url):
    h = Harness([post()])
    assert not x.valid_url(url)

    with pytest.raises(ParseFailure) as refused:
        await h.run(url=url)

    assert refused.value.reason is Reason.INVALID_REQUEST and h.calls == []


# --- from the library's posts to documents -----------------------------------------------------------------------


def test_the_saved_timeline_maps_to_posts_with_their_repost_flag():
    timeline = x.timeline_from_scweet(FIXTURE)

    assert len(timeline.posts) == 20 and sum(p.is_repost for p in timeline.posts) == 7
    first = timeline.posts[0]
    assert (first.post_id, first.created_at, first.lang, first.media_count) == (
        "1972944761934790806", "Tue Sep 30 08:41:01 +0000 2025", "pl", 1,
    )
    assert timeline.name == "Urząd KNF"


async def test_the_saved_timeline_gives_one_document_per_original_post():
    h = Harness(x.timeline_from_scweet(FIXTURE).posts)

    result = await h.run()

    assert (result.documents, result.error) == (13, None)  # 20 posts, 7 of them reposts
    first = h.ingested[0]
    assert (first["url"], first["canonical_url"], first["title"], first["published_at"], first["lang"]) == (
        "https://x.com/uknf/status/1972944761934790806", "https://x.com/uknf/status/1972944761934790806", None,
        "2025-09-30T08:41:01+00:00", "pl",
    )
    assert first["text"] == FIXTURE[0]["text"] and first["http_status"] is None
    assert first["scrape_meta"]["post_id"] == "1972944761934790806" and first["scrape_meta"]["scraper"] == "api"


async def test_a_text_post_becomes_a_document_with_its_permalink_and_utc_time():
    h = Harness([post("2123819354898731226", "Z upoważnienia Komisji…", "Fri Nov 20 16:42:47 +0000 2026")])

    await h.run()

    page = h.ingested[0]
    assert page["url"] == "https://x.com/uknf/status/2123819354898731226"
    assert page["text"] == "Z upoważnienia Komisji…" and page["published_at"] == "2026-11-20T16:42:47+00:00"


async def test_a_creation_time_with_an_offset_is_converted_to_utc():
    h = Harness([post(created="Fri Nov 20 18:42:47 +0200 2026")])

    await h.run()

    assert h.ingested[0]["published_at"] == "2026-11-20T16:42:47+00:00"


@pytest.mark.parametrize("code, expected", [("pl", "pl"), ("en", "en"), ("und", None), ("qme", None), ("PL", None), ("pol", None), ("", None), (None, None)])
async def test_the_language_is_two_lowercase_letters_or_null(code, expected):
    h = Harness([post(lang=code)])

    result = await h.run()

    assert result.documents == 1 and h.ingested[0]["lang"] == expected


async def test_a_repost_of_another_account_is_skipped_and_counted(caplog):
    h = Harness([post("1", "RT @other: tekst", is_repost=True), post("2", "własny wpis")])
    caplog.set_level(logging.INFO, logger="iw_scraper.social.x")

    result = await h.run()

    assert result.documents == 1 and [p["scrape_meta"]["post_id"] for p in h.ingested] == ["2"]
    assert "1 reposts" in caplog.text


@pytest.mark.parametrize("text", ["", "   \n", None])
async def test_a_post_without_text_is_skipped_and_is_not_an_error(text):
    h = Harness([post("1", text, media_count=1), post("2", "własny wpis")])

    result = await h.run()

    assert (result.documents, result.error) == (1, None)


async def test_the_stored_html_is_the_post_as_json_with_only_the_listed_keys():
    h = Harness([post("2", "wpis", media_count=2)])

    await h.run()

    stored = json.loads(h.ingested[0]["html"])
    assert stored == {
        "id": "2", "text": "wpis", "created_at": "Tue Sep 30 08:41:01 +0000 2025", "lang": "pl", "handle": "uknf",
        "media_count": 2,
    }


async def test_one_malformed_post_is_skipped_and_the_others_are_collected(caplog):
    h = Harness([post(post_id=None), post("2"), post("3", created=None), post("4")])
    caplog.set_level(logging.INFO, logger="iw_scraper.social.x")

    result = await h.run()

    assert result.documents == 2 and [p["scrape_meta"]["post_id"] for p in h.ingested] == ["2", "4"]
    assert "2 malformed" in caplog.text


async def test_a_creation_time_that_cannot_be_read_is_malformed():
    h = Harness([post("1", created="yesterday"), post("2")])

    result = await h.run()

    assert result.documents == 1 and h.ingested[0]["scrape_meta"]["post_id"] == "2"


async def test_when_every_post_is_malformed_the_run_is_one_parse_error():
    h = Harness([post(post_id=None), post("3", created=None)])

    with pytest.raises(ParseFailure) as failure:
        await h.run()

    assert failure.value.reason is Reason.PARSE_ERROR and h.ingested == []


async def test_a_timeline_with_no_posts_is_not_an_error_and_asks_nothing_more():
    h = Harness([])

    result = await h.run()

    assert (result.documents, result.error) == (0, None)
    assert [c[0] for c in h.calls] == ["timeline"]  # no follower lookup


async def test_the_same_post_twice_in_one_answer_is_ingested_once():
    h = Harness([post("7", "wpis"), post("7", "wpis")])

    await h.run()

    assert len(h.ingested) == 1


async def test_a_post_that_is_already_stored_is_not_counted():
    h = Harness([post("7", "wpis")], existing={"https://x.com/uknf/status/7"})

    result = await h.run()

    assert (result.documents, result.error) == (0, None)


async def test_an_ingest_failure_ends_the_run_with_the_recorded_error_and_keeps_the_count():
    class Failing(Harness):
        async def ingest(self, page, source, **kw):
            if page["scrape_meta"]["post_id"] == "3":
                return IngestResult("failed", error=JobError(Reason.STORAGE_ERROR, "upload failed", SRC))
            return await super().ingest(page, source, **kw)

    h = Failing([post("1"), post("2"), post("3"), post("4")])

    result = await h.run()

    assert (result.documents, result.recorded) == (2, True) and result.error.reason is Reason.STORAGE_ERROR
    assert [p["scrape_meta"]["post_id"] for p in h.ingested] == ["1", "2"]


# --- the author ----------------------------------------------------------------------------------------------------


async def test_the_author_comes_from_the_url_and_the_account_and_is_a_trusted_argument():
    h = Harness([post("1"), post("2")])

    await h.run()

    expected = {"name": "Urząd KNF", "handle": "@uknf", "profile_url": "https://x.com/uknf", "followers": 26773}
    assert h.authors == [expected, expected]
    assert all("author" not in page for page in h.ingested)


async def test_the_handle_is_the_urls_even_when_the_post_names_another():
    h = Harness([post("1")])

    await h.run(url="https://x.com/Other_Account")

    assert h.authors[0]["handle"] == "@Other_Account" and h.authors[0]["profile_url"] == "https://x.com/Other_Account"
    assert json.loads(h.ingested[0]["html"])["handle"] == "Other_Account"


async def test_no_name_and_no_follower_count_are_null_and_the_documents_are_still_emitted():
    h = Harness([post("1")], name=None, followers=None)

    result = await h.run()

    assert result.documents == 1
    assert (h.authors[0]["name"], h.authors[0]["followers"]) == (None, None)


# --- bounds, cookies and restrictions ------------------------------------------------------------------------------


@pytest.mark.parametrize("max_posts, limit", [(15, 15), (40, 40), (500, 40), (1, 1)])
async def test_one_timeline_call_asks_for_at_most_forty_posts(max_posts, limit):
    h = Harness([post("1")])

    await h.run(max_posts=max_posts)

    timeline_calls = [c for c in h.calls if c[0] == "timeline"]
    assert len(timeline_calls) == 1 and timeline_calls[0][1:3] == ("uknf", limit)


async def test_no_more_documents_than_the_cap_are_ingested():
    h = Harness([post(str(i), f"wpis {i}") for i in range(1, 41)])

    result = await h.run(max_posts=15)

    assert result.documents == 15 and len(h.ingested) == 15


async def test_the_follower_lookup_is_made_once_after_the_posts_came_back():
    h = Harness([post("1"), post("2")])

    await h.run()

    assert [c[0] for c in h.calls] == ["timeline", "followers"]


async def test_the_flow_does_not_wait_a_limiter_turn_itself_the_dispatcher_did_once():
    h = Harness([post("1")])

    await h.run()

    assert h.waits == 0


async def test_missing_cookies_end_the_run_before_any_request():
    h = Harness([post("1")])

    result = await h.run(cookies=None)

    assert result.error == JobError(Reason.INVALID_REQUEST, "X cookies are not configured", SRC)
    assert h.calls == []


async def test_a_restriction_on_the_timeline_call_ends_the_run_as_blocked_with_nothing_stored():
    h = Harness([post("1")], timeline_error=FetchFailure(Reason.BLOCKED, "X restricted the account"))

    with pytest.raises(FetchFailure) as failure:
        await h.run()

    assert failure.value.reason is Reason.BLOCKED
    assert h.ingested == [] and [c[0] for c in h.calls] == ["timeline"]


async def test_a_restriction_on_the_follower_lookup_keeps_the_posts_and_ends_the_run_blocked():
    h = Harness([post("1"), post("2")], followers_error=FetchFailure(Reason.BLOCKED, "X restricted the account"))

    result = await h.run()

    assert result.documents == 2 and result.error.reason is Reason.BLOCKED
    assert h.authors[0]["followers"] is None and [c[0] for c in h.calls] == ["timeline", "followers"]


@pytest.mark.parametrize("reason", [Reason.HTTP_ERROR, Reason.TIMEOUT, Reason.PARSE_ERROR])
async def test_a_failed_follower_lookup_without_a_restriction_leaves_followers_null(reason):
    h = Harness([post("1")], followers_error=FetchFailure(reason, "lookup failed"))

    result = await h.run()

    assert (result.documents, result.error) == (1, None) and h.authors[0]["followers"] is None


@pytest.mark.parametrize("reason", [Reason.HTTP_ERROR, Reason.TIMEOUT, Reason.PARSE_ERROR])
async def test_other_timeline_failures_propagate_with_their_reason_and_emit_nothing(reason):
    h = Harness([post("1")], timeline_error=FetchFailure(reason, "failed"))

    with pytest.raises(FetchFailure) as failure:
        await h.run()

    assert failure.value.reason is reason and h.ingested == []


# --- the adapter: library errors and the Scweet call ---------------------------------------------------------------


@pytest.mark.parametrize(
    "error, reason",
    [
        (AuthError("401"), Reason.BLOCKED),
        (RateLimitError("429"), Reason.BLOCKED),
        (AccountPoolExhausted("no account left"), Reason.BLOCKED),
        (RunFailed("account is locked: challenge required"), Reason.BLOCKED),
        (RunFailed("Your account is suspended"), Reason.BLOCKED),
        (NetworkError("connection reset"), Reason.HTTP_ERROR),
        (asyncio.TimeoutError(), Reason.TIMEOUT),
        (TimeoutError(), Reason.TIMEOUT),
        (RuntimeError("something nobody planned for"), Reason.PARSE_ERROR),
        (KeyError("tweet_id"), Reason.PARSE_ERROR),
    ],
)
def test_every_library_error_maps_to_a_reason_of_the_closed_set(error, reason):
    assert x.map_library_error(error).reason is reason


def test_a_library_error_carrying_the_cookies_and_the_proxy_host_leaks_neither():
    secret_message = f"GET https://x.com failed: auth_token={COOKIES[0]} ct0={COOKIES[1]} via proxy pl-sticky.proxy.example"

    try:
        try:
            raise RunFailed(secret_message)
        except Exception as exc:
            raise x.map_library_error(exc) from None
    except FetchFailure as failure:
        rendered = "".join(traceback.format_exception(failure)) + str(failure) + failure.detail
        assert failure.__cause__ is None and failure.__suppress_context__
    for secret in (*COOKIES, "pl-sticky.proxy.example"):
        assert secret not in rendered


class FakeScweet:
    created = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.calls = []
        FakeScweet.created.append(self)

    async def aget_profile_tweets(self, users, **kwargs):
        self.calls.append(("tweets", users, kwargs))
        return FIXTURE[:3]

    async def aget_user_info(self, users, **kwargs):
        self.calls.append(("info", users, kwargs))
        return [{"username": "uknf", "name": "Urząd KNF", "followers_count": 26773}]


@pytest.fixture(autouse=True)
def reset_fake():
    FakeScweet.created = []


async def test_the_timeline_call_is_one_library_call_with_the_limit_and_one_empty_page_at_most():
    timeline = await x.scweet_timeline("uknf", 25, COOKIES, client_factory=FakeScweet)

    (client,) = FakeScweet.created
    assert client.calls == [("tweets", ["uknf"], {"limit": 25, "max_empty_pages": 1})]
    assert len(timeline.posts) == 3 and timeline.name == "Urząd KNF"


async def test_the_client_gets_the_cookies_and_keeps_its_state_out_of_the_working_directory():
    await x.scweet_timeline("uknf", 20, COOKIES, client_factory=FakeScweet)

    kwargs = FakeScweet.created[0].kwargs
    assert kwargs["cookies"] == {"auth_token": COOKIES[0], "ct0": COOKIES[1]}
    assert kwargs["manifest_scrape_on_init"] is False
    assert Path(kwargs["db_path"]).is_absolute() and Path.cwd() not in Path(kwargs["db_path"]).parents


async def test_the_follower_lookup_reads_the_count_from_the_account_info():
    followers = await x.scweet_followers("uknf", COOKIES, client_factory=FakeScweet)

    assert followers == 26773
    assert FakeScweet.created[0].calls == [("info", ["uknf"], {})]


@pytest.mark.parametrize("info", [[], [{"username": "uknf"}], [{"followers_count": "many"}], [{"followers_count": -1}], [{"followers_count": True}]])
async def test_an_unreadable_follower_count_is_none(info):
    class Odd(FakeScweet):
        async def aget_user_info(self, users, **kwargs):
            return info

    assert await x.scweet_followers("uknf", COOKIES, client_factory=Odd) is None


async def test_a_library_failure_inside_the_call_is_mapped_without_the_original_as_cause():
    class Failing(FakeScweet):
        async def aget_profile_tweets(self, users, **kwargs):
            raise RunFailed(f"cookie {COOKIES[0]} was refused")

    with pytest.raises(FetchFailure) as failure:
        await x.scweet_timeline("uknf", 20, COOKIES, client_factory=Failing)

    assert failure.value.__cause__ is None and failure.value.__suppress_context__
    assert COOKIES[0] not in "".join(traceback.format_exception(failure.value))


async def test_a_failure_while_building_the_client_is_mapped_too():
    def broken(**kwargs):
        raise RuntimeError(f"bad cookie {COOKIES[1]}")

    with pytest.raises(FetchFailure) as failure:
        await x.scweet_timeline("uknf", 20, COOKIES, client_factory=broken)

    assert COOKIES[1] not in "".join(traceback.format_exception(failure.value))
