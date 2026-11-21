import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

import asyncpg

from iw_scraper.types import JobError


@dataclass(frozen=True)
class IngestResult:
    outcome: Literal["inserted", "duplicate", "failed"]
    document_id: str | None = None
    error: JobError | None = None  # set when outcome is "failed"


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
    return datetime.fromisoformat(value) if value else None


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
            datetime.fromisoformat(doc["fetched_at"]),
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
