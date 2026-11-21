"""The contract fields of a `ScrapedDocument` that a fetch and a parse produce, as a plain dict.

`id` (UUID v4) and `content_hash` are added when the document is stored (`scraper-ingest`), which also validates the
record against `contracts/schemas/scraped-document.schema.json` before the insert. `source_kind`, `platform` and
`source_id` are copied from the source row and never inferred from the page. `text` is never empty here: `parse_page` raises `empty_text` first, so a caller that goes through the parser cannot
produce an empty document. `scrape_meta.scraper` is `httpx`, the
nearest value of the v1 enum for an HTTP client (ADR 0101); `client` says which one it really is.
"""

from datetime import datetime, timezone

from iw_scraper.fetch import FetchResult
from iw_scraper.parsing import ParsedPage
from iw_scraper.types import Source

SCRAPER = "httpx"
CLIENT = "noble-tls"


def build_document(source: Source, result: FetchResult, page: ParsedPage, fetched_at: datetime) -> dict:
    if fetched_at.tzinfo is None:
        raise ValueError("fetched_at needs a timezone: time is UTC ISO-8601")
    return {
        "source_id": source.id,
        "platform": source.platform,
        "source_kind": source.source_kind,
        "url": result.url,
        "canonical_url": page.canonical_url,
        "fetched_at": fetched_at.astimezone(timezone.utc).isoformat(),
        "http_status": result.status,
        "title": page.title,
        "text": page.text,
        "links": [{"href": href} for href in page.links],
        "scrape_meta": {"scraper": SCRAPER, "client": CLIENT, "proxy": result.proxy_id},  # an identifier, never a URL
    }
