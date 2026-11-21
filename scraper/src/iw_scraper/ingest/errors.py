import json
import logging
import re
import uuid

import asyncpg

from iw_scraper.types import JobError

log = logging.getLogger("iw_scraper.ingest")

# credentials in a URL (scheme://user:pass@host) and in key=value pairs
_URL_USERINFO = re.compile(r"(\w+://)[^/\s@]+@")
_SECRET_PAIR = re.compile(r"(?i)\b(password|passwd|pwd|token|secret|api[_-]?key)=\S+")


def redact(detail: str) -> str:
    """Last line of defence: `detail` should never hold credentials, and if it does they are not stored."""
    return _SECRET_PAIR.sub(r"\1=***", _URL_USERINFO.sub(r"\1***@", detail))


async def record_error(pool: asyncpg.Pool, error: JobError) -> None:
    """Write one `job_errors` row and one JSON log line."""
    detail = redact(error.detail)
    log.warning(json.dumps({"event": "job_error", "reason": error.reason.value, "source_id": error.source_id, "detail": detail}))
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO job_errors (id, source_id, reason, detail) VALUES ($1, $2, $3, $4)",
            uuid.uuid4(),  # ids have no server default (integration-plan §7)
            uuid.UUID(error.source_id) if error.source_id else None,
            error.reason.value,
            detail,
        )
