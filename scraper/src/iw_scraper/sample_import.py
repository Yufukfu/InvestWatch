"""Load saved samples (HTML, text, markdown) into the system through the normal ingest, with no network access.

    python -m iw_scraper.sample_import DIR [--kind KIND --modules M1,M3]

Without a `samples.toml` in DIR, `--kind` and `--modules` are required: routing is never inferred. Reading and the
manifest come first; the run against PostgreSQL, Redis and MinIO is at the end. The importer builds its own small
wiring from the environment of `app.runtime` and does not import `app.py`.
"""

import argparse
import asyncio
import json
import logging
import os
import re
import stat
import sys
import tomllib
from collections import Counter
from contextlib import asynccontextmanager
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from functools import lru_cache
from html import escape
from pathlib import Path
from urllib.parse import quote, urlsplit

import asyncpg
from jsonschema import Draft202012Validator, FormatChecker
from redis import asyncio as aioredis

from iw_scraper.config import contracts_dir, fetch_settings
from iw_scraper.events import utc_iso
from iw_scraper.ingest.document import parse_timestamp
from iw_scraper.ingest.errors import record_error
from iw_scraper.ingest.pipeline import Ingestor
from iw_scraper.ingest.storage import Storage
from iw_scraper.logs import configure_logging
from iw_scraper.parsing import ParseFailure, parse_page
from iw_scraper.pgstore import PgSourceStore
from iw_scraper.types import JobError, Reason, Source

log = logging.getLogger("iw_scraper.sample_import")

MANIFEST = "samples.toml"
CLIENT = "sample-import"
DEFAULT_PLATFORM = "web"
SAMPLE_HOST = "https://sample.invalid"  # `.invalid` never resolves; the stored schema accepts only http(s) URLs
MAX_MANIFEST_BYTES = 1_000_000
_WEB_SCHEMES = frozenset({"http", "https"})
_SET_KEYS = frozenset({"name", "url", "source_kind", "platform", "target_modules", "lang", "published_at", "author"})
_FILE_KEYS = frozenset({"url", "source_kind", "platform", "target_modules", "title", "lang", "published_at", "author"})


class ManifestError(ValueError):
    """The manifest or the routing flags are unusable; the message names the key."""


@dataclass(frozen=True)
class Entry:
    name: str
    skipped: str | None  # None: will be read; else why it is not ("unsupported", "symlink")


@dataclass(frozen=True)
class FileSettings:
    """Everything the manifest decides for one file."""

    url: str
    source_kind: str
    platform: str
    target_modules: tuple[str, ...]
    title: str | None = None
    lang: str | None = None
    published_at: str | None = None
    author: dict | None = None


@dataclass(frozen=True)
class SampleSet:
    name: str
    url: str  # of the set's source row
    source_kind: str
    platform: str
    target_modules: tuple[str, ...]
    slug: str
    defaults: dict
    files: dict

    def settings_for(self, file_name: str) -> FileSettings:
        values = {**self.defaults, **self.files.get(file_name, {})}
        values.setdefault("url", f"{SAMPLE_HOST}/{self.slug}/{quote(file_name)}")
        values["target_modules"] = tuple(values["target_modules"])
        return FileSettings(**values)


# --- reading ---------------------------------------------------------------------------------------------------


def _read_file(directory: Path, name: str, max_bytes: int) -> bytes:
    """The file's bytes. Opened without following a symlink and checked on the descriptor, so a file swapped
    after the scan is still refused; details carry the file name only."""
    try:
        fd = os.open(directory / name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError as exc:
        raise ParseFailure(Reason.PARSE_ERROR, f"{name}: cannot be opened ({type(exc).__name__})") from None
    with os.fdopen(fd, "rb") as handle:
        info = os.fstat(handle.fileno())
        if not stat.S_ISREG(info.st_mode):
            raise ParseFailure(Reason.PARSE_ERROR, f"{name}: not a regular file")
        too_big = ParseFailure(Reason.PARSE_ERROR, f"{name}: larger than {max_bytes} bytes")
        if info.st_size > max_bytes:
            raise too_big
        data = handle.read(max_bytes + 1)  # the file may have grown since fstat
        if len(data) > max_bytes:
            raise too_big
    return data


def _read_html(name: str, data: bytes, settings: FileSettings) -> dict:
    parsed = parse_page(data, "text/html", settings.url)
    return {
        "title": parsed.title,
        "canonical_url": parsed.canonical_url,
        "text": parsed.text,
        "links": [{"href": href} for href in parsed.links],
        "html": data.decode("utf-8", errors="replace"),
    }


def _read_text(name: str, data: bytes, settings: FileSettings) -> dict:
    if b"\x00" in data:
        raise ParseFailure(Reason.PARSE_ERROR, f"{name}: contains NUL bytes, not text")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ParseFailure(Reason.PARSE_ERROR, f"{name}: not valid UTF-8") from None
    # the ingest stores the HTML of every document and refuses a blank one
    return {"title": None, "canonical_url": settings.url, "text": text, "links": [], "html": f"<pre>{escape(text)}</pre>"}


READERS = {".html": _read_html, ".htm": _read_html, ".txt": _read_text, ".md": _read_text}


def _extension(name: str) -> str:
    return os.path.splitext(name)[1].lower()


def scan(directory: Path) -> list[Entry]:
    """The regular files directly inside `directory`, by name. No recursion, no symlink followed, never guessed.
    `samples.toml` and dotfiles are not samples: they are neither read nor reported."""
    entries = []
    with os.scandir(directory) as found:
        for entry in sorted(found, key=lambda e: e.name):
            if entry.name == MANIFEST or entry.name.startswith("."):  # not samples: the manifest, Finder and editor files
                continue
            if entry.is_symlink():
                entries.append(Entry(entry.name, "symlink"))
            elif entry.is_file(follow_symlinks=False):
                unsupported = _extension(entry.name) not in READERS
                entries.append(Entry(entry.name, "unsupported" if unsupported else None))
    return entries


def read_sample(directory: Path, name: str, settings: FileSettings, max_bytes: int) -> tuple[dict, dict | None]:
    """(page dict for `Ingestor.ingest`, author). The author is only what the manifest says, never the markup.

    Raises `ParseFailure` (`parse_error`, or `empty_text` for HTML without text) naming the file.
    """
    data = _read_file(Path(directory), name, max_bytes)
    try:
        page = READERS[_extension(name)](name, data, settings)
    except ParseFailure as failure:
        raise ParseFailure(failure.reason, f"{name}: {failure.detail}") from None
    page.update(url=settings.url, scrape_meta={"client": CLIENT, "sample_file": name})
    page["title"] = settings.title or page["title"]
    for key in ("lang", "published_at"):
        if getattr(settings, key):
            page[key] = getattr(settings, key)
    return page, settings.author


# --- manifest --------------------------------------------------------------------------------------------------


@lru_cache(maxsize=2)
def _validator(schema_file: str) -> Draft202012Validator:
    schema = json.loads((contracts_dir() / "schemas" / schema_file).read_text(encoding="utf-8"))
    return Draft202012Validator(schema, format_checker=FormatChecker())


def _timestamp(value: object) -> str:
    moment = parse_timestamp(value) if isinstance(value, str) else value
    if not isinstance(moment, datetime) or moment.tzinfo is None:
        raise ValueError("needs a date, a time and an offset")
    return utc_iso(moment)


def _check_web_url(where: str, key: str, value: object) -> None:
    try:
        scheme = urlsplit(value).scheme.lower() if isinstance(value, str) else ""
    except ValueError:
        scheme = ""
    if scheme not in _WEB_SCHEMES:
        raise ManifestError(f"{where}{key}: must be an http or https URL")


def _fail_first(validator: Draft202012Validator, fragment: dict, where: str) -> None:
    """Raise for the first contract violation of `fragment`; a missing required field is not one, it is a fragment."""
    for error in sorted(validator.iter_errors(fragment), key=lambda e: list(e.absolute_path)):
        if error.validator != "required":
            key = ".".join(str(part) for part in error.absolute_path)
            raise ManifestError(f"{where}{key}: {error.validator} failed")


def _validate_layer(values: dict, where: str) -> dict:
    """`values` checked against the contract, one key at a time, and `published_at` in its stored form."""
    values = dict(values)
    if "name" in values and not (isinstance(values["name"], str) and values["name"].strip()):
        raise ManifestError(f"{where}name: must be a non-empty string")
    if "url" in values:
        _check_web_url(where, "url", values["url"])
    author = values.get("author")
    if isinstance(author, dict) and author.get("profile_url") is not None:
        _check_web_url(where, "author.profile_url", author["profile_url"])
    if "published_at" in values:
        try:
            values["published_at"] = _timestamp(values["published_at"])
        except ValueError:
            raise ManifestError(f"{where}published_at: must be an RFC 3339 date-time with an offset") from None
    if "target_modules" in values:
        _fail_first(_validator("source.schema.json"), {"target_modules": values["target_modules"]}, where)
    contract_keys = ("source_kind", "platform", "lang", "author", "title", "url")
    _fail_first(_validator("scraped-document.schema.json"), {k: values[k] for k in contract_keys if k in values}, where)
    return values


def _only_keys(values: dict, allowed: frozenset, where: str) -> None:
    for key in values:
        if key not in allowed:
            raise ManifestError(f"{where}{key}: not a key allowed here")


def _read_manifest(directory: Path) -> dict | None:
    if not os.path.lexists(directory / MANIFEST):
        return None
    try:
        return tomllib.loads(_read_file(directory, MANIFEST, MAX_MANIFEST_BYTES).decode("utf-8"))
    except ParseFailure as failure:
        raise ManifestError(f"{MANIFEST}: {failure.detail}") from None
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise ManifestError(f"{MANIFEST}: not valid TOML ({exc})") from None


def _file_layers(raw: object, directory: Path) -> dict:
    if not isinstance(raw, dict) or not all(isinstance(value, dict) for value in raw.values()):
        raise ManifestError("files: must be a table of tables, one per file name")
    present = {entry.name for entry in scan(directory)}
    layers = {}
    for name, values in raw.items():
        where = f"files.{name}."
        _only_keys(values, _FILE_KEYS, where)
        layers[name] = _validate_layer(values, where)
        if name not in present:
            raise ManifestError(f"files.{name}: no such file in the directory")
    return layers


def load_manifest(directory: Path, *, kind: str | None = None, modules: str | None = None) -> SampleSet:
    """The set's settings from `samples.toml`, with `--kind` and `--modules` as the layer beneath it.

    Every value is checked before anything is read or stored. Without a manifest both flags are required.
    """
    directory = Path(directory)
    manifest = _read_manifest(directory)
    layer: dict = {"platform": DEFAULT_PLATFORM}
    if kind is not None:
        layer["source_kind"] = kind
    if modules is not None:
        layer["target_modules"] = [item.strip() for item in modules.split(",")]
    files: dict = {}
    if manifest is None:
        for flag, key in (("--kind", "source_kind"), ("--modules", "target_modules")):
            if key not in layer:
                raise ManifestError(f"{flag} is required when the directory has no {MANIFEST}")
    else:
        declared = {key: value for key, value in manifest.items() if key != "files"}
        _only_keys(declared, _SET_KEYS, "")
        layer.update(declared)
        files = _file_layers(manifest.get("files", {}), directory)
    for key in ("source_kind", "target_modules"):
        if key not in layer:
            raise ManifestError(f"{key}: set it in {MANIFEST} or with the matching flag")
    layer = _validate_layer(layer, "")

    folder = directory.resolve().name
    slug = re.sub(r"[^a-z0-9-]+", "-", folder.lower()).strip("-") or "samples"
    return SampleSet(
        name=layer.pop("name", folder or slug),
        url=layer.pop("url", f"{SAMPLE_HOST}/{slug}"),
        source_kind=layer["source_kind"],
        platform=layer["platform"],
        target_modules=tuple(layer["target_modules"]),
        slug=slug,
        defaults=layer,
        files=files,
    )


# --- the run ---------------------------------------------------------------------------------------------------

# Matched by URL like `seed.py` and never updated: an operator's edits in the dashboard survive a rerun. `active`
# is false and there is no cron, so neither the scheduler nor the collector (and its URL guard) ever selects it.
_INSERT_SOURCE = """
INSERT INTO sources (id, name, platform, url, source_kind, target_modules, schedule_cron, active)
SELECT gen_random_uuid(), $1, $2, $3, $4, $5, NULL, false
WHERE NOT EXISTS (SELECT 1 FROM sources WHERE url = $3)
"""


@dataclass(frozen=True)
class Summary:
    inserted: int = 0
    duplicate: int = 0
    skipped: int = 0
    failed: int = 0

    def __str__(self) -> str:
        return f"inserted {self.inserted}, duplicate {self.duplicate}, skipped {self.skipped}, failed {self.failed}"


async def ensure_source(pool: asyncpg.Pool, sample_set: SampleSet) -> Source:
    """The set's `sources` row: the existing one with the set's URL, unchanged, else a new inactive one."""
    await pool.execute(
        _INSERT_SOURCE, sample_set.name, sample_set.platform, sample_set.url, sample_set.source_kind,
        list(sample_set.target_modules),
    )
    source_id = await pool.fetchval("SELECT id FROM sources WHERE url = $1 ORDER BY id LIMIT 1", sample_set.url)
    return await PgSourceStore(pool).get(str(source_id))


async def _ingest_file(directory: Path, name: str, sample_set: SampleSet, source: Source, pool, ingestor, max_bytes) -> dict:
    settings = sample_set.settings_for(name)
    # the document takes `source_kind` and `platform` from the Source it is built for: same id, this file's values
    file_source = replace(
        source, source_kind=settings.source_kind, platform=settings.platform, target_modules=settings.target_modules
    )
    try:
        page, author = read_sample(directory, name, settings, max_bytes)
    except ParseFailure as failure:
        await record_error(pool, JobError(failure.reason, failure.detail, source.id))
        return {"outcome": "failed", "reason": failure.reason.value}
    result = await ingestor.ingest(
        page, file_source, fetched_at=datetime.now(UTC), duration_ms=0, proxy=None, author=author
    )
    if result.outcome == "failed":  # the ingestor has recorded it in `job_errors`
        return {"outcome": "failed", "reason": result.error.reason.value}
    if result.outcome == "inserted":
        return {"outcome": "inserted", "document_id": result.document_id}
    return {"outcome": "duplicate"}


async def import_directory(
    directory: Path, sample_set: SampleSet, *, pool: asyncpg.Pool, ingestor: Ingestor, max_bytes: int
) -> Summary:
    """Ingest every supported file of `directory`; one JSON log line per file, then one for the summary.

    A file that fails is recorded and the rest go on. The ids in the per-file lines are what a gold label attaches to.
    """
    directory = Path(directory)
    source = await ensure_source(pool, sample_set)
    counts: Counter = Counter()
    for entry in scan(directory):
        if entry.skipped:
            line = {"outcome": "skipped", "reason": entry.skipped}
        else:
            line = await _ingest_file(directory, entry.name, sample_set, source, pool, ingestor, max_bytes)
        counts[line["outcome"]] += 1
        log.info(json.dumps({"event": "sample_file", "file": entry.name, **line}))
    summary = Summary(**counts)
    log.info(json.dumps({"event": "sample_summary", **vars(summary)}))
    return summary


@asynccontextmanager
async def _ingestor():
    """Pool, storage and Redis from the environment of `app.runtime`; the stores are closed afterwards."""
    pool = await asyncpg.create_pool(os.environ["DATABASE_URL"], min_size=1, max_size=2)
    try:
        storage = Storage(
            os.environ["MINIO_ENDPOINT"],
            os.environ["MINIO_ACCESS_KEY"],
            os.environ["MINIO_SECRET_KEY"],
            bucket=os.environ.get("MINIO_BUCKET", "iw-raw"),
            secure=os.environ.get("MINIO_SECURE", "false").lower() == "true",
        )
        await storage.check_bucket()
        redis = aioredis.from_url(os.environ["REDIS_URL"])
        try:
            yield pool, Ingestor(pool, storage, redis)
        finally:
            await redis.aclose()
    finally:
        await pool.close()


def exit_code(summary: Summary) -> int:
    """Non-zero when any file failed; skipped and duplicate files do not count."""
    return 1 if summary.failed else 0


def _usage_error(event: str, error: str) -> int:
    log.error(json.dumps({"event": event, "error": error}))
    return 2


async def main(argv: list[str]) -> int:
    """Exit code: 0 all fine, 1 when any file failed, 2 on a usage or manifest error (nothing was ingested)."""
    configure_logging()
    parser = argparse.ArgumentParser(prog="python -m iw_scraper.sample_import", description=__doc__.split("\n")[0])
    parser.add_argument("directory", type=Path, help="the directory of saved samples")
    parser.add_argument("--kind", help="source_kind of the set (firm_own, third_party, unknown) when there is no samples.toml")
    parser.add_argument("--modules", help="target modules, comma separated (M1,M2,M3), when there is no samples.toml")
    args = parser.parse_args(argv)
    if not args.directory.is_dir():
        return _usage_error("usage_error", "the directory argument is not a directory")
    try:
        sample_set = load_manifest(args.directory, kind=args.kind, modules=args.modules)
    except ManifestError as exc:
        return _usage_error("manifest_invalid", str(exc))
    _, max_bytes = fetch_settings()
    async with _ingestor() as (pool, ingestor):
        summary = await import_directory(args.directory, sample_set, pool=pool, ingestor=ingestor, max_bytes=max_bytes)
    return exit_code(summary)


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
