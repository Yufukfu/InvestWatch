import hashlib
import unicodedata
import uuid
from datetime import datetime, timezone

from iw_scraper.types import Source

# the parsed page carries the raw HTML for the object store; it is not part of the ScrapedDocument. The object
# key is set by the pipeline after a real upload, never taken from a page.
_PAGE_ONLY_KEYS = frozenset({"html", "html_object_key"})
# `author` is dropped too: page markup (meta, rel=author, embedded JSON) is writer-controlled, and analytics routes a
# post to M2 on `author.handle` / `author.profile_url` (issue 36). A platform collector that has account data adds its own path.
_UNTRUSTED_PAGE_KEYS = frozenset({"author"})


def normalise_text(text: str) -> str:
    """NFC, every whitespace run collapsed to one space, trimmed. Case is kept: it can carry meaning."""
    return " ".join(unicodedata.normalize("NFC", text).split())


def content_hash(text: str, identity: str | None = None) -> str:
    """sha256 of the normalised text; for a post, of `identity`, a line feed and the text (see `document_identity`)."""
    prefix = f"{identity}\n" if identity else ""
    return hashlib.sha256((prefix + normalise_text(text)).encode("utf-8")).hexdigest()


def document_identity(doc: dict) -> str | None:
    """What a social document is hashed with: its `canonical_url`, else its `url`. None for a web page.

    Social posts live at one permalink each, so identical text at two permalinks is two documents; the canonical
    URL (no share or tracking parameters) keeps a rescrape of one post from becoming a second row.
    """
    if doc.get("platform") == "web":
        return None
    identity = doc.get("canonical_url") or doc.get("url")
    return identity if isinstance(identity, str) else None


def parse_timestamp(value: str) -> datetime:
    """An RFC 3339 `date-time`, as the contract's `format` allows it: a lowercase `t` or `z` is fine, `fromisoformat` is not."""
    return datetime.fromisoformat(value.upper())


def _iso_utc(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _scrape_meta(from_page: object, duration_ms: int, proxy: str | None) -> dict:
    """What the parser put there stays; the fetch facts are added, and `scraper` defaults to `httpx` (ADR 0101)."""
    meta = dict(from_page) if isinstance(from_page, dict) else {}
    meta.update(duration_ms=duration_ms, proxy=proxy)
    meta.setdefault("scraper", "httpx")
    return meta


def build_document(
    page: dict, source: Source, *, fetched_at: datetime, duration_ms: int, proxy: str | None, author: dict | None = None
) -> dict:
    """The full ScrapedDocument for a parsed page. Does not validate: a page missing a field stays missing.

    `proxy` is an identifier, never credentials (contract `scrape_meta.proxy`). `author` is the one trusted path to
    the contract's `author`: collector code passes platform account data here; an `author` on the page is ignored.
    """
    doc = {key: value for key, value in page.items() if key not in _PAGE_ONLY_KEYS | _UNTRUSTED_PAGE_KEYS}
    doc.pop("content_hash", None)  # always derived from the text here, never trusted from the page
    doc.update(
        id=str(uuid.uuid4()),
        source_id=source.id,
        platform=source.platform,
        source_kind=source.source_kind,
        fetched_at=_iso_utc(fetched_at),
        scrape_meta=_scrape_meta(page.get("scrape_meta"), duration_ms, proxy),
    )
    if author is not None:
        doc["author"] = author
    if isinstance(doc.get("text"), str):
        doc["content_hash"] = content_hash(doc["text"], document_identity(doc))
    return doc
