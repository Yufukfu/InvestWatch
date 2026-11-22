import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

import asyncpg

from iw_scraper.ingest.document import parse_timestamp
from iw_scraper.types import JobError


@dataclass(frozen=True)
class IngestResult:
    outcome: Literal["inserted", "duplicate", "failed"]
    document_id: str | None = None
    error: JobError | None = None  # set when outcome is "failed"
    previous_document_id: str | None = None  # a web page that already had a version: the one this replaces


@dataclass(frozen=True)
class RemovalState:
    """The newest document of a source and whether a removal job error is newer than it."""

    document_id: str | None
    content_hash: str | None
    created_at: datetime | None
    gone_at: datetime | None

    @property
    def gone_is_newer(self) -> bool:
        # strictly newer: at the same instant the document wins (a removal is only recorded after a document)
        return self.created_at is not None and self.gone_at is not None and self.gone_at > self.created_at


# Named conflict target, as in api/README.md: a bare ON CONFLICT DO NOTHING would also hide a reused `id`.
# It must match the partial unique index `uq_documents_source_hash` (Damian's migration 0001).
_INSERT = """
INSERT INTO documents
  (id, source_id, platform, source_kind, url, canonical_url, fetched_at, published_at, http_status, lang,
   title, text, content_hash, html_object_key, payload)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15::jsonb)
ON CONFLICT (source_id, content_hash) WHERE content_hash IS NOT NULL DO NOTHING
RETURNING id
"""

# nested contract fields live in `documents.payload`; everything else is a column
_PAYLOAD_KEYS = ("author", "links", "media", "screenshots", "blocks", "scrape_meta")


def _timestamp(value: str | None) -> datetime | None:
    return parse_timestamp(value) if value else None


async def is_duplicate(pool: asyncpg.Pool, source_id: str, content_hash: str) -> bool:
    """Cheap pre-check before uploading HTML. Not authoritative: the unique index decides races."""
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "SELECT EXISTS (SELECT 1 FROM documents WHERE source_id = $1 AND content_hash = $2)",
            uuid.UUID(source_id),
            content_hash,
        )


async def insert_document(pool: asyncpg.Pool, doc: dict) -> IngestResult:
    """Insert one validated document; a second copy of the same (source, content) is reported, not an error."""
    payload = {key: doc[key] for key in _PAYLOAD_KEYS if key in doc}
    async with pool.acquire() as conn:
        inserted = await conn.fetchval(
            _INSERT,
            uuid.UUID(doc["id"]),
            uuid.UUID(doc["source_id"]),
            doc["platform"],
            doc["source_kind"],
            doc["url"],
            doc.get("canonical_url"),
            parse_timestamp(doc["fetched_at"]),
            _timestamp(doc.get("published_at")),
            doc.get("http_status"),
            doc.get("lang"),
            doc.get("title"),
            doc["text"],
            doc["content_hash"],
            doc.get("html_object_key"),
            json.dumps(payload, ensure_ascii=False),
        )
    if inserted is None:
        return IngestResult("duplicate")
    return IngestResult("inserted", str(inserted))


async def removal_state(pool: asyncpg.Pool, source_id: str) -> RemovalState:
    """Newest document of the source ("newest" is `created_at DESC, id DESC`) and the newest removal row: an `http_error` `HTTP 404`/`HTTP 410` with a url (what `record_gone` writes, what the api reads)."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT d.id, d.content_hash, d.created_at,
                   (SELECT max(occurred_at) FROM job_errors WHERE source_id = $1 AND reason = 'http_error'
                      AND detail ~ '^HTTP (404|410)$' AND url IS NOT NULL) AS gone_at
            FROM (SELECT 1) AS one
            LEFT JOIN LATERAL (
              SELECT id, content_hash, created_at FROM documents WHERE source_id = $1
              ORDER BY created_at DESC, id DESC LIMIT 1
            ) AS d ON true
            """,
            uuid.UUID(source_id),
        )
    document_id = row["id"]
    return RemovalState(None if document_id is None else str(document_id), row["content_hash"], row["created_at"], row["gone_at"])


async def previous_document(pool: asyncpg.Pool, source_id: str, document_id: str) -> str | None:
    """The newest other row of the source created before `document_id` (ties by id); informational only."""
    async with pool.acquire() as conn:
        found = await conn.fetchval(
            """
            SELECT d.id FROM documents d JOIN documents n ON n.id = $2
            WHERE d.source_id = $1 AND d.id <> n.id AND (d.created_at, d.id) < (n.created_at, n.id)
            ORDER BY d.created_at DESC, d.id DESC LIMIT 1
            """,
            uuid.UUID(source_id),
            uuid.UUID(document_id),
        )
    return None if found is None else str(found)
