import json
from datetime import UTC, datetime
from typing import Literal

from arq.connections import ArqRedis

EVENTS_CHANNEL = "iw:events"


def derive_status(*, documents: int, errors: int) -> str:
    """`ok` with no job error, `failed` with no document and an error, otherwise `partial`."""
    if errors == 0:
        return "ok"
    return "failed" if documents == 0 else "partial"


def utc_iso(moment: datetime) -> str:
    return moment.astimezone(UTC).isoformat().replace("+00:00", "Z")


async def publish_scan_event(
    redis: ArqRedis, kind: Literal["started", "finished"], source_id: str, *, documents: int = 0, status: str = "ok"
) -> None:
    """`scan.started` / `scan.finished` as an `event` envelope on Pub/Sub `iw:events`."""
    data: dict = {"source_id": source_id}
    if kind == "finished":
        data.update(documents=documents, status=status)
    envelope = {"type": f"scan.{kind}", "emitted_at": utc_iso(datetime.now(UTC)), "data": data}
    await redis.publish(EVENTS_CHANNEL, json.dumps(envelope))
