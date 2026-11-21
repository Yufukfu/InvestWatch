"""Propose candidate web sources from the links of documents we already stored.

    python -m iw_scraper.discover [--since HOURS] [--limit N] [--dry-run]   (needs DATABASE_URL)

No network call. A candidate is an inactive, manual-only `sources` row a human approves through the sources API;
until then it is neither collected nor part of the URL guard's allow-list. Spec: `source-discovery`.
"""

import argparse
import asyncio
import logging
import os
import re
import sys
import uuid
from collections import Counter, defaultdict
from collections.abc import Collection, Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit, urlunsplit

import asyncpg

from iw_scraper.logs import configure_logging

log = logging.getLogger("iw_scraper.discover")  # not __name__: the module also runs as __main__

FALLBACK_MODULES = ("M1",)  # a document without a source says nothing about modules; discovery is M1's job

# Hosts that are never candidates; a subdomain of a listed host matches.
DENYLIST = frozenset(
    {
        # social platforms (links stay pointers; channels need a platform collector)
        "facebook.com", "instagram.com", "tiktok.com", "x.com", "twitter.com", "t.me", "youtube.com", "youtu.be",
        "linkedin.com", "reddit.com",
        # share endpoints and messengers
        "telegram.me", "wa.me", "whatsapp.com", "pinterest.com", "vk.com", "sharethis.com", "addthis.com",
        # link shorteners
        "bit.ly", "t.co", "tinyurl.com", "goo.gl", "ow.ly", "is.gd", "buff.ly",
        # ads, analytics, tag managers
        "doubleclick.net", "googletagmanager.com", "google-analytics.com", "googleadservices.com",
    }
)
_TRACKING_KEYS = frozenset({"fbclid", "gclid"})
_DEFAULT_PORTS = {"http": 80, "https": 443}
_LABEL = re.compile(r"[a-z0-9]([a-z0-9-]*[a-z0-9])?")
_TLD = re.compile(r"[a-z]{2,}|xn--[a-z0-9-]+")  # no numeric TLD: `0x7f.0x1` and `127.1` are addresses, not names
_MAX_HOST = 188  # the API caps `name` at 200 and ours is "[candidate] " + host
_MAX_URL = 2000


@dataclass(frozen=True)
class Link:
    """One stored outbound link and the `target_modules` of the source of the document that holds it."""

    href: str
    modules: tuple[str, ...]


@dataclass(frozen=True)
class Candidate:
    url: str
    host: str
    modules: tuple[str, ...]
    links: int  # how many stored links point at the host


@dataclass(frozen=True)
class Selection:
    candidates: list[Candidate]
    hosts_considered: int  # new hosts that passed the filters, before the cap
    skipped_by_cap: int


def host_key(host: str) -> str:
    """The form in which hosts are compared: lower case, without a leading `www.`."""
    host = host.lower().rstrip(".")
    return host[4:] if host.startswith("www.") else host


def _is_denied(host: str) -> bool:
    return any(host == denied or host.endswith("." + denied) for denied in DENYLIST)


def _has_forbidden_character(href: str) -> bool:
    return any(ch <= " " or ch == "\x7f" or ch == "\\" for ch in href)


def _is_hostname(host: str) -> bool:
    """A DNS name of at least two labels with a letter-only TLD: not `localhost`, an IP literal or an empty label."""
    labels = host.split(".")
    return (
        len(host) <= _MAX_HOST
        and len(labels) >= 2
        and all(_LABEL.fullmatch(label) for label in labels)
        and _TLD.fullmatch(labels[-1]) is not None
    )


def _is_tracking(parameter: str) -> bool:
    key = parameter.split("=", 1)[0].lower()
    return key.startswith("utm_") or key in _TRACKING_KEYS


def clean_url(href: str) -> str | None:
    """The URL to store for a stored link, or None when the link is not a candidate.

    Mirrors the API's source-URL shape rules, so a candidate is never a row the API would refuse.
    """
    if not href or len(href) > _MAX_URL or _has_forbidden_character(href):
        return None
    try:
        parts = urlsplit(href)
        port = parts.port
    except ValueError:
        return None
    host = (parts.hostname or "").lower().rstrip(".")  # `localhost.` and `facebook.com.` are the same hosts
    if not host.isascii() or parts.scheme not in _DEFAULT_PORTS or not host or "@" in parts.netloc:
        return None
    if port not in (None, _DEFAULT_PORTS[parts.scheme]) or not _is_hostname(host) or _is_denied(host):
        return None
    query = "&".join(p for p in parts.query.split("&") if p and not _is_tracking(p))
    return urlunsplit((parts.scheme, host, parts.path or "/", query, ""))


def select_candidates(links: Iterable[Link], known_hosts: Collection[str], limit: int) -> Selection:
    """One candidate per host that no source uses yet, the most-linked hosts first, at most `limit`."""
    known = {host_key(h) for h in known_hosts}
    url_counts: dict[str, Counter[str]] = defaultdict(Counter)
    modules: dict[str, set[str]] = defaultdict(set)
    for link in links:
        url = clean_url(link.href)
        if url is None:
            continue
        host = host_key(urlsplit(url).hostname or "")
        if host in known:
            continue
        url_counts[host][url] += 1
        modules[host].update(link.modules)

    ranked = sorted(url_counts, key=lambda h: (-sum(url_counts[h].values()), h))
    chosen = [
        Candidate(
            url=min(url_counts[host], key=lambda u: (-url_counts[host][u], u)),
            host=host,
            modules=tuple(sorted(modules[host])) or FALLBACK_MODULES,
            links=sum(url_counts[host].values()),
        )
        for host in ranked[: max(limit, 0)]
    ]
    return Selection(candidates=chosen, hosts_considered=len(ranked), skipped_by_cap=len(ranked) - len(chosen))


CANDIDATE_PREFIX = "[candidate] "
# `payload` is written by collectors we do not own: anything that is not a list of {"href": str} is skipped here.
_LINKS = """
SELECT d.source_id, l.entry ->> 'href' AS href
FROM documents d
CROSS JOIN LATERAL jsonb_array_elements(
    CASE WHEN jsonb_typeof(d.payload -> 'links') = 'array' THEN d.payload -> 'links' ELSE '[]'::jsonb END
) AS l(entry)
WHERE d.fetched_at >= $1 AND jsonb_typeof(l.entry -> 'href') = 'string'
"""
_INSERT = """
INSERT INTO sources (id, name, platform, url, source_kind, target_modules, schedule_cron, active)
SELECT $1, $2, 'web', $3, 'unknown', $4, NULL, false
WHERE NOT EXISTS (SELECT 1 FROM sources WHERE url = $3)
RETURNING id
"""


@dataclass(frozen=True)
class Report:
    links_read: int
    hosts_considered: int
    inserted: int
    skipped_by_cap: int
    candidates: list[Candidate]  # what was chosen (inserted, or only reported by a dry run)


async def insert_candidate(pool: asyncpg.Pool, candidate: Candidate) -> bool:
    """False when a source already has this exact URL; nothing is updated.

    `sources.url` has no unique index (Damian's schema), so two runs at the same moment, or a run racing a dashboard
    POST, can still both insert: run one discovery at a time. A rerun never repeats a host (`discover` skips it).
    """
    row = await pool.fetchrow(
        _INSERT, uuid.uuid4(), CANDIDATE_PREFIX + candidate.host, candidate.url, list(candidate.modules)
    )
    return row is not None


async def discover(
    pool: asyncpg.Pool, *, since_hours: float, limit: int, dry_run: bool = False, now: datetime | None = None
) -> Report:
    """Read the links of recent documents, choose the new hosts and insert them as inactive candidates."""
    since = (now or datetime.now(UTC)) - timedelta(hours=since_hours)
    source_rows = await pool.fetch("SELECT id, url, target_modules FROM sources")
    modules_of = {row["id"]: tuple(row["target_modules"]) for row in source_rows}
    known_hosts = [host for row in source_rows if (host := urlsplit(row["url"]).hostname)]  # `host_key` folds the rest

    links = [Link(href=row["href"], modules=modules_of.get(row["source_id"], ())) for row in await pool.fetch(_LINKS, since)]
    selection = select_candidates(links, known_hosts, limit)
    inserted = 0
    if not dry_run:
        for candidate in selection.candidates:
            inserted += await insert_candidate(pool, candidate)
    return Report(len(links), selection.hosts_considered, inserted, selection.skipped_by_cap, selection.candidates)


def _non_negative_int(text: str) -> int:
    value = int(text)
    if value < 0:
        raise argparse.ArgumentTypeError("must be 0 or more")
    return value


def _positive_float(text: str) -> float:
    value = float(text)
    if value <= 0:
        raise argparse.ArgumentTypeError("must be more than 0")
    return value


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m iw_scraper.discover", description=__doc__.split("\n")[0])
    parser.add_argument("--since", type=_positive_float, default=168.0, help="read documents fetched in the last HOURS (168)")
    parser.add_argument("--limit", type=_non_negative_int, default=20, help="insert at most N candidates (20)")
    parser.add_argument("--dry-run", action="store_true", help="log the candidates and write nothing")
    return parser.parse_args(argv)


async def main(argv: list[str], environ: Mapping[str, str]) -> int:
    """Run one discovery; the exit code is 0, or 1 when the database cannot be used. Reports through the JSON log."""
    args = parse_args(argv)
    configure_logging()
    dsn = environ.get("DATABASE_URL")
    if not dsn:
        log.error("DATABASE_URL is not set")
        return 1
    try:
        pool = await asyncpg.create_pool(dsn, min_size=1, max_size=1)
    except (OSError, asyncpg.PostgresError) as exc:
        log.error("cannot connect to the database: %s: %s", type(exc).__name__, exc)  # the formatter redacts secrets
        return 1
    try:
        report = await discover(pool, since_hours=args.since, limit=args.limit, dry_run=args.dry_run)
    except asyncpg.PostgresError as exc:
        log.error("discovery failed: %s: %s", type(exc).__name__, exc)
        return 1
    finally:
        await pool.close()
    for candidate in report.candidates:
        log.info("candidate url=%s links=%d modules=%s", candidate.url, candidate.links, ",".join(candidate.modules))
    log.info(
        "discovery done links_read=%d hosts_considered=%d inserted=%d skipped_by_cap=%d dry_run=%s",
        report.links_read, report.hosts_considered, report.inserted, report.skipped_by_cap, args.dry_run,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main(sys.argv[1:], os.environ)))
