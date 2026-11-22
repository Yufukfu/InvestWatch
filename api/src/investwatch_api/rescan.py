"""Re-scan state of a finding's document, derived on read (issue #71, specs/rest-api).

A re-scan that finds new text stores a new `documents` row (new `content_hash`, new id), so the old finding stays
on the old row. Nothing is stored here: the state comes from the newest later fetch of the same page (same
`source_id`, same `canonical_url` or `url`) and, failing that, from a later `job_errors` row saying the page is gone.

A web source is one page, so its gone rows are matched by `source_id` alone: the scraper stores the source URL as
entered (`job_errors.url`), which a redirect makes differ from the document's final URL. Other platforms hold many
pages per source and keep the URL match.

The frozen contract has no field for it on `Finding` (`additionalProperties: false`); the detail route serves it
in the open `document.scrape_meta` object as `scrape_meta.rescan`.
"""

from __future__ import annotations

from sqlalchemy import and_, func, select

from .db.mapping import format_time
from .db.tables import documents, job_errors

GONE_STATUSES = (404, 410)
GONE_DETAIL = r"^HTTP (404|410)$"  # scraper: f"HTTP {status}" on both reasons below
# `gone`: a web page that answered 404/410 twice (scraper ingest/pipeline.py record_gone);
# `http_error`: a single failed fetch, the only signal before the scraper wrote `gone`
GONE_REASONS = ("gone", "http_error")


def _page_key(column_canonical, column_url):
    return func.coalesce(column_canonical, column_url)


async def rescan_state(conn, doc) -> dict:
    """`{"state": "current"|"changed"|"removed", "latest_document_id": str|None, "checked_at": str}` for one document."""
    key = doc["canonical_url"] or doc["url"]
    newer = (await conn.execute(
        select(documents.c.id, documents.c.fetched_at, documents.c.http_status, documents.c.content_hash)
        .where(documents.c.source_id.is_not_distinct_from(doc["source_id"]),
               _page_key(documents.c.canonical_url, documents.c.url) == key,
               documents.c.fetched_at > doc["fetched_at"],
               documents.c.id != doc["id"])
        .order_by(documents.c.fetched_at.desc(), documents.c.created_at.desc(), documents.c.id)
        .limit(1))).mappings().first()

    last_seen = newer["fetched_at"] if newer else doc["fetched_at"]
    if doc["platform"] == "web" and doc["source_id"] is not None:
        same_page = job_errors.c.source_id == doc["source_id"]
    else:  # many pages per source, or no source to match: the error must name this page
        same_page = and_(job_errors.c.source_id.is_not_distinct_from(doc["source_id"]),
                         job_errors.c.url.in_(sorted({key, doc["url"]})))
    gone_at = (await conn.execute(
        select(func.max(job_errors.c.occurred_at))
        .where(same_page,
               job_errors.c.reason.in_(GONE_REASONS),
               job_errors.c.detail.regexp_match(GONE_DETAIL),
               job_errors.c.occurred_at > last_seen))).scalar_one_or_none()

    if gone_at is not None:
        return {"state": "removed", "latest_document_id": None, "checked_at": format_time(gone_at)}
    if newer is None:
        return {"state": "current", "latest_document_id": None, "checked_at": format_time(doc["fetched_at"])}
    if newer["http_status"] in GONE_STATUSES:
        state = "removed"
    elif newer["content_hash"] != doc["content_hash"]:
        state = "changed"
    else:
        state = "current"
    return {"state": state, "latest_document_id": str(newer["id"]), "checked_at": format_time(newer["fetched_at"])}
