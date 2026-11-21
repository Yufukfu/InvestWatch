import uuid
from datetime import timedelta

import asyncpg
from redis.exceptions import RedisError

from iw_scraper.ingest.errors import record_error
from iw_scraper.types import JobError, Reason

STREAM = "iw:documents"
DEFAULT_GRACE = timedelta(seconds=60)
SCHEMA_VERSION = "v1"

# Skip-locked row claim: concurrent sweeps take different rows. Only the grace period protects a run that is
# still publishing its own fresh row, because its row is committed but not yet marked.
_CLAIM = """
SELECT id, source_id FROM documents
WHERE stream_published_at IS NULL AND created_at < now() - $1::interval
ORDER BY created_at, id
LIMIT $2
FOR UPDATE SKIP LOCKED
"""


async def publish(redis, document_id: str, stream: str = STREAM) -> None:
    """`XADD iw:documents * document_id <uuid> schema v1`. Call only after the row is committed."""
    await redis.xadd(stream, {"document_id": document_id, "schema": SCHEMA_VERSION})


async def mark_published(pool: asyncpg.Pool, document_id: str) -> None:
    async with pool.acquire() as conn:
        await conn.execute("UPDATE documents SET stream_published_at = now() WHERE id = $1", uuid.UUID(document_id))


async def sweep(
    pool: asyncpg.Pool, redis, *, grace: timedelta = DEFAULT_GRACE, batch: int = 100, stream: str = STREAM
) -> int:
    """Publish documents that are committed, unpublished and older than `grace`. Returns how many were published.

    At-least-once: a crash between XADD and the marker update republishes that row, and consumers deduplicate
    by `document_id`. A Redis failure stops the sweep and is recorded as `publish_failed`.
    """
    published = 0
    failure: JobError | None = None
    async with pool.acquire() as conn, conn.transaction():
        for row in await conn.fetch(_CLAIM, grace, batch):
            try:
                await publish(redis, str(row["id"]), stream)
            except (RedisError, OSError) as exc:
                failure = JobError(
                    Reason.PUBLISH_FAILED, f"sweep: {type(exc).__name__}: {exc}", str(row["source_id"])
                )
                break
            await conn.execute("UPDATE documents SET stream_published_at = now() WHERE id = $1", row["id"])
            published += 1
    if failure is not None:
        await record_error(pool, failure)
    return published
