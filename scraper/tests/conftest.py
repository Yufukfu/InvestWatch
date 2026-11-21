"""Fixtures for the ingest tests.

The service-backed tests need PostgreSQL, Redis and MinIO. Their addresses come from the environment
(`IW_TEST_PG_DSN`, `IW_TEST_REDIS_URL`, `IW_TEST_MINIO_*`); without them those tests are skipped, so the
pure-logic tests still run anywhere.
"""

import os
import uuid
from pathlib import Path

import asyncpg
import pytest
import pytest_asyncio

from iw_scraper.types import Source

SCHEMA_SQL = (Path(__file__).parent / "schema.sql").read_text()


def _require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        message = f"{name} not set (needs the test containers)"
        if os.environ.get("CI"):
            # in CI a skipped service test would hide the core spec scenarios behind a green run
            pytest.fail(message)
        pytest.skip(message)
    return value


@pytest_asyncio.fixture
async def pool():
    """A pool on a fresh, throwaway schema (dropped afterwards)."""
    dsn = _require("IW_TEST_PG_DSN")
    schema = f"t_{uuid.uuid4().hex[:12]}"
    admin = await asyncpg.connect(dsn)
    await admin.execute(f'CREATE SCHEMA "{schema}"')
    created = await asyncpg.create_pool(dsn, min_size=1, max_size=4, server_settings={"search_path": schema})
    async with created.acquire() as conn:
        await conn.execute(SCHEMA_SQL)
    try:
        yield created
    finally:
        await created.close()
        await admin.execute(f'DROP SCHEMA "{schema}" CASCADE')
        await admin.close()


@pytest_asyncio.fixture
async def redis_client():
    """A Redis client; tests use their own stream name, so nothing is shared between tests."""
    from redis import asyncio as aioredis

    client = aioredis.from_url(_require("IW_TEST_REDIS_URL"), decode_responses=True)
    try:
        yield client
    finally:
        await client.aclose()


@pytest.fixture
def stream_name() -> str:
    return f"iw:documents:test:{uuid.uuid4().hex[:8]}"


@pytest_asyncio.fixture
async def storage():
    """A Storage on a unique bucket. The bucket is made here, as Damian's `minio-init` does in the stack:
    the service itself never creates it."""
    import asyncio

    from iw_scraper.ingest.storage import Storage

    store = Storage(
        _require("IW_TEST_MINIO_ENDPOINT"),
        os.environ["IW_TEST_MINIO_ACCESS_KEY"],
        os.environ["IW_TEST_MINIO_SECRET_KEY"],
        bucket=f"iw-raw-test-{uuid.uuid4().hex[:10]}",
    )
    await asyncio.to_thread(store._client.make_bucket, store.bucket)
    try:
        yield store
    finally:
        for key in await store.list_keys():
            await store.remove(key)
        await asyncio.to_thread(store._client.remove_bucket, store.bucket)


@pytest.fixture
def source() -> Source:
    return Source(
        id=str(uuid.uuid4()),
        name="Alfa",
        platform="web",
        url="https://alfa.example.com/",
        source_kind="firm_own",
        target_modules=("M2",),
        active=True,
    )


@pytest_asyncio.fixture
async def seeded_source(pool, source):
    """The `sources` row that `documents.source_id` points at."""
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO sources (id, name, platform, url, source_kind, target_modules) VALUES ($1, $2, $3, $4, $5, $6)",
            uuid.UUID(source.id), source.name, source.platform, source.url, source.source_kind,
            ["M3"],
        )
    return source
