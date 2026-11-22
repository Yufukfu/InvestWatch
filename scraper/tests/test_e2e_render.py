"""Render end to end on real Redis, PostgreSQL and MinIO and the real renderer container (spec page-rendering).

Needs the `renderer-e2e` service of `scraper/compose.test.yaml` (`--profile e2e`) and `IW_TEST_RENDERER_URL`; without
it the module is skipped. The demo pages are synthetic stand-ins for a broker's and a bank's IKE offer. Only the
network guards are relaxed (the demo hosts are on the renderer container, a private address).
"""

import asyncio
import json
import os
import socket
import uuid

import pytest
from arq.connections import RedisSettings, create_pool

from iw_scraper.rendering import DomainPause, PageRenderer, RenderBudget, http_renderer
from iw_scraper.domaingate import DomainGate
from iw_scraper.guards import DomainHealth
from iw_scraper.ratelimit import DomainLimiter
from iw_scraper.targets import UrlGuard
from stack import stack, wait_for

RENDERER_URL = os.environ.get("IW_TEST_RENDERER_URL")
pytestmark = pytest.mark.skipif(not RENDERER_URL, reason="needs the renderer-e2e service (IW_TEST_RENDERER_URL)")

HOSTS = ("xtb.demo.test", "mbank.demo.test")
PORT = 8081
PNG = b"\x89PNG\r\n\x1a\n"


class DemoAddresses:
    """The demo hosts live on the renderer container, which the real address guard refuses as private."""

    async def check(self, host: str) -> str:
        return socket.gethostbyname(RENDERER_URL.split("//")[1].split(":")[0])


async def seed(pool, host: str) -> str:
    source_id = uuid.uuid4()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO sources (id, name, platform, url, source_kind, target_modules, active)"
            " VALUES ($1, $2, 'web', $3, 'firm_own', ARRAY['M2'], true)",
            source_id, host, f"http://{host}:{PORT}/",
        )
    return str(source_id)


async def stored(pool, source_id: str):
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT id, payload FROM documents WHERE source_id = $1", uuid.UUID(source_id))
    return [(str(row["id"]), json.loads(row["payload"])) for row in rows]


@pytest.mark.parametrize("host", HOSTS)
async def test_a_demo_page_is_stored_with_blocks_and_three_screenshots(pool, storage, host):
    async def urls():
        return UrlGuard(list(HOSTS), [PORT])

    redis = await create_pool(RedisSettings.from_dsn(os.environ["IW_TEST_REDIS_URL"]))
    try:
        gate = DomainGate(redis, max_retry_after=300.0, failure_threshold=5, pause_seconds=300.0)
        renderer = PageRenderer(
            http_renderer(RENDERER_URL),
            DomainLimiter(redis, 0.05),
            DomainPause(gate, lambda domain: DomainHealth(redis, domain, threshold=5, cooldown=300.0)),
            RenderBudget(redis, 20),
            timeout_seconds=90.0,
            ports=(PORT,),
        )
        async with stack(pool, storage, urls=urls, addresses=DemoAddresses(), renderer=renderer) as rt:
            source_id = await seed(pool, host)
            await rt.redis.xadd("iw:scan-requests", {"source_id": source_id, "requested_at": "2026-11-22T00:00:00Z"})

            async def done():
                return bool(await stored(pool, source_id))

            await wait_for(done, timeout=120.0)
            (document_id, payload), = await stored(pool, source_id)

            blocks = payload["blocks"]
            assert blocks and {b["viewport"] for b in blocks} == {"desktop", "mobile", "tablet"}
            assert {b["region"] for b in blocks} >= {"main", "legal"}
            assert any(b["font_size_px"] <= 11 and b["region"] in ("legal", "footer", "main") for b in blocks)
            assert set(payload["screenshots"]) == {"desktop", "mobile", "tablet"}
            for key in payload["screenshots"].values():
                assert key.startswith(f"shot/{document_id}/") and await storage.exists(key)
            assert payload["scrape_meta"]["scraper"] == "httpx" and payload["scrape_meta"]["render"]["browser_version"]
            objects = sorted(await storage.list_keys())

            await rt.redis.xadd("iw:scan-requests", {"source_id": source_id, "requested_at": "2026-11-22T00:05:00Z"})
            await asyncio.sleep(8)  # a rerun of an unchanged page costs no render and adds no object
            assert len(await stored(pool, source_id)) == 1 and sorted(await storage.list_keys()) == objects
            print(json.dumps({"host": host, "blocks": len(blocks), "payload_bytes": len(json.dumps(payload))}))
    finally:
        await redis.aclose()
