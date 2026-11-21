import json
import logging
from datetime import datetime

import asyncpg
from redis.exceptions import RedisError

from iw_scraper.ingest.document import build_document
from iw_scraper.ingest.errors import record_error
from iw_scraper.ingest.publisher import STREAM, mark_published, publish
from iw_scraper.ingest.storage import Storage
from iw_scraper.ingest.store import IngestResult, insert_document, is_duplicate
from iw_scraper.ingest.validate import check_document
from iw_scraper.types import JobError, Reason, Source

log = logging.getLogger("iw_scraper.ingest")


class Ingestor:
    """Parsed page -> validated, deduplicated row + raw HTML in MinIO + event on the stream.

    Order: validate, cheap dedup check, upload HTML, insert (commit), then XADD. A failure before the commit
    leaves no object and no event; a failure after it leaves an unpublished row that the sweep republishes.
    """

    def __init__(self, pool: asyncpg.Pool, storage: Storage, redis, *, stream: str = STREAM):
        self.pool, self.storage, self.redis, self.stream = pool, storage, redis, stream

    async def ingest(
        self, page: dict, source: Source, *, fetched_at: datetime, duration_ms: int, proxy: str | None
    ) -> IngestResult:
        doc = build_document(page, source, fetched_at=fetched_at, duration_ms=duration_ms, proxy=proxy)
        invalid = check_document(doc)
        if invalid is not None:
            return await self._fail(invalid)

        source_id = doc["source_id"]
        try:
            if await is_duplicate(self.pool, source_id, doc["content_hash"]):
                return IngestResult("duplicate")
        except (asyncpg.PostgresError, OSError) as exc:
            return await self._fail(JobError(Reason.STORAGE_ERROR, f"dedup check failed: {exc}", source_id))

        key = None
        html = page.get("html")
        if html is not None:
            try:
                key = await self.storage.put_html(doc["id"], html)
            except Exception as exc:  # the minio client raises S3Error, urllib3 and OS errors alike
                return await self._fail(JobError(Reason.STORAGE_ERROR, f"upload failed: {exc}", source_id))
            doc["html_object_key"] = key

        try:
            result = await insert_document(self.pool, doc)
        except (asyncpg.PostgresError, OSError) as exc:
            await self._remove_object(key)
            return await self._fail(JobError(Reason.STORAGE_ERROR, f"insert failed: {exc}", source_id))

        if result.outcome == "duplicate":
            await self._remove_object(key)  # lost the race: another worker inserted the same page
            return result

        await self._announce(result.document_id, source_id)
        return result

    async def _announce(self, document_id: str, source_id: str) -> None:
        try:
            await publish(self.redis, document_id, self.stream)
        except (RedisError, OSError) as exc:
            await self._record(JobError(Reason.PUBLISH_FAILED, f"publish failed: {exc}", source_id))
            return  # the row stays unpublished; the sweep republishes it
        try:
            await mark_published(self.pool, document_id)
        except (asyncpg.PostgresError, OSError) as exc:
            # published but unmarked: the sweep may publish it again, which consumers deduplicate
            log.warning(json.dumps({"event": "mark_published_failed", "document_id": document_id, "error": str(exc)}))

    async def _remove_object(self, key: str | None) -> None:
        if key is None:
            return
        try:
            await self.storage.remove(key)
        except Exception as exc:
            log.error(json.dumps({"event": "orphan_object", "key": key, "error": str(exc)}))

    async def _fail(self, error: JobError) -> IngestResult:
        await self._record(error)
        return IngestResult("failed", error=error)

    async def _record(self, error: JobError) -> None:
        try:
            await record_error(self.pool, error)
        except (asyncpg.PostgresError, OSError) as exc:
            log.error(json.dumps({"event": "job_error_not_recorded", "reason": error.reason.value, "error": str(exc)}))
