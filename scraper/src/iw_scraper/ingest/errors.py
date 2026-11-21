import json
import logging
import re
import uuid

import asyncpg

from iw_scraper.types import JobError

log = logging.getLogger("iw_scraper.ingest")

_MAX_DETAIL = 300

# credentials in a URL (scheme://user:pass@host, greedy to the LAST "@" of the token so a password containing
# "@" or "/" is covered), scheme-less user:pass@host, key=value / "key": "value" pairs whose name looks secret,
# and auth headers (the whole rest of the line)
_URL_USERINFO = re.compile(r"(\w+://)\S*@")
_BARE_USERINFO = re.compile(r"\b[^\s/:@]+:[^\s/@]+@(?=[\w.-]+)")
_SECRET_PAIR = re.compile(
    r"(?i)([\w-]*(?:password|passwd|pwd|token|secret|key|signature|session)[\w-]*[\"']?)"
    r"(\s*[=:]\s*)(?:\"[^\"]*\"|'[^']*'|\S+)"
)
_AUTH_HEADER = re.compile(r"(?i)\b(authorization|proxy-authorization|cookie|set-cookie)(\s*:\s*).*")


def redact(detail: str) -> str:
    """Last line of defence: `detail` should never hold credentials, and if it does they are not stored.

    Over-redacting is acceptable here; leaking is not. The detail is also capped, because driver messages can
    be long.
    """
    detail = _URL_USERINFO.sub(r"\1***@", detail)
    detail = _BARE_USERINFO.sub("***@", detail)
    detail = _AUTH_HEADER.sub(r"\1\2***", detail)
    detail = _SECRET_PAIR.sub(r"\1\2***", detail)
    return detail[:_MAX_DETAIL]


def _source_uuid(source_id: str | None) -> tuple[uuid.UUID | None, str]:
    """A scan request can name any string as a source; keep a non-UUID one in the detail instead of failing."""
    if source_id is None:
        return None, ""
    try:
        return uuid.UUID(source_id), ""
    except ValueError:
        return None, f" (source_id={source_id})"


async def record_error(pool: asyncpg.Pool, error: JobError) -> None:
    """Write one `job_errors` row and one JSON log line."""
    source_uuid, suffix = _source_uuid(error.source_id)
    detail = redact(error.detail + suffix)
    log.warning(
        json.dumps({"event": "job_error", "reason": error.reason.value, "source_id": error.source_id, "detail": detail})
    )
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO job_errors (id, source_id, reason, detail) VALUES ($1, $2, $3, $4)",
            uuid.uuid4(),  # ids have no server default (integration-plan §7)
            source_uuid,
            error.reason.value,
            detail,
        )
