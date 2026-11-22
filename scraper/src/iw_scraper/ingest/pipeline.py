import asyncio
import json
import logging
from dataclasses import replace
from datetime import datetime

import asyncpg
from iw_scraper.ingest.document import build_document
from iw_scraper.ingest.errors import record_error, redact
from iw_scraper.ingest.publisher import STREAM, mark_published, publish
from iw_scraper.ingest.storage import Storage
from iw_scraper.ingest.store import (
    IngestResult,
    RemovalState,
    insert_document,
    is_duplicate,
    previous_document,
    removal_state,
)
from iw_scraper.ingest.validate import check_document
from iw_scraper.rendering import VIEWPORT_ORDER, RenderOutput
from iw_scraper.types import JobError, Reason, Source

log = logging.getLogger("iw_scraper.ingest")

# An insert error after which the row certainly does not exist: the server answered with an error to a statement
# that autocommit then rolled back, or the client refused the arguments before sending anything. Anything else
# (a dropped connection, a timeout, a cancel) may have come after the commit; deleting the object then would leave
# a committed row whose `html_object_key` points at nothing, which is worse than an orphan object.
_UNSURE_POSTGRES_ERRORS = (asyncpg.exceptions.PostgresConnectionError, asyncpg.exceptions.OperatorInterventionError)
_REFUSED_BEFORE_SENDING = (asyncpg.InterfaceError, ValueError, TypeError, KeyError)


def _certainly_not_committed(exc: BaseException) -> bool:
    if isinstance(exc, asyncpg.PostgresError):
        return not isinstance(exc, _UNSURE_POSTGRES_ERRORS)
    return isinstance(exc, _REFUSED_BEFORE_SENDING)


class Ingestor:
    """Parsed page -> validated, deduplicated row + raw HTML in MinIO + event on the stream.

    Order: validate, cheap dedup check, upload HTML, insert (commit), then XADD. A failure before the commit
    leaves no object and no event; a failure after it leaves an unpublished row that the sweep republishes.
    """

    def __init__(self, pool: asyncpg.Pool, storage: Storage, redis, *, stream: str = STREAM):
        self.pool, self.storage, self.redis, self.stream = pool, storage, redis, stream

    async def ingest(
        self,
        page: dict,
        source: Source,
        *,
        fetched_at: datetime,
        duration_ms: int,
        proxy: str | None,
        author: dict | None = None,
    ) -> IngestResult:
        try:
            doc = build_document(page, source, fetched_at=fetched_at, duration_ms=duration_ms, proxy=proxy, author=author)
        except UnicodeError:  # e.g. a lone surrogate in the text: it cannot be hashed or stored
            return await self._fail(JobError(Reason.SCHEMA_INVALID, "text is not valid unicode", source.id))
        invalid = check_document(doc)
        if invalid is not None:
            return await self._fail(invalid)

        source_id = doc["source_id"]
        try:
            if await is_duplicate(self.pool, source_id, doc["content_hash"]):
                await self._log_duplicate(doc)
                return IngestResult("duplicate")
        except Exception as exc:  # nothing is uploaded yet; any failure here is a recorded storage error
            return await self._fail(JobError(Reason.STORAGE_ERROR, f"dedup check failed: {exc}", source_id))

        html = page.get("html")
        if not (html and html.strip()):  # the spec stores the HTML of every page; a parser that drops it must show up, not pass silently
            return await self._fail(JobError(Reason.PARSE_ERROR, "page has no html", source_id))
        # the render runs before the first upload: a cancellation (the attempt timeout) then leaves no object behind
        output = await self._render(page.get("render"), source_id)

        try:
            key = await self.storage.put_html(doc["id"], html)
        except Exception as exc:  # the minio client raises S3Error, urllib3 and OS errors alike
            return await self._fail(JobError(Reason.STORAGE_ERROR, f"upload failed: {exc}", source_id))
        doc["html_object_key"] = key
        keys = [key]
        try:
            await self._attach_render(doc, output, source_id, keys)
        except asyncio.CancelledError:  # no insert has started: nothing can be committed, so every object goes
            for stale in keys:
                await self._remove_object(stale)
            raise

        try:
            result = await insert_document(self.pool, doc)
        except asyncio.CancelledError as exc:  # e.g. the orchestrator's timeout
            await self._discard_objects(keys, exc)
            raise
        except Exception as exc:
            # whatever went wrong after the upload (driver, pool, a value the schema let through) is recorded and
            # never escapes; the objects go only if the row certainly was not committed
            await self._discard_objects(keys, exc)
            return await self._fail(JobError(Reason.STORAGE_ERROR, f"insert failed: {exc}", source_id))

        if result.outcome == "duplicate":
            for stale in keys:  # lost the race: another worker inserted the same page
                await self._remove_object(stale)
            await self._log_duplicate(doc)
            return result

        await self._announce(result.document_id, source_id)
        return await self._with_previous(result, doc)

    async def rescan_state(self, source_id: str) -> RemovalState | None:
        """The newest stored document of the source and whether a removal row is newer; None when the lookup fails."""
        try:
            return await removal_state(self.pool, source_id)
        except Exception as exc:  # informational: a failing lookup is logged and never fails a run
            self._log_lookup_failure(source_id, exc)
            return None

    async def record_gone(self, source: Source, status: int, *, already_recorded: bool = False) -> None:
        """A web page answered 404 or 410 twice: store one `http_error` job error (`HTTP 404`/`HTTP 410`, the shape the api reads) with the source URL, and log it.

        `already_recorded` is a re-scan that found the page still missing after a removal row that is newer than its
        newest document: only the log line is written. Never raises; it observes, it does not fail the run.
        """
        if not already_recorded:
            await self._record(JobError(Reason.HTTP_ERROR, f"HTTP {status}", source.id, url=source.url))
        self._log_outcome("gone", source.id, None)

    async def _with_previous(self, result: IngestResult, doc: dict) -> IngestResult:
        """A web page that already had a version reports it; the first collection says nothing."""
        if doc["platform"] != "web":
            return result
        try:
            previous = await previous_document(self.pool, doc["source_id"], result.document_id)
        except Exception as exc:
            self._log_lookup_failure(doc["source_id"], exc)
            return result
        if previous is None:
            return result
        self._log_outcome("changed", doc["source_id"], result.document_id)
        return replace(result, previous_document_id=previous)

    async def _log_duplicate(self, doc: dict) -> None:
        """Unchanged, reverted or reappeared: a duplicate leaves no trace in the tables, so the log is the evidence."""
        if doc["platform"] != "web":
            return
        state = await self.rescan_state(doc["source_id"])
        if state is None:
            return
        if state.gone_is_newer:
            outcome = "reappeared"
        elif state.content_hash == doc["content_hash"]:
            outcome = "unchanged"
        else:
            outcome = "reverted"
        self._log_outcome(outcome, doc["source_id"], state.document_id)

    @staticmethod
    def _log_outcome(outcome: str, source_id: str, document_id: str | None) -> None:
        log.info(json.dumps({"event": "rescan_outcome", "outcome": outcome, "source_id": source_id, "document_id": document_id}))

    @staticmethod
    def _log_lookup_failure(source_id: str, exc: BaseException) -> None:
        log.warning(json.dumps({"event": "rescan_lookup_failed", "source_id": source_id, "error": redact(f"{type(exc).__name__}: {exc}")}))

    async def _render(self, render, source_id: str) -> RenderOutput | None:
        """Run the collector's render step. Whatever it does, the document goes on without layout."""
        if render is None:
            return None
        try:
            output = await render()
        except Exception as exc:  # the render step reports its own failures; this is a bug in it
            await self._record(JobError(Reason.RENDER_FAILED, f"render step failed: {type(exc).__name__}", source_id))
            return None
        for error in output.errors:  # one per failed render, never a queue retry: these are recorded, not returned
            await self._record(JobError(error.reason, error.detail, source_id))
        return output

    async def _attach_render(self, doc: dict, output: RenderOutput | None, source_id: str, keys: list[str]) -> None:
        """Upload the screenshots and set `screenshots` and `scrape_meta.render`.

        Each uploaded key is appended to `keys` at once, so a cancellation can remove what is already there.
        A failure here costs the layout only: nothing of it is kept, and the error is recorded. A viewport the renderer
        failed to capture is `null` while the others are kept (its error is recorded by `_render`).
        """
        if output is None or (output.errors and not output.screenshots):
            return
        if output.skipped or not output.screenshots:
            doc["scrape_meta"] = {**doc["scrape_meta"], "render": {"skipped": output.skipped or "empty"}}
            return
        uploaded: dict[str, str] = {}
        try:
            for viewport, png in output.screenshots.items():
                uploaded[viewport] = await self.storage.put_screenshot(doc["id"], viewport, png)
                keys.append(uploaded[viewport])
        except Exception as exc:
            await self._record(JobError(Reason.STORAGE_ERROR, f"screenshot upload failed: {exc}", source_id))
            await self._drop(uploaded.values(), keys)
            return
        candidate = {
            **doc,
            "screenshots": {viewport: uploaded.get(viewport) for viewport in VIEWPORT_ORDER},
            **({"blocks": list(output.blocks)} if output.blocks else {}),
            "scrape_meta": {
                **doc["scrape_meta"], "render": {"browser_version": output.browser_version, "truncated": output.truncated}
            },
        }
        if check_document(candidate) is not None:  # the layout is not worth a document the schema refuses
            await self._record(JobError(Reason.RENDER_FAILED, "render output is not valid against the schema", source_id))
            await self._drop(uploaded.values(), keys)
            return
        doc.update(candidate)

    async def _drop(self, shots, keys: list[str]) -> None:
        for key in shots:
            await self._remove_object(key)
            keys.remove(key)

    async def _announce(self, document_id: str, source_id: str) -> None:
        try:
            await publish(self.redis, document_id, self.stream)
        except Exception as exc:  # RedisError, a timeout, or a client bug: the row is stored either way
            await self._record(JobError(Reason.PUBLISH_FAILED, f"publish failed: {exc}", source_id))
            return  # the row stays unpublished; the sweep republishes it
        try:
            await mark_published(self.pool, document_id)
        except Exception as exc:
            # published but unmarked: the sweep may publish it again, which consumers deduplicate
            log.warning(json.dumps({"event": "mark_published_failed", "document_id": document_id, "error": redact(str(exc))}))

    async def _discard_objects(self, keys: list[str], exc: BaseException) -> None:
        if _certainly_not_committed(exc):
            for key in keys:
                await self._remove_object(key)
            return
        log.warning(json.dumps({"event": "possible_orphan", "keys": keys, "error": redact(f"{type(exc).__name__}: {exc}")}))

    async def _remove_object(self, key: str) -> None:
        try:
            await self.storage.remove(key)
        except Exception as exc:
            log.error(json.dumps({"event": "orphan_object", "key": key, "error": redact(str(exc))}))

    async def _fail(self, error: JobError) -> IngestResult:
        # redact once, here: the returned error is what callers log, as well as what the sink stores
        error = JobError(error.reason, redact(error.detail), error.source_id)
        await self._record(error)
        return IngestResult("failed", error=error)

    async def _record(self, error: JobError) -> None:
        try:
            await record_error(self.pool, error)
        except Exception as exc:  # a failing sink must not mask the failure it was recording
            log.error(
                json.dumps({"event": "job_error_not_recorded", "reason": error.reason.value, "error": redact(str(exc))})
            )
