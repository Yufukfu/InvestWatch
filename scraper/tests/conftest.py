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
        pytest.skip(f"{name} not set (needs the test containers)")
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
            "INSERT INTO sources (id, name, platform, url, source_kind) VALUES ($1, $2, $3, $4, $5)",
            uuid.UUID(source.id), source.name, source.platform, source.url, source.source_kind,
        )
    return source
