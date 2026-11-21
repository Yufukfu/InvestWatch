import hashlib
import unicodedata
import uuid
from datetime import datetime, timezone

from iw_scraper.types import Source

# the parsed page carries the raw HTML for the object store; it is not part of the ScrapedDocument
_PAGE_ONLY_KEYS = frozenset({"html"})


def normalise_text(text: str) -> str:
    """NFC, every whitespace run collapsed to one space, trimmed. Case is kept: it can carry meaning."""
    return " ".join(unicodedata.normalize("NFC", text).split())


def content_hash(text: str) -> str:
    return hashlib.sha256(normalise_text(text).encode("utf-8")).hexdigest()


def _iso_utc(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_document(page: dict, source: Source, *, fetched_at: datetime, duration_ms: int, proxy: str | None) -> dict:
    """The full ScrapedDocument for a parsed page. Does not validate: a page missing a field stays missing.

    `proxy` is an identifier, never credentials (contract `scrape_meta.proxy`).
    """
    doc = {key: value for key, value in page.items() if key not in _PAGE_ONLY_KEYS}
    doc.update(
        id=str(uuid.uuid4()),
        source_id=source.id,
        platform=source.platform,
        source_kind=source.source_kind,
        fetched_at=_iso_utc(fetched_at),
        scrape_meta={"scraper": "httpx", "duration_ms": duration_ms, "proxy": proxy},
    )
    if isinstance(doc.get("text"), str):
        doc["content_hash"] = content_hash(doc["text"])
    return doc
