import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

import asyncpg


@dataclass(frozen=True)
class IngestResult:
    outcome: Literal["inserted", "duplicate"]
    document_id: str | None = None


# The conflict target must match the partial unique index from the migration request exactly.
_INSERT = """
INSERT INTO documents
  (id, source_id, platform, source_kind, url, fetched_at, content_hash, html_object_key, payload)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::jsonb)
ON CONFLICT (source_id, content_hash) WHERE source_id IS NOT NULL AND content_hash IS NOT NULL DO NOTHING
RETURNING id
"""


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
    async with pool.acquire() as conn:
        inserted = await conn.fetchval(
            _INSERT,
            uuid.UUID(doc["id"]),
            uuid.UUID(doc["source_id"]),
            doc["platform"],
            doc["source_kind"],
            doc["url"],
            datetime.fromisoformat(doc["fetched_at"]),
            doc["content_hash"],
            doc.get("html_object_key"),
            json.dumps(doc, ensure_ascii=False),
        )
    if inserted is None:
        return IngestResult("duplicate")
    return IngestResult("inserted", str(inserted))
