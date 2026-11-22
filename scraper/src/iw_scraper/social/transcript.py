"""The YouTube transcript adapter over `youtube-transcript-api` (ADR 0109).

The caption URL is refused from the home IP, so the one request goes through the dedicated residential proxy
(`YT_TRANSCRIPT_PROXY`). The library is synchronous and runs in a worker thread. Every library failure is mapped at
this boundary to a `FetchFailure` of the closed `Reason` set (a block is `blocked`) or to `None` (no usable transcript),
raised without the original as cause: the proxy URL carries credentials and library messages may echo it.
"""

import asyncio
import re

from iw_scraper.fetch import FetchFailure
from iw_scraper.timeout_session import TimeoutSession
from iw_scraper.types import Reason

_VIDEO_ID = re.compile(r"[A-Za-z0-9_-]{11}")
TRANSCRIPT_TIMEOUT = 15.0  # seconds; the library sets none, so `TimeoutSession` does and `wait_for` backs it up
_TIMEOUT_NAMES = ("Timeout", "ReadTimeout", "ConnectTimeout")


def map_library_error(error: Exception) -> FetchFailure | None:
    """None when the video has no usable transcript, else a `FetchFailure`; its detail never carries library text."""
    from youtube_transcript_api import (
        AgeRestricted, InvalidVideoId, NoTranscriptFound, PoTokenRequired, RequestBlocked, TranscriptsDisabled,
        VideoUnavailable, VideoUnplayable, YouTubeRequestFailed,
    )

    if isinstance(error, RequestBlocked):  # includes IpBlocked
        return FetchFailure(Reason.BLOCKED, "YouTube refused the transcript request")
    if isinstance(
        error,
        (NoTranscriptFound, TranscriptsDisabled, AgeRestricted, VideoUnavailable, VideoUnplayable, InvalidVideoId, PoTokenRequired),
    ):
        return None
    # the library's HTTP client raises its own timeout classes; this module imports no HTTP client, so they are known by name
    if isinstance(error, TimeoutError) or any(cls.__name__ in _TIMEOUT_NAMES for cls in type(error).__mro__):
        return FetchFailure(Reason.TIMEOUT, "the transcript request timed out")
    if isinstance(error, (YouTubeRequestFailed, OSError)):
        return FetchFailure(Reason.HTTP_ERROR, "the transcript could not be requested")
    return FetchFailure(Reason.PARSE_ERROR, f"the transcript answer could not be read ({type(error).__name__})")


def _fetch_sync(video_id: str, language: str, proxy_url: str, api_factory, timeout: float) -> str | None:
    if api_factory is None:
        from youtube_transcript_api import YouTubeTranscriptApi as api_factory
    from youtube_transcript_api.proxies import GenericProxyConfig

    api = api_factory(
        proxy_config=GenericProxyConfig(http_url=proxy_url, https_url=proxy_url), http_client=TimeoutSession(timeout)
    )
    snippets = api.fetch(video_id, languages=[language])
    return " ".join(" ".join(snippet.text for snippet in snippets).split()) or None


async def fetch_transcript(
    video_id: str, language: str, proxy_url: str, *, api_factory=None, timeout: float = TRANSCRIPT_TIMEOUT
) -> str | None:
    """The transcript text of one video in `language`, or None when it has none; one request through `proxy_url`."""
    if not _VIDEO_ID.fullmatch(video_id):
        raise FetchFailure(Reason.INVALID_REQUEST, "not a YouTube video id")
    try:
        return await asyncio.wait_for(asyncio.to_thread(_fetch_sync, video_id, language, proxy_url, api_factory, timeout), timeout)
    except Exception as error:  # every library failure, whatever its type; the original stays out of the chain
        failure = map_library_error(error)
        if failure is None:
            return None
        raise failure from None
