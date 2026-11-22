"""The X collector: the newest posts of a public account, read with a dedicated account's cookies (ADR 0109).

A dedicated flow, not a page parser: it runs from the home IP (`home_ip`), reads no `robots.txt` and draws no
identity, and calls `Scweet` once, which makes at most one account lookup and two timeline requests. Every library
failure is mapped to a `FetchFailure` at the adapter boundary without the original as cause, so no cookie reaches a
log, a job error or a traceback. The dedicated account is at risk (X suspends automation accounts): the first sign of
a restriction ends the run, and nothing here ever loops.
"""

import asyncio
import json
import logging
import re
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime

from iw_scraper.config import x_cookies
from iw_scraper.fetch import FetchFailure
from iw_scraper.jobs import AttemptResult
from iw_scraper.parsing import ParseFailure
from iw_scraper.social.model import Channel, Flow, FlowContext, Post, build_author, build_page
from iw_scraper.types import JobError, Reason

_log = logging.getLogger(__name__)

MAX_POSTS_PER_RUN = 40  # two timeline pages of twenty: the most one run asks of the account
_ACCOUNT_URL = re.compile(r"https://x\.com/([A-Za-z0-9_]{1,15})")
_LANG = re.compile(r"[a-z]{2}")
_CREATED_AT = "%a %b %d %H:%M:%S %z %Y"  # `Tue Sep 30 08:41:01 +0000 2025`
_RESTRICTION_WORDS = ("suspend", "locked", "challenge", "restricted", "unauthorized", "forbidden")


@dataclass(frozen=True)
class XPost:
    post_id: str | None
    text: str | None
    created_at: str | None
    lang: str | None
    is_repost: bool
    media_count: int


@dataclass(frozen=True)
class Timeline:
    name: str | None  # the account's display name, as the posts carry it
    posts: tuple[XPost, ...]


def valid_url(url: str) -> bool:
    """`https://x.com/<handle>`, the handle of 1 to 15 letters, digits or underscores, and nothing after it."""
    return _ACCOUNT_URL.fullmatch(url) is not None


# --- the adapter over Scweet -----------------------------------------------------------------------------------------


def map_library_error(error: Exception) -> FetchFailure:
    """A library failure as a `FetchFailure` of the closed `Reason` set. The detail never carries the library's text."""
    from Scweet import AccountPoolExhausted, AuthError, NetworkError, ProxyError, RateLimitError, ScweetError

    if isinstance(error, (AuthError, RateLimitError, AccountPoolExhausted)):
        return FetchFailure(Reason.BLOCKED, "X restricted the account or refused the cookies")
    if isinstance(error, (NetworkError, ProxyError)):
        return FetchFailure(Reason.HTTP_ERROR, "X could not be reached")
    if isinstance(error, (TimeoutError, asyncio.TimeoutError)):
        return FetchFailure(Reason.TIMEOUT, "X did not answer in time")
    if isinstance(error, ScweetError) and any(word in str(error).lower() for word in _RESTRICTION_WORDS):
        return FetchFailure(Reason.BLOCKED, "X restricted the account or refused the cookies")
    return FetchFailure(Reason.PARSE_ERROR, f"X answer could not be read ({type(error).__name__})")


def _row_post(row) -> XPost:
    if not isinstance(row, dict):
        return XPost(None, None, None, None, False, 0)
    media = row.get("media") if isinstance(row.get("media"), dict) else {}
    media_count = sum(len(media.get(key) or ()) for key in ("image_links", "video_links"))
    post_id = row.get("tweet_id")
    return XPost(
        post_id=str(post_id) if post_id not in (None, "") else None,
        text=row.get("text") if isinstance(row.get("text"), str) else None,
        created_at=row.get("timestamp") if isinstance(row.get("timestamp"), str) else None,
        lang=row.get("lang") if isinstance(row.get("lang"), str) else None,
        is_repost=bool(row.get("is_retweet")),
        media_count=media_count,
    )


def timeline_from_scweet(rows) -> Timeline:
    """The library's post dicts as `XPost`s (reposts flagged, not dropped) and the account's display name."""
    name = next(
        (
            row["user"]["name"]
            for row in rows
            if isinstance(row, dict) and isinstance(row.get("user"), dict) and row["user"].get("name")
        ),
        None,
    )
    return Timeline(name=name, posts=tuple(_row_post(row) for row in rows))


def _scweet_client(factory, cookies: tuple[str, str], state_dir: str):
    if factory is None:
        from Scweet import Scweet as factory
    return factory(
        cookies={"auth_token": cookies[0], "ct0": cookies[1]},
        db_path=f"{state_dir}/scweet_state.db",  # a temporary directory: the root file system is read-only
        manifest_scrape_on_init=False,
    )


async def scweet_timeline(handle: str, limit: int, cookies: tuple[str, str], *, client_factory=None) -> Timeline:
    """One library call for the account's newest `limit` posts; it pages twenty at a time and stops at an empty page."""
    try:
        with tempfile.TemporaryDirectory(prefix="iw-x-") as state_dir:
            client = await asyncio.to_thread(_scweet_client, client_factory, cookies, state_dir)
            rows = await client.aget_profile_tweets([handle], limit=limit, max_empty_pages=1)
            return timeline_from_scweet(rows)
    except Exception as error:  # every library failure, whatever its type; the original stays out of the chain
        raise map_library_error(error) from None


async def scweet_followers(handle: str, cookies: tuple[str, str], *, client_factory=None) -> int | None:
    """The account's follower count from one account lookup; None when the answer holds no usable count."""
    try:
        with tempfile.TemporaryDirectory(prefix="iw-x-") as state_dir:
            client = await asyncio.to_thread(_scweet_client, client_factory, cookies, state_dir)
            info = await client.aget_user_info([handle])
    except Exception as error:
        raise map_library_error(error) from None
    count = info[0].get("followers_count") if info and isinstance(info[0], dict) else None
    return count if isinstance(count, int) and not isinstance(count, bool) and count >= 0 else None


# --- the flow --------------------------------------------------------------------------------------------------------


def _created_at_iso(created_at: str | None) -> str | None:
    if not created_at:
        return None
    try:
        return datetime.strptime(created_at, _CREATED_AT).isoformat()  # aware; `build_page` normalises it to UTC
    except ValueError:
        return None


def _is_malformed(post: XPost) -> bool:
    return not (post.post_id and post.post_id.isdigit()) or _created_at_iso(post.created_at) is None


def _post(post: XPost, handle: str) -> Post:
    """A readable original post as the shared `Post`; `post_id` and the scraper kind ride in `scrape_meta`."""
    html = {
        "id": post.post_id, "text": post.text, "created_at": post.created_at, "lang": post.lang, "handle": handle,
        "media_count": post.media_count,
    }
    return Post(
        message_id=int(post.post_id), permalink=f"https://x.com/{handle}/status/{post.post_id}", text=post.text,
        published_at=_created_at_iso(post.created_at), views=None, links=(),
        html=json.dumps(html, ensure_ascii=False, sort_keys=True), extra={"post_id": post.post_id, "scraper": "api"},
    )


def _readable_posts(posts, handle: str):
    """The posts to store, and the counts of those skipped: malformed, reposts of other accounts, without text."""
    seen, kept, malformed, reposts, textless = set(), [], 0, 0, 0
    for post in posts:
        if _is_malformed(post):
            malformed += 1
        elif post.is_repost:
            reposts += 1
        elif not (post.text or "").strip():
            textless += 1
        elif post.post_id not in seen:
            seen.add(post.post_id)
            kept.append((post, _post(post, handle)))
    return kept, malformed, reposts, textless


def make_flow(*, timeline=scweet_timeline, followers=scweet_followers, cookies=x_cookies) -> Flow:
    """The X flow over an adapter; the arguments are the three things a test replaces."""

    async def flow(ctx: FlowContext) -> AttemptResult:
        source = ctx.source
        match = _ACCOUNT_URL.fullmatch(source.url)
        if match is None:
            raise ParseFailure(Reason.INVALID_REQUEST, "source URL is not an X account URL")
        handle, pair = match.group(1), cookies()
        if pair is None:
            return AttemptResult(error=JobError(Reason.INVALID_REQUEST, "X cookies are not configured", source.id))

        began = time.monotonic()
        limit = min(ctx.max_posts, MAX_POSTS_PER_RUN)
        fetched = await timeline(handle, limit, pair)  # a restriction raises here, before anything is stored
        posts = fetched.posts[:limit]
        kept, malformed, reposts, textless = _readable_posts(posts, handle)
        _log.info(
            "x posts of %s: %d to store, %d reposts skipped, %d without text skipped, %d malformed skipped",
            handle, len(kept), reposts, textless, malformed,
        )
        if posts and malformed == len(posts):
            raise ParseFailure(Reason.PARSE_ERROR, "no readable post in the timeline")
        if not kept:
            return AttemptResult(documents=0)

        follower_count, restriction = None, None
        try:
            follower_count = await followers(handle, pair)
        except FetchFailure as failure:  # the count is optional: only a restriction changes the outcome
            if failure.reason is Reason.BLOCKED:
                restriction = JobError(Reason.BLOCKED, failure.detail, source.id)
            _log.info("x follower count of %s not read: %s", handle, failure.reason.value)

        channel = Channel(
            network="x", title=fetched.name, handle=f"@{handle}", profile_url=f"https://x.com/{handle}",
            followers=follower_count, posts=(), skipped=0, older_url=None,
        )
        author, fetched_at, stored = build_author(channel), ctx.clock(), 0
        duration_ms = int((time.monotonic() - began) * 1000)
        for raw, post in kept:
            page = build_page(channel, post, http_status=None)
            page["lang"] = raw.lang if raw.lang and _LANG.fullmatch(raw.lang) else None
            outcome = await ctx.ingest(
                page, source, fetched_at=fetched_at, duration_ms=duration_ms, proxy=None, author=author
            )
            if outcome.outcome == "failed":  # the ingestor has recorded it in `job_errors`
                return AttemptResult(documents=stored, error=outcome.error, recorded=True)
            stored += outcome.outcome == "inserted"
        return AttemptResult(documents=stored, error=restriction)

    return flow


flow = make_flow()
