"""First-run bootstrap: queue one scan for every source that has a cron and never ran, so a clean `up` fills itself.

    python -m iw_scraper.bootstrap          (needs DATABASE_URL and REDIS_URL; BOOTSTRAP_SCAN=false turns it off)
    python -m iw_scraper.bootstrap status   (needs DATABASE_URL; JSON report, exit 0 ready, 1 not yet, 2 cannot tell)

It writes the `scan_request` the dashboard's rescan writes (`iw:scan-requests`) and exits; the worker does the scans.
A Redis key per source keeps a rerun, a second `up` or a scale-out from queuing a source twice. A source without a
cron stays manual (the X and YouTube seed rows, ADR 0109), and one whose first scan failed is not queued again:
`last_run_at` is set by a failed job too, and the scheduler or an analyst retries it.
"""

import asyncio
import json
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


MODULES = ("M1", "M2", "M3")
_SOURCES = """
SELECT s.id::text AS id, s.name, s.url, s.schedule_cron IS NOT NULL AS scheduled, s.last_run_at, s.last_run_status,
       (SELECT e.reason FROM job_errors e WHERE e.source_id = s.id ORDER BY e.occurred_at DESC LIMIT 1) AS reason
FROM sources s WHERE s.active ORDER BY s.name, s.id
"""


def _source_state(row: asyncpg.Record) -> str:
    if row["last_run_status"] == "running":
        return "pending"
    if row["last_run_at"] is None:
        return "pending" if row["scheduled"] else "manual"
    return "failed" if row["last_run_status"] == "failed" else "scanned"


async def collect_status(pool: asyncpg.Pool) -> dict:
    """Where every active source and every pipeline stage stands, read in one read-only transaction."""
    async with pool.acquire() as conn, conn.transaction(readonly=True):
        sources = await conn.fetch(_SOURCES)
        documents = await conn.fetchval("SELECT count(*) FROM documents")
        findings = dict(await conn.fetch("SELECT module, count(*) FROM findings GROUP BY module"))
        points = dict(await conn.fetch("SELECT module, count(*) FROM calibration_points GROUP BY module"))
    listed = []
    for row in sources:
        state = _source_state(row)
        listed.append({"id": row["id"], "name": row["name"], "url": row["url"], "state": state,
                       "reason": row["reason"] if state == "failed" else None})
    counted = {module: findings.get(module, 0) for module in MODULES}
    missing = [module for module in MODULES if counted[module] == 0]
    pending = sum(entry["state"] == "pending" for entry in listed)
    return {
        "ready": not missing and pending == 0,
        "pending": pending,
        "missing_modules": missing,
        "documents": documents,
        "findings": counted,
        "calibration_points": {module: points.get(module, 0) for module in MODULES},
        "sources": listed,
    }


def exit_code(report: dict) -> int:
    return 0 if report["ready"] else 1


async def status_main(environ: Mapping[str, str]) -> int:
    """Print the report as JSON; 0 ready, 1 not yet, 2 when the database cannot be read (nothing on stdout)."""
    dsn = environ.get("DATABASE_URL")
    if not dsn:
        sys.stderr.write("DATABASE_URL is not set\n")
        return 2
    try:
        pool = await asyncpg.create_pool(dsn, min_size=1, max_size=1)
    except (OSError, asyncpg.PostgresError):
        sys.stderr.write("cannot connect to the database (check DATABASE_URL)\n")
        return 2
    try:
        report = await collect_status(pool)
    except asyncpg.PostgresError:
        sys.stderr.write("the database failed while reading the status (check that the schema is migrated)\n")
        return 2
    finally:
        await pool.close()
    sys.stdout.write(json.dumps(report, indent=2) + "\n")
    return exit_code(report)


def main(argv: list[str]) -> None:
    if argv[1:] == ["status"]:
        raise SystemExit(asyncio.run(status_main(os.environ)))
    if len(argv) > 1:
        raise SystemExit("usage: python -m iw_scraper.bootstrap [status]")
    configure_logging()
    asyncio.run(run(os.environ))


if __name__ == "__main__":
    main(sys.argv)
