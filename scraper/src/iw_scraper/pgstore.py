"""`SourceStore` over the shared `sources` table (`api/migrations`). The scraper writes only the two run columns."""

import uuid
from collections.abc import Sequence
from datetime import datetime

import asyncpg

from iw_scraper.types import Source

_COLUMNS = "id, platform, name, url, source_kind, target_modules, schedule_cron, active"


def _source(record: asyncpg.Record) -> Source:
    return Source(
        id=str(record["id"]),
        name=record["name"],
        platform=record["platform"],
        url=record["url"],
        source_kind=record["source_kind"],
        target_modules=tuple(record["target_modules"]),
        active=record["active"],
        schedule_cron=record["schedule_cron"],
    )


def _uuid(value: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(value)
    except ValueError:
        return None


class PgSourceStore:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def get(self, source_id: str) -> Source | None:
        key = _uuid(source_id)
        if key is None:
            return None
        record = await self._pool.fetchrow(f"SELECT {_COLUMNS} FROM sources WHERE id = $1", key)
        return _source(record) if record else None

    async def mark_running(self, source_id: str) -> None:
        await self._pool.execute("UPDATE sources SET last_run_status = 'running' WHERE id = $1", uuid.UUID(source_id))

    async def mark_finished(self, source_id: str, *, at: datetime, status: str) -> None:
        await self._pool.execute(
            "UPDATE sources SET last_run_at = $2, last_run_status = $3 WHERE id = $1", uuid.UUID(source_id), at, status
        )

    async def known_urls(self, urls: Sequence[str]) -> set[str]:
        if not urls:
            return set()
        records = await self._pool.fetch("SELECT url FROM documents WHERE url = ANY($1::text[])", list(urls))
        return {record["url"] for record in records}

    async def collectable(self) -> Sequence[Source]:
        """Every active source a collector reads (`Source.collectable`): the hosts a run may be redirected to are theirs."""
        records = await self._pool.fetch(f"SELECT {_COLUMNS} FROM sources WHERE active")
        return [source for source in map(_source, records) if source.collectable]

    async def never_run_scheduled(self) -> Sequence[Source]:
        """Collectable (so active) sources with a cron that no job has ended for yet (`last_run_at` is set by a failed job too)."""
        records = await self._pool.fetch(
            f"SELECT {_COLUMNS} FROM sources WHERE schedule_cron IS NOT NULL AND last_run_at IS NULL ORDER BY name, id"
        )
        return [source for source in map(_source, records) if source.collectable]

    async def schedulable(self) -> Sequence[Source]:
        records = await self._pool.fetch(f"SELECT {_COLUMNS} FROM sources WHERE active AND schedule_cron IS NOT NULL")
        return [source for source in map(_source, records) if source.collectable]
