"""YouTube transcripts: the flow's use of an injected transcript function (language choice, final outcomes, block
and failure rules, no proxy) and the adapter over `youtube-transcript-api` against a fake client."""

import logging
import threading

import pytest
import requests
from youtube_transcript_api import (
    AgeRestricted, IpBlocked, NoTranscriptFound, RequestBlocked, TranscriptsDisabled, VideoUnavailable,
    YouTubeRequestFailed,
)

from iw_scraper.fetch import FetchFailure
from iw_scraper.social import transcript, youtube
from iw_scraper.types import Reason
from test_social_youtube import Harness, channel_ids, watch_body, with_watch_pages

PROXY = "http://user-77:s3cr3tpass@proxy.example.net:8000"
TRACKS = "captions.playerCaptionsTracklistRenderer.captionTracks"


def tracks(*languages, kind=None):
    return [{"languageCode": code, **({"kind": kind} if kind else {})} for code in languages]


def pages_with_tracks(ids, *languages):
    pages = with_watch_pages([])
    for video_id in ids:
        pages[youtube._watch_url(video_id)] = watch_body(video_id, **{TRACKS: tracks(*languages)})
    return pages


class Recorder:
    """A transcript function that records its calls and answers from a script (a value, None or an exception)."""

    def __init__(self, *answers):
        self.answers, self.calls = list(answers), []

    async def __call__(self, video_id, language, proxy_url):
        self.calls.append((video_id, language, proxy_url))
        answer = self.answers.pop(0) if len(self.answers) > 1 else self.answers[0]
        if isinstance(answer, Exception):
            raise answer
        return answer


async def run(h, fn, *, proxy=PROXY):
    """Runs the flow over every watch page the harness holds (the list page is the one other entry)."""
    flow = youtube.make_flow(max_videos=lambda: len(h.pages) - 1, transcript=fn, proxy=lambda: proxy)
    return await flow(h.context())


def metas(h):
    return [p["scrape_meta"]["transcript"] for p in h.ingested]


# --- the flow ------------------------------------------------------------------------------------------------------


async def test_the_transcript_follows_the_title_and_the_description_and_is_marked_caption():
    ids = channel_ids()[:1]
    h, fn = Harness(pages_with_tracks(ids, "pl")), Recorder("Dzień dobry, to jest nagranie.")
    await run(h, fn)
    parts = h.ingested[0]["text"].split("\n\n")
    assert parts[0] == h.ingested[0]["title"] and parts[-1] == "Dzień dobry, to jest nagranie."
    assert len(parts) >= 2 and metas(h) == ["caption"]


async def test_the_transcript_is_requested_once_per_video_through_the_configured_proxy():
    ids = channel_ids()[:2]
    h, fn = Harness(pages_with_tracks(ids, "pl")), Recorder("tekst")
    await run(h, fn)
    assert sorted(fn.calls) == sorted((video_id, "pl", PROXY) for video_id in ids)


async def test_the_polish_track_is_preferred_over_the_english_one():
    ids = channel_ids()[:1]
    h, fn = Harness(pages_with_tracks(ids, "en", "pl")), Recorder("tekst")
    await run(h, fn)
    assert [call[1] for call in fn.calls] == ["pl"]


async def test_without_a_polish_track_the_first_listed_track_is_used():
    ids = channel_ids()[:1]
    h, fn = Harness(pages_with_tracks(ids, "de", "en")), Recorder("text")
    await run(h, fn)
    assert [call[1] for call in fn.calls] == ["de"]


async def test_a_video_without_a_caption_track_makes_no_request_and_is_none():
    ids = channel_ids()[:1]
    h, fn = Harness(pages_with_tracks(ids)), Recorder("never")
    await run(h, fn)
    assert fn.calls == [] and metas(h) == ["none"]


async def test_a_transcript_the_library_reports_as_missing_is_none_and_the_document_is_stored():
    ids = channel_ids()[:1]
    h, fn = Harness(pages_with_tracks(ids, "pl")), Recorder(None)
    result = await run(h, fn)
    assert metas(h) == ["none"] and result.documents == 1 and result.error is None


async def test_a_blank_transcript_is_none_and_adds_no_empty_paragraph():
    ids = channel_ids()[:1]
    h, fn = Harness(pages_with_tracks(ids, "pl")), Recorder("  \n ")
    await run(h, fn)
    assert metas(h) == ["none"] and not h.ingested[0]["text"].endswith("\n\n")


async def test_without_a_proxy_no_request_is_made_and_a_log_line_says_transcripts_are_off(caplog):
    ids = channel_ids()[:2]
    h, fn = Harness(pages_with_tracks(ids, "pl")), Recorder("never")
    with caplog.at_level(logging.INFO):
        result = await run(h, fn, proxy=None)
    assert fn.calls == [] and metas(h) == ["none", "none"] and result.error is None
    assert sum("transcripts are off" in r.getMessage() for r in caplog.records) == 1


async def test_a_block_marks_that_video_failed_and_stops_transcripts_for_the_run():
    ids = channel_ids()[:3]
    h, fn = Harness(pages_with_tracks(ids, "pl")), Recorder(FetchFailure(Reason.BLOCKED, "blocked"))
    result = await run(h, fn)
    assert metas(h) == ["failed", "none", "none"] and len(fn.calls) == 1
    assert result.documents == 3 and result.error is None  # the documents are stored; the block is not a job error


async def test_another_failure_marks_that_video_failed_and_the_next_transcript_is_still_requested():
    ids = channel_ids()[:3]
    h = Harness(pages_with_tracks(ids, "pl"))
    fn = Recorder(FetchFailure(Reason.TIMEOUT, "slow"), "dalszy tekst")
    await run(h, fn)
    assert metas(h) == ["failed", "caption", "caption"] and len(fn.calls) == 3


async def test_a_failed_transcript_leaves_the_text_as_title_and_description():
    ids = channel_ids()[:1]
    h, fn = Harness(pages_with_tracks(ids, "pl")), Recorder(FetchFailure(Reason.HTTP_ERROR, "down"))
    await run(h, fn)
    assert "down" not in h.ingested[0]["text"] and metas(h) == ["failed"]


async def test_the_proxy_url_is_in_no_log_line_and_no_stored_page(caplog):
    ids = channel_ids()[:2]
    h = Harness(pages_with_tracks(ids, "pl"))
    fn = Recorder(FetchFailure(Reason.BLOCKED, "YouTube refused the transcript request"))
    with caplog.at_level(logging.DEBUG):
        result = await run(h, fn)
    everything = caplog.text + repr(h.ingested) + repr(result)
    for secret in (PROXY, "s3cr3tpass", "user-77", "proxy.example.net"):
        assert secret not in everything


async def test_the_stored_html_never_holds_the_transcript():
    ids = channel_ids()[:1]
    h, fn = Harness(pages_with_tracks(ids, "pl")), Recorder("unikalny-tekst-transkrypcji")
    await run(h, fn)
    assert "unikalny-tekst-transkrypcji" not in h.ingested[0]["html"]


async def test_a_video_that_is_already_stored_is_not_requested_again_for_a_transcript():
    ids = channel_ids()[:2]
    h = Harness(pages_with_tracks(ids, "pl"), known={youtube._watch_url(ids[0])})
    fn = Recorder("tekst")
    await run(h, fn)
    assert [call[0] for call in fn.calls] == [ids[1]]


# --- the adapter ---------------------------------------------------------------------------------------------------


class Snippet:
    def __init__(self, text):
        self.text = text


class FakeApi:
    """Stands in for `YouTubeTranscriptApi`: records its construction and `fetch` calls, answers from `result`."""

    def __init__(self, result):
        self.result, self.config, self.calls, self.thread = result, None, [], None

    def factory(self, *, proxy_config):
        self.config = proxy_config
        return self

    def fetch(self, video_id, languages=("en",)):
        self.calls.append((video_id, tuple(languages)))
        self.thread = threading.current_thread()
        if isinstance(self.result, BaseException):
            raise self.result
        return self.result


async def adapter(api, video_id="JLShF0trXZI", language="pl"):
    return await transcript.fetch_transcript(video_id, language, PROXY, api_factory=api.factory)


async def test_the_adapter_joins_the_snippets_into_one_text_with_single_spaces():
    api = FakeApi([Snippet("Dzień  dobry,"), Snippet("państwo\n"), Snippet(" witam.")])
    assert await adapter(api) == "Dzień dobry, państwo witam."
    assert api.calls == [("JLShF0trXZI", ("pl",))]


async def test_the_adapter_hands_the_proxy_to_the_library_for_both_schemes():
    api = FakeApi([Snippet("x")])
    await adapter(api)
    assert (api.config.http_url, api.config.https_url) == (PROXY, PROXY)


async def test_the_adapter_runs_the_synchronous_library_off_the_event_loop():
    api = FakeApi([Snippet("x")])
    await adapter(api)
    assert api.thread is not threading.main_thread()


@pytest.mark.parametrize(
    "error", [NoTranscriptFound("v", ["pl"], None), TranscriptsDisabled("v"), AgeRestricted("v"), VideoUnavailable("v")]
)
async def test_a_video_with_no_usable_transcript_is_none_not_an_error(error):
    assert await adapter(FakeApi(error)) is None


@pytest.mark.parametrize("error", [IpBlocked("v"), RequestBlocked("v")])
async def test_an_ip_block_is_blocked(error):
    with pytest.raises(FetchFailure) as caught:
        await adapter(FakeApi(error))
    assert caught.value.reason is Reason.BLOCKED


@pytest.mark.parametrize(
    ("error", "reason"),
    [
        (YouTubeRequestFailed("v", "boom"), Reason.HTTP_ERROR), (TimeoutError("t"), Reason.TIMEOUT),
        (ConnectionError("c"), Reason.HTTP_ERROR), (ValueError("odd"), Reason.PARSE_ERROR),
        (requests.exceptions.ReadTimeout("slow"), Reason.TIMEOUT), (requests.exceptions.ProxyError("p"), Reason.HTTP_ERROR),
    ],
)
async def test_every_other_library_failure_is_one_mapped_reason(error, reason):
    with pytest.raises(FetchFailure) as caught:
        await adapter(FakeApi(error))
    assert caught.value.reason is reason


async def test_a_failure_carries_neither_the_proxy_nor_the_library_text_nor_a_cause():
    api = FakeApi(ConnectionError(f"cannot reach {PROXY}"))
    with pytest.raises(FetchFailure) as caught:
        await adapter(api)
    failure = caught.value
    assert PROXY not in str(failure) and "s3cr3tpass" not in repr(failure) and "cannot reach" not in failure.detail
    assert failure.__cause__ is None and failure.__suppress_context__


@pytest.mark.parametrize("video_id", ["short", "has space!!", "../../etc/passwd", "a" * 12, ""])
async def test_a_malformed_video_id_is_refused_before_the_library_is_called(video_id):
    api = FakeApi([Snippet("x")])
    with pytest.raises(FetchFailure) as caught:
        await adapter(api, video_id=video_id)
    assert caught.value.reason is Reason.INVALID_REQUEST and api.calls == []
