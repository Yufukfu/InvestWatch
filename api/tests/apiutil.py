"""Helpers for API tests: a fake object store, service factories and DB seeding from contracts/mocks."""

from __future__ import annotations

import asyncio
import json
import os

import pytest
from sqlalchemy import create_engine, insert
from sqlalchemy.ext.asyncio import create_async_engine

from conftest import CONTRACTS_DIR
from investwatch_api.app import Services
from investwatch_api.db.mapping import document_to_row, finding_to_row, source_to_row
from investwatch_api.db.tables import documents, findings, sources

DEAD_PG = "postgresql+psycopg://nobody:x@127.0.0.1:1/none?connect_timeout=1"
DEAD_REDIS = "redis://127.0.0.1:1/0"


class FakeObjectStore:
    def __init__(self, objects: dict[str, bytes] | None = None, up: bool = True, slow: bool = False):
        self.objects = dict(objects or {})
        self.up = up
        self.slow = slow
        self.requested: list[str] = []

    async def get(self, key: str) -> bytes | None:
        from investwatch_api.objectstore import ObjectStoreError

        self.requested.append(key)
        if not self.up:
            raise ObjectStoreError("down")
        return self.objects.get(key)

    async def ping(self) -> bool:
        if self.slow:
            await asyncio.sleep(10)
        return self.up


def redis_url() -> str:
    url = os.environ.get("TEST_REDIS_URL", "").strip()
    if not url:
        pytest.skip("TEST_REDIS_URL is not set (see api/README.md)")
    return url


def make_services(db_url: str, redis: str, objects=None) -> Services:
    from redis.asyncio import Redis

    return Services(engine=create_async_engine(db_url),
                    redis=Redis.from_url(redis, socket_connect_timeout=1, socket_timeout=2),
                    objects=objects if objects is not None else FakeObjectStore())


def mock_items(name: str) -> list[dict]:
    data = json.loads((CONTRACTS_DIR / "mocks" / name).read_text(encoding="utf-8"))
    return data["items"] if isinstance(data, dict) else data


def seed_mocks(sync_url: str) -> dict[str, list[dict]]:
    """Insert contracts/mocks sources, documents and findings; returns the mock items."""
    data = {"sources": mock_items("sources.json"), "documents": mock_items("documents.json"),
            "findings": mock_items("findings.json")}
    engine = create_engine(sync_url)
    with engine.begin() as conn:
        for s in data["sources"]:
            conn.execute(insert(sources).values(source_to_row(s)))
        for d in data["documents"]:
            conn.execute(insert(documents).values(document_to_row(d)))
        for f in data["findings"]:
            conn.execute(insert(findings).values(finding_to_row(f)))
    engine.dispose()
    return data
