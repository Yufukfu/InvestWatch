"""End to end on real Redis, PostgreSQL and MinIO: a scan request goes through the consumer, the arq worker, the
collector (real fetch, robots and parse against a local stub of the saved KNF page) and the ingest pipeline.

Only the network guards are relaxed (the stub is on loopback); everything else is the production wiring of `app.py`.
"""

import asyncio
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from iw_scraper.targets import UrlGuard
from stack import LoopbackAddresses, stack as running_stack, wait_for

FIXTURES = Path(__file__).parent / "fixtures"


@asynccontextmanager
async def stack(pool, storage, stub, *, workers=1):
    guard = UrlGuard(["127.0.0.1"], [stub.port])

    async def urls():
        return guard

    async with running_stack(pool, storage, urls=urls, addresses=LoopbackAddresses(), workers=workers) as rt:
        yield rt

PAGE = "/komunikaty"
DOCUMENTS_STREAM = "iw:documents"


async def seed(pool, stub, *, delay=0.0) -> str:
    stub.route(PAGE, body=(FIXTURES / "knf_warnings.html").read_bytes(), delay=delay)
    stub.route("/robots.txt", status=404, body=b"", content_type="text/plain")
    source_id = uuid.uuid4()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO sources (id, name, platform, url, source_kind, target_modules, active)"
            " VALUES ($1, 'KNF', 'web', $2, 'third_party', ARRAY['M3'], true)",
            source_id, stub.url(PAGE),
        )
    return str(source_id)


async def scan(rt, source_id: str) -> None:
    await rt.redis.xadd("iw:scan-requests", {"source_id": source_id, "requested_at": "2026-11-21T12:00:00Z"})


async def finished(events, source_id: str) -> list[dict]:
    return [e["data"] for e in events if e["type"] == "scan.finished" and e["data"]["source_id"] == source_id]


async def document_count(pool, source_id: str) -> int:
    return await pool.fetchval("SELECT count(*) FROM documents WHERE source_id = $1", uuid.UUID(source_id))


async def test_a_scan_request_yields_one_document_object_and_announcement_and_a_rerun_adds_nothing(
    pool, storage, stub, events
):
    source_id = await seed(pool, stub)
    async with stack(pool, storage, stub) as rt:
        await scan(rt, source_id)
        await wait_for(lambda: _has(events, source_id, 1))

        row = await pool.fetchrow("SELECT * FROM documents WHERE source_id = $1", uuid.UUID(source_id))
        assert (row["platform"], row["source_kind"], row["http_status"]) == ("web", "third_party", 200)
        assert row["text"].strip() and len(row["content_hash"]) == 64
        assert await storage.exists(row["html_object_key"])
        assert [e[1][b"document_id"].decode() for e in await rt.redis.xrange(DOCUMENTS_STREAM)] == [str(row["id"])]
        assert (await finished(events, source_id))[0] == {"source_id": source_id, "documents": 1, "status": "ok"}
        assert (await pool.fetchrow("SELECT last_run_status FROM sources WHERE id = $1", uuid.UUID(source_id)))[0] == "ok"

        await scan(rt, source_id)
        await wait_for(lambda: _has(events, source_id, 2))

        assert (await finished(events, source_id))[1] == {"source_id": source_id, "documents": 0, "status": "ok"}
        assert await document_count(pool, source_id) == 1
        assert await rt.redis.xlen(DOCUMENTS_STREAM) == 1


async def _has(events, source_id, count) -> bool:
    return len(await finished(events, source_id)) >= count


async def test_two_workers_and_two_simultaneous_requests_store_the_page_once(pool, storage, stub, events):
    source_id = await seed(pool, stub, delay=1.5)  # long enough that the second job meets the first one running
    async with stack(pool, storage, stub, workers=2) as rt:
        await asyncio.gather(scan(rt, source_id), scan(rt, source_id))
        await wait_for(lambda: _settled(events, source_id))
        await asyncio.sleep(0.5)

        assert len([r for r in stub.requests if r.path == PAGE]) == 1  # the run lock coalesced the second job

        assert await document_count(pool, source_id) == 1
        assert await rt.redis.xlen(DOCUMENTS_STREAM) == 1
        assert sum(e["documents"] for e in await finished(events, source_id)) == 1


async def _settled(events, source_id) -> bool:
    # one job coalesces into the running one (no event) or both finish: at least one finish, none pending
    return len(await finished(events, source_id)) >= 1
