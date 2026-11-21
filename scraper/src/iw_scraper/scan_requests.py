"""Manual scans: the `iw:scan-requests` consumer only enqueues, the job does the work."""

import logging
import os
import socket
import uuid

from arq.connections import ArqRedis
from redis.exceptions import ResponseError

from iw_scraper.events import publish_scan_event
from iw_scraper.sources import SourceStore, domain_of
from iw_scraper.types import JobError, Reason

STREAM = "iw:scan-requests"
GROUP = "iw-scraper"
BATCH = 50
NO_MORE_PENDING = {"0-0", b"0-0"}

logger = logging.getLogger(__name__)


def consumer_name() -> str:
    """Stable per worker: a restart finds its own pending messages again."""
    return os.environ.get("SCRAPER_CONSUMER") or socket.gethostname()


def _text(value) -> str:
    # undecodable bytes become U+FFFD, which no valid source_id contains: the request is malformed, not a crash
    return value.decode(errors="replace") if isinstance(value, bytes) else value


def _valid_uuid(value: str | None) -> bool:
    try:
        return value is not None and str(uuid.UUID(value)) == value
    except ValueError:
        return False


class ScanRequestConsumer:
    def __init__(
        self, redis: ArqRedis, store: SourceStore, record_error, *, consumer: str, claim_idle: float = 60.0
    ) -> None:
        self._redis = redis
        self._store = store
        self._record_error = record_error
        self._consumer = consumer
        self._claim_idle_ms = int(claim_idle * 1000)

    async def setup(self) -> None:
        """Create the consumer group (from the start of the stream, so early requests are not lost)."""
        try:
            await self._redis.xgroup_create(STREAM, GROUP, id="0", mkstream=True)
        except ResponseError as error:
            if "BUSYGROUP" not in str(error):
                raise

    async def poll(self, block: float = 1.0) -> int:
        """Handle messages other consumers left pending too long, then new ones; returns how many."""
        messages = await self._claim_stale()
        fresh = await self._redis.xreadgroup(
            GROUP, self._consumer, {STREAM: ">"}, count=BATCH, block=int(block * 1000)
        )
        for _stream, batch in fresh or []:
            messages.extend(batch)
        for message_id, fields in messages:
            await self.handle(_text(message_id), fields)
        return len(messages)

    async def _claim_stale(self) -> list:
        claimed, cursor = [], "0-0"
        while True:
            cursor, batch, *_ = await self._redis.xautoclaim(
                STREAM, GROUP, self._consumer, min_idle_time=self._claim_idle_ms, start_id=cursor, count=BATCH
            )
            claimed.extend(batch)
            if cursor in NO_MORE_PENDING:
                return claimed

    async def handle(self, message_id: str, fields: dict) -> None:
        """Enqueue or refuse one request, then acknowledge it."""
        source_id = {_text(k): _text(v) for k, v in fields.items()}.get("source_id")
        if not _valid_uuid(source_id):
            await self._record_error(JobError(Reason.INVALID_REQUEST, "scan request without a valid source_id", None))
        else:
            source = await self._store.get(source_id)
            if source is None or not source.collectable:
                await self._record_error(
                    JobError(Reason.INVALID_REQUEST, "scan request for a source that cannot be scanned", source_id)
                )
                await publish_scan_event(self._redis, "finished", source_id, documents=0, status="failed")
            else:
                # the message id makes a redelivered request enqueue the same job id, which arq rejects
                await self._redis.enqueue_job(
                    "execute_job", source_id, domain_of(source), True, _job_id=f"scan-{message_id}"
                )
        await self._redis.xack(STREAM, GROUP, message_id)
