"""First-run bootstrap: queue one scan for every source that has a cron and never ran, so a clean `up` fills itself.

    python -m iw_scraper.bootstrap          (needs DATABASE_URL and REDIS_URL; BOOTSTRAP_SCAN=false turns it off)

It writes the `scan_request` the dashboard's rescan writes (`iw:scan-requests`) and exits; the worker does the scans.
A Redis key per source keeps a rerun, a second `up` or a scale-out from queuing a source twice. A source without a
cron stays manual (the X and YouTube seed rows, ADR 0109), and one whose first scan failed is not queued again:
`last_run_at` is set by a failed job too, and the scheduler or an analyst retries it.
"""

import asyncio
import logging
import os
import sys
from collections.abc import Mapping
from datetime import UTC, datetime

import asyncpg
from redis import asyncio as aioredis
from redis.exceptions import RedisError

from iw_scraper.events import utc_iso
from iw_scraper.logs import configure_logging
from iw_scraper.pgstore import PgSourceStore
from iw_scraper.scan_requests import STREAM

DONE_KEY = "iw:bootstrap:{source_id}"

logger = logging.getLogger(__name__)


def bootstrap_enabled(environ: Mapping[str, str]) -> bool:
    """`BOOTSTRAP_SCAN`: `true` (also unset or empty) or `false`; anything else is a typo that must not silently scan."""
    value = environ.get("BOOTSTRAP_SCAN", "") or "true"
    if value not in ("true", "false"):
        raise SystemExit(f"BOOTSTRAP_SCAN must be true or false, not {value!r}")
    return value == "true"


async def enqueue_never_run(pool: asyncpg.Pool, redis) -> list[str]:
    """Queue a scan for each never-run scheduled source not queued before; returns their ids."""
    enqueued: list[str] = []
    for source in await PgSourceStore(pool).never_run_scheduled():
        key = DONE_KEY.format(source_id=source.id)
        if not await redis.set(key, "1", nx=True):
            continue  # an earlier run queued it; the worker may not have consumed it yet
        requested_at = utc_iso(datetime.now(UTC).replace(microsecond=0))
        try:
            await redis.xadd(STREAM, {"source_id": source.id, "requested_at": requested_at})
        except BaseException:
            await redis.delete(key)  # not queued: the next run must try again
            raise
        enqueued.append(source.id)
    return enqueued


async def run(environ: Mapping[str, str]) -> None:
    if not bootstrap_enabled(environ):
        logger.info("first-run bootstrap is disabled (BOOTSTRAP_SCAN=false)")
        return
    dsn, redis_url = environ.get("DATABASE_URL"), environ.get("REDIS_URL")
    if not dsn or not redis_url:
        raise SystemExit("DATABASE_URL and REDIS_URL must be set")
    # a driver's message can hold the host, user or part of the DSN: say only what failed
    try:
        pool = await asyncpg.create_pool(dsn, min_size=1, max_size=1)
    except (OSError, asyncpg.PostgresError):
        raise SystemExit("cannot connect to the database (check DATABASE_URL)") from None
    redis = aioredis.from_url(redis_url)
    try:
        enqueued = await enqueue_never_run(pool, redis)
    except RedisError:
        raise SystemExit("cannot queue scan requests: Redis failed (check REDIS_URL)") from None
    except asyncpg.PostgresError:
        raise SystemExit("the database failed while reading sources (check that the schema is migrated)") from None
    finally:
        await redis.aclose()
        await pool.close()
    logger.info("first-run bootstrap queued %d scan request(s)", len(enqueued))


def main(argv: list[str]) -> None:
    configure_logging()
    asyncio.run(run(os.environ))


if __name__ == "__main__":
    main(sys.argv)
