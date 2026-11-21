"""End to end for a Telegram source on real Redis, PostgreSQL and MinIO: a scan request goes through the consumer,
the arq worker, the social branch of the collector and the ingest pipeline.

The pages are the saved real channel pages, served by an injected `Stages.fetch`: the URL form (`https://t.me/s/<handle>`)
and the host are fixed by the spec, so a loopback HTTP stub cannot stand in for them. Ingest, PostgreSQL, MinIO, the
stream and the scan events are the production wiring of `app.py`.
"""

import json
import uuid
from pathlib import Path

from iw_scraper.collect import Stages
from iw_scraper.fetch import FetchResult
from iw_scraper.robots import RobotsVerdict
from iw_scraper.targets import UrlGuard
from stack import LoopbackAddresses, stack as running_stack, wait_for

FIXTURES = Path(__file__).parent / "fixtures"
CHANNEL = "https://t.me/s/kdpwiadomosci"
OLDER = "https://t.me/s/kdpwiadomosci?before=5179"
DOCUMENTS_STREAM = "iw:documents"
TEXT_POSTS = 18 + 20  # page one has 20 posts (two without text), page two 20 posts with text


class TelegramStub:
    """The `fetch` and `check_robots` stages over the saved pages; records every page request."""

    def __init__(self) -> None:
        self.pages = {
            CHANNEL: (FIXTURES / "telegram_kdpwiadomosci.html").read_bytes(),
            OLDER: (FIXTURES / "telegram_rarecryptosignals_before.html").read_bytes(),
        }
        self.requests: list[str] = []

    def stages(self) -> Stages:
        async def fetch(url, identity, proxy, **kw):
            self.requests.append(url)
            return FetchResult(url, 200, "text/html; charset=utf-8", self.pages[url], {}, None)

        async def check_robots(url, identity, proxy, **kw):
            return RobotsVerdict(True, "no robots.txt")

        async def close_session(session):
            return None

        return Stages(
            open_session=lambda identity: object(), close_session=close_session, check_robots=check_robots,
            fetch=fetch,
        )


async def seed(pool) -> str:
    source_id = uuid.uuid4()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO sources (id, name, platform, url, source_kind, target_modules, active)"
            " VALUES ($1, 'KDP', 'other', $2, 'third_party', ARRAY['M1'], true)",
            source_id, CHANNEL,
        )
    return str(source_id)


async def finished(events, source_id: str) -> list[dict]:
    return [e["data"] for e in events if e["type"] == "scan.finished" and e["data"]["source_id"] == source_id]


async def _has(events, source_id, count) -> bool:
    return len(await finished(events, source_id)) >= count


async def test_a_telegram_source_yields_documents_with_objects_and_announcements_and_a_rerun_adds_nothing(
    pool, storage, events
):
    source_id = await seed(pool)
    telegram = TelegramStub()
    guard = UrlGuard(["t.me"])

    async def urls():
        return guard

    async with running_stack(pool, storage, urls=urls, addresses=LoopbackAddresses(), stages=telegram.stages()) as rt:
        await rt.redis.xadd("iw:scan-requests", {"source_id": source_id, "requested_at": "2026-11-21T12:00:00Z"})
        await wait_for(lambda: _has(events, source_id, 1))

        rows = await pool.fetch("SELECT * FROM documents WHERE source_id = $1 ORDER BY url", uuid.UUID(source_id))
        assert len(rows) == TEXT_POSTS
        assert {(r["platform"], r["source_kind"]) for r in rows} == {("other", "third_party")}
        assert all(r["url"].startswith("https://t.me/") and len(r["content_hash"]) == 64 for r in rows)
        assert json.loads(rows[0]["payload"])["scrape_meta"]["network"] == "telegram"
        assert all([await storage.exists(r["html_object_key"]) for r in rows])
        assert await rt.redis.xlen(DOCUMENTS_STREAM) == TEXT_POSTS
        assert (await finished(events, source_id))[0] == {"source_id": source_id, "documents": TEXT_POSTS, "status": "ok"}
        assert telegram.requests == [CHANNEL, OLDER]

        telegram.requests.clear()
        await rt.redis.xadd("iw:scan-requests", {"source_id": source_id, "requested_at": "2026-11-21T12:05:00Z"})
        await wait_for(lambda: _has(events, source_id, 2))

        assert (await finished(events, source_id))[1] == {"source_id": source_id, "documents": 0, "status": "ok"}
        assert await pool.fetchval("SELECT count(*) FROM documents WHERE source_id = $1", uuid.UUID(source_id)) == TEXT_POSTS
        assert await rt.redis.xlen(DOCUMENTS_STREAM) == TEXT_POSTS
        assert telegram.requests == [CHANNEL]  # nothing new on the newest page: no older page is requested
