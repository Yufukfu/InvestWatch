"""Propose candidate web sources from the links of documents we already stored.

    python -m iw_scraper.discover [--since HOURS] [--limit N] [--dry-run]   (needs DATABASE_URL)

No network call. A candidate is an inactive, manual-only `sources` row a human approves through the sources API;
until then it is neither collected nor part of the URL guard's allow-list. Spec: `source-discovery`.
"""

import ipaddress
from collections import Counter, defaultdict
from collections.abc import Collection, Iterable
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit

FALLBACK_MODULES = ("M1",)  # a document without a source says nothing about modules; discovery is M1's job

# Hosts that are never candidates; a subdomain of a listed host matches.
DENYLIST = frozenset(
    {
        # social platforms (links stay pointers; channels need a platform collector)
        "facebook.com", "instagram.com", "tiktok.com", "x.com", "twitter.com", "t.me", "youtube.com", "youtu.be",
        "linkedin.com", "reddit.com",
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
    host = (parts.hostname or "").lower()
    if parts.scheme not in _DEFAULT_PORTS or not host or "@" in parts.netloc:
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
