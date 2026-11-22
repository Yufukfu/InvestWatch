"""The YouTube collector: the newest videos of a public channel, one document per video (ADR 0109).

A dedicated flow on the fetch path: the channel's `/videos` page and each watch page go through the shared fetch
layer, guards, limiter and robots check, with the fixed consent cookie `SOCS=CAI` (without it the channel page ends on
`consent.youtube.com`, which the URL guard refuses). Both pages embed their data as JSON (`ytInitialData`,
`ytInitialPlayerResponse`); a page without it is skipped and counted, never stored empty. Videos are requested one at a
time and a stored video is never requested again.
"""

import json
import logging
import re
import time
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, timezone

from iw_scraper.config import youtube_max_videos
from iw_scraper.fetch import FetchDeferred, FetchFailure
from iw_scraper.jobs import AttemptResult
from iw_scraper.parsing import ParseFailure
from iw_scraper.social.model import Flow, FlowContext
from iw_scraper.types import JobError, Reason

_log = logging.getLogger(__name__)

CONSENT_COOKIE = "SOCS=CAI"
_CHANNEL_URL = re.compile(r"https://www\.youtube\.com/@([A-Za-z0-9._-]{3,30})")
_VIDEO_ID = re.compile(r"[A-Za-z0-9_-]{11}")
_VIDEO_DETAILS = ("videoId", "title", "channelId", "author", "shortDescription", "lengthSeconds")
_MICROFORMAT = ("publishDate", "uploadDate", "ownerChannelName", "externalChannelId", "category", "lengthSeconds")


@dataclass(frozen=True)
class ChannelList:
    channel_id: str
    video_ids: tuple[str, ...]  # newest first, no repeats


@dataclass(frozen=True)
class Track:
    language: str
    kind: str | None  # `asr` for an automatic caption


@dataclass(frozen=True)
class Video:
    video_id: str
    title: str
    description: str
    published_at: str | None  # UTC ISO-8601
    channel_id: str
    channel_name: str | None
    tracks: tuple[Track, ...]
    stored: dict  # what goes into `html`: player details, microformat and the track list, without any token


def valid_url(url: str) -> bool:
    """`https://www.youtube.com/@<handle>`, the handle of 3 to 30 letters, digits, dots, hyphens or underscores."""
    return _CHANNEL_URL.fullmatch(url) is not None


def _embedded(body: bytes, name: str) -> dict | None:
    """The JSON object a page assigns to `var <name> =`, or None when it is absent or broken."""
    text = body.decode("utf-8", errors="replace")
    match = re.search(rf"var {name}\s*=\s*", text)
    if match is None:
        return None
    try:
        data, _ = json.JSONDecoder().raw_decode(text, match.end())
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def _dicts(node) -> Iterator[dict]:
    stack = [node]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            yield current
            stack.extend(current.values())
        elif isinstance(current, list):
            stack.extend(reversed(current))


def _get(node, *path):
    for key in path:
        node = node.get(key) if isinstance(node, dict) else None
    return node


def parse_channel(body: bytes) -> ChannelList:
    """The channel id and the video ids of a channel's `/videos` page, in page order."""
    unreadable = ParseFailure(Reason.PARSE_ERROR, "no readable video list")
    data = _embedded(body, "ytInitialData")
    channel_id = _get(data, "metadata", "channelMetadataRenderer", "externalId")
    if data is None or not isinstance(channel_id, str) or not channel_id:
        raise unreadable
    ids: dict[str, None] = {}
    for node in _dicts(data):
        candidate = None
        if node.get("contentType") == "LOCKUP_CONTENT_TYPE_VIDEO":
            candidate = node.get("contentId")
        elif isinstance(node.get("videoRenderer"), dict):
            candidate = node["videoRenderer"].get("videoId")
        if isinstance(candidate, str) and _VIDEO_ID.fullmatch(candidate):
            ids.setdefault(candidate)
    if not ids:
        raise unreadable
    return ChannelList(channel_id, tuple(ids))


def _published_at(microformat) -> str | None:
    value = _get(microformat, "publishDate") or _get(microformat, "uploadDate")
    if not isinstance(value, str):
        return None
    try:
        moment = datetime.fromisoformat(value)
    except ValueError:
        return None
    if moment.tzinfo is None:  # a bare date: its zone is unknown, so it is taken as UTC midnight
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc).isoformat()


def _tracks(data: dict) -> tuple[Track, ...]:
    raw = _get(data, "captions", "playerCaptionsTracklistRenderer", "captionTracks")
    tracks = []
    for item in raw if isinstance(raw, list) else ():
        if isinstance(item, dict) and isinstance(item.get("languageCode"), str) and item["languageCode"]:
            kind = item.get("kind")
            tracks.append(Track(item["languageCode"], kind if isinstance(kind, str) else None))
    return tuple(tracks)


def parse_watch(body: bytes) -> Video | str:
    """The video of a watch page, or `"unplayable"` (unavailable, private, age-restricted) or `"unreadable"`."""
    data = _embedded(body, "ytInitialPlayerResponse")
    status = _get(data, "playabilityStatus", "status")
    if not isinstance(status, str):
        return "unreadable"
    if status != "OK":
        return "unplayable"
    details, microformat = _get(data, "videoDetails"), _get(data, "microformat", "playerMicroformatRenderer")
    video_id, title, channel_id = (_get(details, key) for key in ("videoId", "title", "channelId"))
    if not all(isinstance(value, str) and value.strip() for value in (video_id, title, channel_id)):
        return "unreadable"
    description = _get(details, "shortDescription")
    name = _get(microformat, "ownerChannelName") or _get(details, "author")
    tracks = _tracks(data)
    stored = {
        "videoDetails": {key: details[key] for key in _VIDEO_DETAILS if key in details},
        "microformat": {key: microformat[key] for key in _MICROFORMAT if isinstance(microformat, dict) and key in microformat},
        "captionTracks": [
            {"languageCode": track.language, **({"kind": track.kind} if track.kind else {})} for track in tracks
        ],
    }
    return Video(
        video_id=video_id, title=title.strip(), description=description.strip() if isinstance(description, str) else "",
        published_at=_published_at(microformat), channel_id=channel_id, channel_name=name if isinstance(name, str) else None,
        tracks=tracks, stored=stored,
    )


def _watch_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"


def _page(video: Video, *, http_status: int) -> dict:
    """The page dict `Ingestor.ingest` takes: the title, the description and (later) the transcript, one text."""
    text = "\n\n".join(part for part in (video.title, video.description) if part)
    url = _watch_url(video.video_id)
    return {
        "url": url, "canonical_url": url, "http_status": http_status, "title": video.title, "lang": None,
        "text": text, "published_at": video.published_at, "links": [],
        "scrape_meta": {"video_id": video.video_id, "transcript": "none"},
        "html": json.dumps(video.stored, ensure_ascii=False, sort_keys=True),
    }


def make_flow(*, max_videos=youtube_max_videos) -> Flow:
    """The YouTube flow; `max_videos` is the one thing a test replaces."""

    async def flow(ctx: FlowContext) -> AttemptResult:
        source = ctx.source
        match = _CHANNEL_URL.fullmatch(source.url)
        if match is None:
            raise ParseFailure(Reason.INVALID_REQUEST, "source URL is not a YouTube channel URL")
        handle = match.group(1)
        if (refusal := await ctx.check_robots()) is not None:
            return refusal

        listing = parse_channel((await ctx.fetch(f"{source.url}/videos", cookie=CONSENT_COOKIE)).body)
        wanted = listing.video_ids[: max_videos()]
        known = await ctx.known_urls([_watch_url(video_id) for video_id in wanted])
        remaining = [video_id for video_id in wanted if _watch_url(video_id) not in known]

        profile = f"https://www.youtube.com/@{handle}"
        stored = unplayable = unreadable = foreign = 0
        for video_id in remaining:
            began = time.monotonic()
            try:
                result = await ctx.fetch(_watch_url(video_id), cookie=CONSENT_COOKIE)
            except FetchDeferred as deferred:
                if stored == 0:
                    raise
                return AttemptResult(documents=stored, deferral=deferred.deferral)
            except FetchFailure as failure:  # a block ends the run; what was stored stays
                if stored == 0:
                    raise
                error = JobError(failure.reason, failure.detail, source.id)
                return AttemptResult(documents=stored, error=error, http_status=failure.http_status)
            video = parse_watch(result.body)
            if video == "unplayable":
                unplayable += 1
            elif video == "unreadable":
                unreadable += 1
            elif video.channel_id != listing.channel_id:
                foreign += 1
            else:
                author = {"name": video.channel_name, "handle": f"@{handle}", "profile_url": profile, "followers": None}
                outcome = await ctx.ingest(
                    _page(video, http_status=result.status), source, fetched_at=ctx.clock(),
                    duration_ms=int((time.monotonic() - began) * 1000), proxy=result.proxy_id, author=author,
                )
                if outcome.outcome == "failed":  # the ingestor has recorded it in `job_errors`
                    return AttemptResult(documents=stored, error=outcome.error, recorded=True)
                stored += outcome.outcome == "inserted"
        _log.info(
            "youtube videos of %s: %d stored, %d already stored, %d unplayable skipped, %d unreadable skipped, "
            "%d of another channel skipped",
            handle, stored, len(wanted) - len(remaining), unplayable, unreadable, foreign,
        )
        if remaining and unreadable == len(remaining):
            raise ParseFailure(Reason.PARSE_ERROR, "no readable watch page")
        return AttemptResult(documents=stored)

    return flow


flow = make_flow()
