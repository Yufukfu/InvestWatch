"""POST /scans: XADD iw:scan-requests * source_id <uuid> requested_at <iso> (events.schema.json scan_request)."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from redis.exceptions import RedisError
from sqlalchemy import exists, select

from ..db.mapping import format_time
from ..db.tables import sources
from ..errors import ServiceUnavailable
from ..models import ScanRequest

router = APIRouter()
STREAM = "iw:scan-requests"


@router.post("/scans", status_code=202)
async def request_scan(body: ScanRequest, request: Request):
    svc = request.app.state.services
    async with svc.engine.connect() as conn:
        found = (await conn.execute(select(exists().where(sources.c.id == body.source_id)))).scalar_one()
    if not found:
        raise HTTPException(404, f"source {body.source_id} not found")
    fields = {"source_id": str(body.source_id),
              "requested_at": format_time(datetime.now(timezone.utc).replace(microsecond=0))}
    try:
        await svc.redis.xadd(STREAM, fields)
    except (RedisError, OSError):
        raise ServiceUnavailable("redis") from None
    return {"queued": True, "source_id": str(body.source_id)}
