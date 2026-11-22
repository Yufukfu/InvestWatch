import json
import logging
import re
import string
import uuid

import asyncpg

from iw_scraper.types import JobError

log = logging.getLogger("iw_scraper.ingest")

_MAX_DETAIL = 300
# Redaction runs on text that page or proxy content can influence, so its input is bounded first. The bound is
# far above _MAX_DETAIL. A secret cut in half by the bound would lose the marker that identifies it (the "@" or
# the name), so the trailing partial token is dropped with the cut. Every pattern below is at worst quadratic in
# this length.
_MAX_REDACT_INPUT = 2000
_MAX_SOURCE_ID_IN_DETAIL = 80

# credentials as userinfo (`user:pass@host`, with or without a scheme; greedy to the LAST "@" of the token so a
# password containing "@" or "/" is covered), bearer tokens, auth headers (the rest of the line), and
# name=value / "name": "value" pairs whose NAME looks secret. The pair pattern does not mention the secret words:
# it finds `name sep value` and the name is judged in code, which keeps the regex free of nested repetition.
_BARE_USERINFO = re.compile(r"\b[^\s/:@]+:\S*@(?=[\w.\[-])")  # a host, an IP, or `[` of an IPv6 literal
_BEARER = re.compile(r"(?i)\b(bearer|basic)\s+\S+")
_AUTH_HEADER = re.compile(r"(?i)\b(authorization|proxy-authorization|cookie|set-cookie)(\s*:\s*).*")
_PAIR = re.compile(r"([\w-]+[\"']?)(\s*[=:]\s*)(\"[^\"]*\"|'[^']*'|\S+)")
_SECRET_NAME_PARTS = ("password", "passwd", "pwd", "token", "secret", "key", "signature", "session", "sess", "credential", "passphrase", "authorization", "cookie")
# short names are matched as whole `-`/`_` separated words, or `bypass` and `AuthenticationError` would be masked
_SECRET_NAME_WORDS = frozenset({"pass", "pw", "auth"})


def _looks_secret(name: str) -> bool:
    lowered = name.lower()
    return any(part in lowered for part in _SECRET_NAME_PARTS) or not _SECRET_NAME_WORDS.isdisjoint(
        re.split(r"[-_]", lowered)
    )


def _mask_secret_pairs(text: str) -> str:
    """Mask the value of every pair whose name looks secret.

    For a harmless name only `name=` is consumed, so a secret nested in its value (`a=1&password=x`,
    `(source_id=password=x)`) is still found by the next search.
    """
    out: list[str] = []
    pos = 0
    while (match := _PAIR.search(text, pos)) is not None:
        out.append(text[pos : match.start()])
        name, separator = match.group(1), match.group(2)
        if _looks_secret(name):
            out.append(f"{name}{separator}***")
            pos = match.end()
        else:
            out.append(f"{name}{separator}")
            pos = match.start(3)
    out.append(text[pos:])
    return "".join(out)


def redact(detail: str) -> str:
    """Last line of defence: `detail` should never hold credentials, and if it does they are not stored.

    Over-redacting is acceptable here; leaking is not. A space inside an unquoted secret value is not
    recoverable (`password=a b c` keeps ` b c`), which is why callers must not put credentials in a detail.
    The result is capped, because driver messages can be long.
    """
    if len(detail) > _MAX_REDACT_INPUT:
        detail = detail[:_MAX_REDACT_INPUT]
        last_gap = max(detail.rfind(ch) for ch in string.whitespace)
        detail = detail[: max(last_gap, 0)]  # no whitespace at all: nothing can be told apart from a secret
    detail = _BARE_USERINFO.sub("***@", detail)
    detail = _BEARER.sub(r"\1 ***", detail)
    detail = _AUTH_HEADER.sub(r"\1\2***", detail)
    detail = _mask_secret_pairs(detail)
    return detail[:_MAX_DETAIL]


_MIN_KNOWN_SECRET = 4  # a shorter value would mask ordinary words; real cookies and proxy parts are longer


def redact_known(text: str, secrets) -> str:
    """Mask every occurrence of the given secret values (cookies, a proxy URL, its host, user and password).

    `redact` finds secrets by their shape; a bare token or a proxy host has none, so the adapters that hold them
    pass them here. The longest value goes first, so a secret that contains another is masked whole.
    """
    for secret in sorted({s for s in secrets if s and len(s) >= _MIN_KNOWN_SECRET}, key=len, reverse=True):
        text = text.replace(secret, "***")
    return text


def _short_source_id(source_id: str) -> str:
    # redact first, cap after: capping first could cut the "@" that marks a userinfo and leave its password
    return redact(source_id)[:_MAX_SOURCE_ID_IN_DETAIL]


def _source_uuid(source_id: str | None) -> tuple[uuid.UUID | None, str]:
    """A scan request can name any string as a source; keep a non-UUID one in the detail instead of failing.

    The returned prefix goes in FRONT of the detail so the length cap can never push it out.
    """
    if source_id is None:
        return None, ""
    try:
        return uuid.UUID(source_id), ""
    except ValueError:
        return None, f"(source_id={_short_source_id(source_id)}) "


async def record_error(pool: asyncpg.Pool, error: JobError) -> None:
    """Write one `job_errors` row and one JSON log line."""
    source_uuid, prefix = _source_uuid(error.source_id)
    detail = redact(prefix + error.detail)
    logged_id = None if error.source_id is None else _short_source_id(error.source_id)
    log.warning(json.dumps({"event": "job_error", "reason": error.reason.value, "source_id": logged_id, "detail": detail}))
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO job_errors (id, source_id, reason, detail) VALUES ($1, $2, $3, $4)",
            uuid.uuid4(),  # ids have no server default (integration-plan §7)
            source_uuid,
            error.reason.value,
            detail,
        )
