"""Propose candidate web sources from the links of documents we already stored.

    python -m iw_scraper.discover [--since HOURS] [--limit N] [--dry-run]   (needs DATABASE_URL)

No network call. A candidate is an inactive, manual-only `sources` row a human approves through the sources API;
until then it is neither collected nor part of the URL guard's allow-list. Spec: `source-discovery`.
"""

import ipaddress
import json
import uuid
from collections import Counter, defaultdict
from collections.abc import Collection, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit, urlunsplit

import asyncpg

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
    host = host.lower()
    return host[4:] if host.startswith("www.") else host


def _is_denied(host: str) -> bool:
    return any(host == denied or host.endswith("." + denied) for denied in DENYLIST)


def _has_forbidden_character(href: str) -> bool:
    return any(ch <= " " or ch == "\x7f" or ch == "\\" for ch in href)


def _is_literal_or_dotless(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        pass
    labels = host.split(".")
    return len(labels) < 2 or labels[-1].isdigit()  # `localhost`, `intranet`, `127.1`


def _is_tracking(parameter: str) -> bool:
    key = parameter.split("=", 1)[0].lower()
    return key.startswith("utm_") or key in _TRACKING_KEYS


def clean_url(href: str) -> str | None:
    """The URL to store for a stored link, or None when the link is not a candidate.

    Mirrors the API's source-URL shape rules, so a candidate is never a row the API would refuse.
    """
    if not href or _has_forbidden_character(href):
        return None
    try:
        parts = urlsplit(href)
        port = parts.port
    except ValueError:
        return None
    host = (parts.hostname or "").lower().rstrip(".")  # `localhost.` and `facebook.com.` are the same hosts
    if not host.isascii() or ".." in host or parts.scheme not in _DEFAULT_PORTS or not host or "@" in parts.netloc:
        return None
    if port not in (None, _DEFAULT_PORTS[parts.scheme]) or _is_literal_or_dotless(host) or _is_denied(host):
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
SELECT d.source_id, l.entry
FROM documents d
CROSS JOIN LATERAL jsonb_array_elements(
    CASE WHEN jsonb_typeof(d.payload -> 'links') = 'array' THEN d.payload -> 'links' ELSE '[]'::jsonb END
) AS l(entry)
WHERE d.fetched_at >= $1
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


def _href(entry: str) -> str | None:
    value = json.loads(entry)
    href = value.get("href") if isinstance(value, dict) else None
    return href if isinstance(href, str) else None


async def insert_candidate(pool: asyncpg.Pool, candidate: Candidate) -> bool:
    """False when a source already has this exact URL (a race with the dashboard); nothing is updated."""
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
    known_hosts = [host for row in source_rows if (host := urlsplit(row["url"]).hostname)]

    links = [
        Link(href=href, modules=modules_of.get(row["source_id"], ()))
        for row in await pool.fetch(_LINKS, since)
        if (href := _href(row["entry"])) is not None
    ]
    selection = select_candidates(links, known_hosts, limit)
    inserted = 0
    if not dry_run:
        for candidate in selection.candidates:
            inserted += await insert_candidate(pool, candidate)
    return Report(len(links), selection.hosts_considered, inserted, selection.skipped_by_cap, selection.candidates)
