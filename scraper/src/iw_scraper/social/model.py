"""What every social collector returns, and how it becomes the page dict `Ingestor.ingest` takes.

A collector module (one per platform, registered by host in `registry`) turns one fetched page into a `Channel`.
Nothing here knows a platform: the platform's name and profile URL travel in the `Channel`.
"""

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class Link:
    href: str
    text: str


@dataclass(frozen=True)
class Post:
    message_id: int
    permalink: str
    text: str
    published_at: str | None
    views: int | None
    links: tuple[Link, ...]
    html: str


@dataclass(frozen=True)
class Channel:
    network: str  # the real network, e.g. `telegram`: `platform` stays `other` while the contract enum has no value
    title: str | None
    handle: str | None
    profile_url: str | None
    followers: int | None
    posts: tuple[Post, ...]  # only the posts that have text
    skipped: int  # posts without text (image, video, sticker)
    older_url: str | None

    @property
    def seen(self) -> int:
        """Posts on the page, with or without text: what `SOCIAL_MAX_POSTS` counts."""
        return len(self.posts) + self.skipped


def _utc(timestamp: str | None) -> str | None:
    """`timestamp` in UTC ISO-8601, or None when it is missing, unreadable or has no offset."""
    if not timestamp:
        return None
    try:
        moment = datetime.fromisoformat(timestamp)
    except ValueError:
        return None
    # no offset: the zone is unknown, and `astimezone` would assume the host's own
    return moment.astimezone(timezone.utc).isoformat() if moment.tzinfo is not None else None


def build_author(channel: Channel) -> dict:
    """The contract `author` of every post of the channel: the channel's own header, as the platform shows it.

    It is passed to `Ingestor.ingest` as the trusted `author=` argument. The page dict never carries it: ingest
    drops an `author` found on a page, because markup is written by the post's author (issue 36).
    """
    return {
        "name": channel.title,
        "handle": channel.handle,
        "profile_url": channel.profile_url,
        "followers": channel.followers,
    }


def build_page(channel: Channel, post: Post, *, http_status: int) -> dict:
    """The page dict `Ingestor.ingest` takes for one post: the contract fields the page decides, plus `html`.

    `platform`, `source_kind`, `source_id`, the fetch time and the fetch facts of `scrape_meta` are added from the
    source row and the fetch by ingest, never taken from the page.
    """
    return {
        "url": post.permalink,
        "canonical_url": post.permalink,
        "http_status": http_status,
        "title": None,
        "lang": None,
        "text": post.text,
        "published_at": _utc(post.published_at),
        "links": [{"href": link.href, "text": link.text or None} for link in post.links],
        "scrape_meta": {"message_id": post.message_id, "views": post.views, "network": channel.network},
        "html": post.html,
    }
