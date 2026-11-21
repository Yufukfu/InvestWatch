"""Insert the first registered source, the KNF public warnings list, if it is not there yet.

    python -m iw_scraper.seed [CRON]   (needs DATABASE_URL; CRON is a 5-field `schedule_cron`, default none)

Idempotent: a source with the same URL is left alone. The dashboard owns every other `sources` edit.
"""

import asyncio
import os
import sys

import asyncpg
from croniter import croniter

KNF_NAME = "KNF ostrzeżenia publiczne"
KNF_URL = "https://www.knf.gov.pl/dla_konsumenta/ostrzezenia_publiczne"
_INSERT = """
INSERT INTO sources (id, name, platform, url, source_kind, target_modules, schedule_cron, active)
SELECT gen_random_uuid(), $1, 'web', $2, 'third_party', ARRAY['M3'], $3, true
WHERE NOT EXISTS (SELECT 1 FROM sources WHERE url = $2)
RETURNING id
"""


async def seed_knf(pool: asyncpg.Pool, *, cron: str | None = None) -> str | None:
    """The new source's id, or None when the URL was already registered."""
    row = await pool.fetchrow(_INSERT, KNF_NAME, KNF_URL, cron)
    return str(row["id"]) if row else None


def cron_from(argv: list[str]) -> str | None:
    """The optional first argument of the command line; an invalid cron ends the process before any write
    (the scheduler would otherwise skip the source with a logged warning on every tick)."""
    if len(argv) < 2:
        return None
    if not croniter.is_valid(argv[1]):
        raise SystemExit(f"invalid cron: {argv[1]!r}")
    return argv[1]


async def main() -> None:
    pool = await asyncpg.create_pool(os.environ["DATABASE_URL"], min_size=1, max_size=1)
    try:
        source_id = await seed_knf(pool, cron=cron_from(sys.argv))
    finally:
        await pool.close()
    sys.stdout.write(f"inserted {source_id}\n" if source_id else "already registered\n")


if __name__ == "__main__":
    asyncio.run(main())
