"""Publisher identity and the `advertiser` of M1/M3 findings (change analytics-m1-m3, design decisions 1 and 12).

The publisher is a registry firm when the author's profile host or a non-social page host is one of its
domains, or the normalized author handle equals a normalized name, core name or alias of the firm.
A firm publisher routes to M2; everything here is about the party that publishes or offers the content.
"""

from __future__ import annotations

import re
import unicodedata
from urllib.parse import urlsplit

from ..models import AdvertiserRef, ScrapedDocument, _absolute_http_url
from ..registry import Firm, Registry, _normalize_domain, http_host

MAX_LEN = 200  # analytics-worker follow-up #8: scraped strings on the finding are cut
#: Platform hosts: a page or profile here is the platform's, never a firm's own domain.
SOCIAL_HOSTS = (
    "instagram.com", "facebook.com", "fb.com", "tiktok.com", "youtube.com", "youtu.be", "x.com",
    "twitter.com", "t.me", "telegram.me", "linkedin.com", "threads.net",
)
_NON_ALNUM = re.compile(r"[\W_]+", re.UNICODE)


def normalize_handle(value: str) -> str:
    """'@Alfa_Inwestycje' -> 'alfainwestycje'; diacritics folded ('ł' -> 'l'), every non-alphanumeric removed."""
    folded = unicodedata.normalize("NFKD", value.lower().replace("ł", "l"))
    folded = "".join(c for c in folded if not unicodedata.combining(c))
    return _NON_ALNUM.sub("", folded)


def is_social(host: str) -> bool:
    host = _normalize_domain(host)
    return any(host == s or host.endswith("." + s) for s in SOCIAL_HOSTS)


def page_host(url: str) -> str:
    """Host of the page URL as written there (original case, so it quotes as a substring of `url`), no www."""
    netloc = urlsplit(url).netloc.rsplit("@", 1)[-1]
    host = netloc.split(":", 1)[0] if not netloc.startswith("[") else netloc.split("]", 1)[0] + "]"
    return host[4:] if host.lower().startswith("www.") else host


def _has_author(doc: ScrapedDocument) -> bool:
    a = doc.author
    return a is not None and any((v or "").strip() for v in (a.name, a.handle, a.profile_url))


def _firm_by_handle(handle: str | None, registry: Registry) -> Firm | None:
    key = normalize_handle(handle or "")
    if not key:
        return None
    for firm in registry.firms:
        if key in {normalize_handle(n) for n in (firm.name, firm.core, *firm.aliases)}:
            return firm
    return None


def publisher_firm(doc: ScrapedDocument, registry: Registry) -> Firm | None:
    """The registry firm that publishes this document itself, or None (design decision 1)."""
    author = doc.author
    if author is not None and author.profile_url:
        host = http_host(author.profile_url)
        if host and not is_social(host) and (firm := registry.firm_on_host(host)) is not None:
            return firm
    host = http_host(doc.url)
    if host and not is_social(host) and (firm := registry.firm_on_host(host)) is not None:
        return firm
    return _firm_by_handle(author.handle if author else None, registry)


def _cut(value: str | None) -> str | None:
    value = (value or "").strip()
    return value[:MAX_LEN] or None


def build_advertiser(doc: ScrapedDocument, registry: Registry) -> AdvertiserRef:
    author = doc.author if _has_author(doc) else None
    host = page_host(doc.url)
    profile = author.profile_url.strip() if author and author.profile_url else None
    if profile:
        try:
            _absolute_http_url(profile)
        except ValueError:
            profile = None  # never fail the finding on a scraped URL the contract would reject
    return AdvertiserRef(
        name=_cut(author.name if author else None) or _cut(author.handle if author else None) or _cut(host),
        handle=_cut(author.handle) if author else None,
        profile_url=profile,
        website=None if author else f"{urlsplit(doc.url).scheme}://{host}/",
        in_registry=publisher_firm(doc, registry) is not None,
        on_warning_list=None,  # S3.7 (KNF public warnings list) is not implemented
    )
