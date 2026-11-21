"""Opt-in smoke test: one real request to the KNF page through the full stack (`pytest -m scraper_live`).

Deselected by default and outside CI. It needs the test services (see `compose.test.yaml`) and outbound HTTPS;
it makes one page request and one `robots.txt` request with the real guards, no proxy.
"""

import os
import uuid

import pytest

from iw_scraper.app import allowed_urls
from iw_scraper.pgstore import PgSourceStore
from iw_scraper.seed import seed_knf
from iw_scraper.targets import AddressGuard
from stack import stack, wait_for

pytestmark = pytest.mark.scraper_live


async def test_the_real_knf_page_becomes_a_document(pool, storage, events):
    source_id = await seed_knf(pool)
    urls = allowed_urls(PgSourceStore(pool), [], (80, 443))
    async with stack(pool, storage, urls=urls, addresses=AddressGuard()) as rt:
        await rt.redis.xadd("iw:scan-requests", {"source_id": source_id})

        async def done() -> bool:
            return any(e["type"] == "scan.finished" for e in events)

        await wait_for(done, timeout=120.0)
        finished = next(e["data"] for e in events if e["type"] == "scan.finished")

        assert finished["status"] == "ok", finished
        assert await pool.fetchval("SELECT count(*) FROM documents WHERE source_id = $1", uuid.UUID(source_id)) == 1


async def test_a_real_public_telegram_channel_becomes_documents(pool, storage, events):
    handle = os.environ.get("IW_LIVE_TELEGRAM_HANDLE")
    if not handle:
        pytest.skip("IW_LIVE_TELEGRAM_HANDLE not set (the public channel to collect once)")
    source_id = uuid.uuid4()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO sources (id, name, platform, url, source_kind, target_modules, active)"
            " VALUES ($1, 'live', 'other', $2, 'unknown', ARRAY['M3'], true)",
            source_id, f"https://t.me/s/{handle}",
        )
    urls = allowed_urls(PgSourceStore(pool), [], (80, 443))
    async with stack(pool, storage, urls=urls, addresses=AddressGuard()) as rt:
        await rt.redis.xadd("iw:scan-requests", {"source_id": str(source_id)})

        async def done() -> bool:
            return any(e["type"] == "scan.finished" for e in events)

        await wait_for(done, timeout=180.0)
        finished = next(e["data"] for e in events if e["type"] == "scan.finished")

        assert finished["status"] == "ok", finished
        assert finished["documents"] >= 1, finished
