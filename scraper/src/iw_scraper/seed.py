"""Register the KNF public warnings list and the sources of every `scraper/seeds/*.toml` file, where not there yet.

    python -m iw_scraper.seed [CRON]   (needs DATABASE_URL; CRON is a 5-field `schedule_cron` of the KNF row, default none)

All seed files are validated before anything is written. Idempotent: a source with the same URL is left alone,
including one the dashboard edited. The dashboard owns every other `sources` edit.
"""

import asyncio
import json
import os
import sys
import tomllib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

import asyncpg
from croniter import croniter

from iw_scraper.config import contracts_dir

KNF_NAME = "KNF ostrzeżenia publiczne"
KNF_URL = "https://www.knf.gov.pl/dla_konsumenta/ostrzezenia_publiczne"
_INSERT = """
INSERT INTO sources (id, name, platform, url, source_kind, target_modules, schedule_cron, active)
SELECT gen_random_uuid(), $1, 'web', $2, 'third_party', ARRAY['M3'], $3, true
WHERE NOT EXISTS (SELECT 1 FROM sources WHERE url = $2)
RETURNING id
"""


class SeedError(ValueError):
    """A seed file is invalid; the message names the file and entry."""


@dataclass(frozen=True)
class SeedEntry:
    name: str
    platform: str
    url: str
    source_kind: str
    target_modules: tuple[str, ...]
    schedule_cron: str | None


SEEDS_DIR = Path(__file__).resolve().parents[2] / "seeds"  # scraper/seeds, beside src/ (the image copies scraper/)
_REQUIRED = ("name", "url", "source_kind", "target_modules")
_OPTIONAL = ("platform", "schedule_cron")
_CRON_FIELDS = 5  # croniter.is_valid also accepts six


def _contract_values() -> tuple[set[str], set[str], set[str]]:
    """`platform`, `source_kind` and module values of the contract `source` schema, so the seed cannot drift from it."""
    properties = json.loads((contracts_dir() / "schemas" / "source.schema.json").read_text())["properties"]
    return (
        set(properties["platform"]["enum"]),
        set(properties["source_kind"]["enum"]),
        set(properties["target_modules"]["items"]["enum"]),
    )


def _is_plain_https_url(url: str) -> bool:
    parts = urlsplit(url)
    # userinfo would be stored and echoed in error messages; whitespace is never part of a fetchable URL
    return parts.scheme == "https" and bool(parts.hostname) and "@" not in parts.netloc and not any(c.isspace() for c in url)


def _parse(raw: object) -> SeedEntry:
    """One `[[source]]` table as an entry; raises ValueError with the problem."""
    if not isinstance(raw, dict):
        raise ValueError("not a table")
    unknown = sorted(set(raw) - {*_REQUIRED, *_OPTIONAL})
    if unknown:
        raise ValueError(f"unknown key {', '.join(unknown)}")
    missing = [key for key in _REQUIRED if key not in raw]
    if missing:
        raise ValueError(f"missing {', '.join(missing)}")
    platforms, kinds, modules = _contract_values()
    name, url, kind = raw["name"], raw["url"], raw["source_kind"]
    platform, cron, targets = raw.get("platform", "web"), raw.get("schedule_cron"), raw["target_modules"]
    if not isinstance(name, str) or not name.strip():
        raise ValueError("name is empty")
    if platform not in platforms:
        raise ValueError(f"platform {platform!r} is not one of {sorted(platforms)}")
    if kind not in kinds:
        raise ValueError(f"source_kind {kind!r} is not one of {sorted(kinds)}")
    if not isinstance(targets, list) or not targets or len(set(targets)) != len(targets) or not set(targets) <= modules:
        raise ValueError(f"target_modules must be a non-empty list of distinct values from {sorted(modules)}")
    if not isinstance(url, str) or not _is_plain_https_url(url):
        raise ValueError("url must be an https URL with a host, without credentials or spaces")
    if cron is not None and (not isinstance(cron, str) or len(cron.split()) != _CRON_FIELDS or not croniter.is_valid(cron)):
        raise ValueError("schedule_cron must be a valid 5-field cron expression")
    return SeedEntry(name, platform, url, kind, tuple(targets), cron)


def _read(path: Path) -> list[tuple[str, SeedEntry]]:
    """Each entry of one file with a label naming file, position and name."""
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as error:
        raise SeedError(f"{path.name}: not valid TOML ({error})") from None
    rows = data.get("source")
    if set(data) - {"source"} or not isinstance(rows, list) or not rows:
        raise SeedError(f"{path.name}: expected one or more [[source]] tables and nothing else")
    found = []
    for position, raw in enumerate(rows, start=1):
        name = raw.get("name") if isinstance(raw, dict) else None
        label = f"{path.name} entry {position}" + (f" ({name!r})" if isinstance(name, str) and name.strip() else "")
        try:
            found.append((label, _parse(raw)))
        except ValueError as error:
            raise SeedError(f"{label}: {error}") from None
    return found


def _unique(found: list[tuple[str, SeedEntry]]) -> list[SeedEntry]:
    seen: dict[str, str] = {}
    for label, entry in found:
        if entry.url in seen:
            raise SeedError(f"{seen[entry.url]} and {label} have the same URL {entry.url}")
        seen[entry.url] = label
    return [entry for _, entry in found]


def load_seed(path: Path) -> list[SeedEntry]:
    """The entries of one seed file; any invalid entry raises SeedError and nothing is returned."""
    return _unique(_read(path))


def load_seed_dir(directory: Path) -> list[SeedEntry]:
    """Every `*.toml` of the directory in file-name order, validated as one list (a URL repeated across files is a duplicate)."""
    return _unique([item for path in sorted(directory.glob("*.toml")) for item in _read(path)])


async def seed_knf(pool: asyncpg.Pool, *, cron: str | None = None) -> str | None:
    """The new source's id, or None when the URL was already registered."""
    async with locked(pool) as connection:
        row = await connection.fetchrow(_INSERT, KNF_NAME, KNF_URL, cron)
    return str(row["id"]) if row else None


_DATABASE_ERRORS = (OSError, ValueError, asyncpg.PostgresError, asyncpg.InterfaceError)
_LOCK_KEY = 7_302_011 # a constant for this writer only: it serialises concurrent seed runs (the table has no unique url)
_INSERT_SOURCE = """
INSERT INTO sources (id, name, platform, url, source_kind, target_modules, schedule_cron, active)
SELECT gen_random_uuid(), $1::text, $2::text, $3::text, $4::text, $5::text[], $6::text, true
WHERE NOT EXISTS (SELECT 1 FROM sources WHERE url = $3::text)
"""


@asynccontextmanager
async def locked(pool: asyncpg.Pool) -> AsyncIterator[asyncpg.Connection]:
    """A connection in a transaction that holds the seed lock, so concurrent seed runs take turns."""
    async with pool.acquire() as connection, connection.transaction():
        await connection.execute("SELECT pg_advisory_xact_lock($1)", _LOCK_KEY)
        yield connection


async def seed_sources(pool: asyncpg.Pool, entries: list[SeedEntry]) -> tuple[int, int]:
    """(inserted, already present). An entry whose URL has a row is left alone, whatever the dashboard made of that row."""
    inserted = 0
    async with locked(pool) as connection:
        for entry in entries:
            status = await connection.execute(
                _INSERT_SOURCE,
                entry.name, entry.platform, entry.url, entry.source_kind, list(entry.target_modules), entry.schedule_cron,
            )
            inserted += status == "INSERT 0 1"
    return inserted, len(entries) - inserted


async def seed_all(pool: asyncpg.Pool, *, directory: Path = SEEDS_DIR, cron: str | None = None) -> str:
    """Validate every seed file, then register the KNF source and the files' sources; the report text.

    Raises SeedError before any write when a file is invalid.
    """
    entries = load_seed_dir(directory)
    knf_id = await seed_knf(pool, cron=cron)
    inserted, present = await seed_sources(pool, entries)
    knf = f"inserted {knf_id}" if knf_id else "already registered"
    return f"{knf}\nsources: inserted {inserted}, already present {present}"


def cron_from(argv: list[str]) -> str | None:
    """The optional first argument of the command line."""
    return argv[1] if len(argv) > 1 else None


async def main() -> None:
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        raise SystemExit("DATABASE_URL is not set")
    # a driver's message can hold the host, user or part of the DSN: say only what failed
    try:
        pool = await asyncpg.create_pool(dsn, min_size=1, max_size=1)
    except _DATABASE_ERRORS:
        raise SystemExit("cannot connect to the database (check DATABASE_URL)") from None
    try:
        report = await seed_all(pool, cron=cron_from(sys.argv))
    except SeedError as error:
        raise SystemExit(str(error)) from None
    except _DATABASE_ERRORS:
        raise SystemExit("the database failed while seeding (check DATABASE_URL and that the schema is migrated)") from None
    finally:
        await pool.close()
    sys.stdout.write(report + "\n")


if __name__ == "__main__":
    asyncio.run(main())
