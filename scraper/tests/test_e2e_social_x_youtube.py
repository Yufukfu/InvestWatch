"""End to end for the X and YouTube seed rows on real Redis, PostgreSQL and MinIO: a scan request goes through the
consumer, the arq worker, the dedicated flow of the platform and the ingest pipeline.

The two platform adapters are replaced by the saved real answers (the Scweet timeline rows, the channel and watch pages):
a flow is built over fixture-backed functions and registered for its host in place of the production one. The seed rows,
the dispatch in `run_source`, ingest, PostgreSQL, MinIO, the stream and the scan events are the production wiring.
"""

import json
import uuid
from dataclasses import replace

from iw_scraper.collect import Stages
from iw_scraper.fetch import FetchResult
from iw_scraper.ratelimit import host_key
from iw_scraper.robots import RobotsVerdict
from iw_scraper.seed import SEEDS_DIR, load_seed_dir, seed_sources
from iw_scraper.social import x, youtube
from iw_scraper.social.registry import registry
from iw_scraper.targets import UrlGuard
from stack import LoopbackAddresses, stack as running_stack, wait_for
from test_social_x import FIXTURE as X_ROWS
from test_social_youtube import CHANNEL_PAGE, LIST_URL, channel_ids, watch_body, watch_url

DOCUMENTS_STREAM = "iw:documents"
X_URL = "https://x.com/uknf"
YOUTUBE_URL = "https://www.youtube.com/@UKNFpolska"
TRACKS = "captions.playerCaptionsTracklistRenderer.captionTracks"
ORIGINAL_POSTS = 13  # the saved timeline has 20 posts, 7 of them reposts
FOLLOWERS = 26773
VIDEOS = 3


async def seed(pool, url: str) -> str:
    entries = [e for e in load_seed_dir(SEEDS_DIR) if e.platform in ("x", "youtube")]
    await seed_sources(pool, entries)
    return str(await pool.fetchval("SELECT id FROM sources WHERE url = $1", url))


async def finished(events, source_id: str) -> list[dict]:
    return [e["data"] for e in events if e["type"] == "scan.finished" and e["data"]["source_id"] == source_id]


async def _has(events, source_id, count) -> bool:
    return len(await finished(events, source_id)) >= count


def register_flow(monkeypatch, host: str, flow) -> None:
    registration = registry.for_url(f"https://{host}/")
    monkeypatch.setitem(registry._by_host, host_key(host), replace(registration, flow=flow))


class Pages:
    """The `fetch` and `check_robots` stages over the saved YouTube pages; records every page request."""

    def __init__(self, ids) -> None:
        self.pages = {LIST_URL: CHANNEL_PAGE, **{watch_url(i): watch_body(i, **{TRACKS: [{"languageCode": "pl"}]}) for i in ids}}
        self.requests: list[str] = []
        self.cookies: list = []

    def stages(self) -> Stages:
        async def fetch(url, identity, proxy, **kw):
            self.requests.append(url)
            self.cookies.append(kw.get("cookies"))
            return FetchResult(url, 200, "text/html; charset=utf-8", self.pages[url], {}, None)

        async def check_robots(url, identity, proxy, **kw):
            return RobotsVerdict(True, "no robots.txt")

        async def close_session(session):
            return None

        return Stages(open_session=lambda identity: object(), close_session=close_session, check_robots=check_robots, fetch=fetch)


async def test_an_x_source_yields_documents_from_the_home_ip_and_a_rerun_adds_nothing(pool, storage, events, monkeypatch):
    calls = []

    async def timeline(handle, limit, cookies):
        calls.append(("timeline", handle, limit))
        return x.timeline_from_scweet(X_ROWS)

    async def followers(handle, cookies):
        calls.append(("followers", handle))
        return FOLLOWERS

    register_flow(monkeypatch, "x.com", x.make_flow(timeline=timeline, followers=followers, cookies=lambda: ("a" * 40, "b" * 40)))
    source_id = await seed(pool, X_URL)
    guard = UrlGuard(["x.com"])

    async def urls():
        return guard

    async def no_page_fetch(*args, **kw):
        raise AssertionError("an X run reads no page through the fetch layer")

    async def close_session(session):
        return None

    stages = Stages(open_session=lambda identity: object(), close_session=close_session, check_robots=no_page_fetch, fetch=no_page_fetch)
    async with running_stack(pool, storage, urls=urls, addresses=LoopbackAddresses(), stages=stages) as rt:
        await rt.redis.xadd("iw:scan-requests", {"source_id": source_id, "requested_at": "2026-11-22T12:00:00Z"})
        await wait_for(lambda: _has(events, source_id, 1))

        rows = await pool.fetch("SELECT * FROM documents WHERE source_id = $1 ORDER BY url", uuid.UUID(source_id))
        assert len(rows) == ORIGINAL_POSTS
        assert {(r["platform"], r["source_kind"]) for r in rows} == {("x", "unknown")}
        assert all(r["url"].startswith("https://x.com/uknf/status/") and len(r["content_hash"]) == 64 for r in rows)
        payload = json.loads(rows[0]["payload"])
        assert payload["scrape_meta"]["scraper"] == "api" and payload["scrape_meta"]["post_id"].isdigit()
        assert payload["author"]["handle"] == "@uknf" and payload["author"]["followers"] == FOLLOWERS
        assert all([await storage.exists(r["html_object_key"]) for r in rows])
        assert await rt.redis.xlen(DOCUMENTS_STREAM) == ORIGINAL_POSTS
        assert (await finished(events, source_id))[0] == {"source_id": source_id, "documents": ORIGINAL_POSTS, "status": "ok"}
        assert calls == [("timeline", "uknf", 40), ("followers", "uknf")]

        await rt.redis.xadd("iw:scan-requests", {"source_id": source_id, "requested_at": "2026-11-22T12:05:00Z"})
        await wait_for(lambda: _has(events, source_id, 2))

        assert (await finished(events, source_id))[1] == {"source_id": source_id, "documents": 0, "status": "ok"}
        assert await pool.fetchval("SELECT count(*) FROM documents WHERE source_id = $1", uuid.UUID(source_id)) == ORIGINAL_POSTS
        assert await rt.redis.xlen(DOCUMENTS_STREAM) == ORIGINAL_POSTS


async def test_a_youtube_source_yields_one_document_per_video_with_transcripts_and_a_rerun_requests_no_video_again(
    pool, storage, events, monkeypatch
):
    ids = channel_ids()[:VIDEOS]
    pages = Pages(ids)

    async def transcript(video_id, language, proxy_url):
        return f"Transkrypcja {video_id}"

    register_flow(
        monkeypatch, "www.youtube.com",
        youtube.make_flow(max_videos=lambda: VIDEOS, transcript=transcript, proxy=lambda: "http://u:p@proxy.example.net:8000"),
    )
    source_id = await seed(pool, YOUTUBE_URL)
    guard = UrlGuard(["www.youtube.com"])

    async def urls():
        return guard

    async with running_stack(pool, storage, urls=urls, addresses=LoopbackAddresses(), stages=pages.stages()) as rt:
        await rt.redis.xadd("iw:scan-requests", {"source_id": source_id, "requested_at": "2026-11-22T12:00:00Z"})
        await wait_for(lambda: _has(events, source_id, 1))

        rows = await pool.fetch("SELECT * FROM documents WHERE source_id = $1 ORDER BY url", uuid.UUID(source_id))
        assert sorted(r["url"] for r in rows) == sorted(watch_url(i) for i in ids)
        assert {(r["platform"], r["source_kind"]) for r in rows} == {("youtube", "unknown")}
        first = next(r for r in rows if r["url"] == watch_url(ids[0]))
        payload = json.loads(first["payload"])
        assert (payload["scrape_meta"]["video_id"], payload["scrape_meta"]["transcript"]) == (ids[0], "caption")
        assert first["text"].endswith(f"Transkrypcja {ids[0]}")
        assert payload["author"]["handle"] == "@UKNFpolska" and payload["author"]["followers"] is None
        assert all([await storage.exists(r["html_object_key"]) for r in rows])
        assert await rt.redis.xlen(DOCUMENTS_STREAM) == VIDEOS
        assert (await finished(events, source_id))[0] == {"source_id": source_id, "documents": VIDEOS, "status": "ok"}
        assert pages.requests == [LIST_URL, *(watch_url(i) for i in ids)]
        assert set(map(str, pages.cookies)) == {str({"SOCS": "CAI"})}

        pages.requests.clear()
        await rt.redis.xadd("iw:scan-requests", {"source_id": source_id, "requested_at": "2026-11-22T12:05:00Z"})
        await wait_for(lambda: _has(events, source_id, 2))

        assert (await finished(events, source_id))[1] == {"source_id": source_id, "documents": 0, "status": "ok"}
        assert pages.requests == [LIST_URL]  # every listed video is stored: no watch page, no transcript
        assert await rt.redis.xlen(DOCUMENTS_STREAM) == VIDEOS
