"""Contract objects (contracts/schemas v1) <-> table rows.

A null scalar and an absent key are the same thing in a column, so `*_to_contract` leaves out optional keys
whose value is null. The `*_to_contract` functions take dict-like rows (`result.mappings()`), not plain `Row`s.
`risk_level` (findings) and `documents_count` (sources) are never stored: the API
derives them on read.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

DOCUMENT_COLUMNS = ("id", "source_id", "platform", "source_kind", "url", "canonical_url", "fetched_at",
                    "published_at", "http_status", "lang", "title", "text", "content_hash", "html_object_key")
DOCUMENT_PAYLOAD = ("author", "links", "media", "screenshots", "blocks", "scrape_meta")
FINDING_COLUMNS = ("id", "document_id", "module", "score", "status", "title", "summary", "firm", "advertiser",
                   "rules", "content_excerpt", "url", "platform", "note", "detected_at", "updated_at", "model")
SOURCE_COLUMNS = ("id", "name", "platform", "url", "source_kind", "target_modules", "schedule_cron", "active",
                  "last_run_at", "last_run_status")
DERIVED = {"findings": ("risk_level",), "sources": ("documents_count",)}

_UUIDS = {"id", "source_id", "document_id"}
_TIMES = {"fetched_at", "published_at", "detected_at", "updated_at", "last_run_at"}


def parse_time(value: str) -> datetime:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def format_time(value: datetime) -> str:
    """UTC ISO-8601 with a Z suffix (integration-plan §7); microseconds only when present."""
    value = value.astimezone(timezone.utc)
    spec = "microseconds" if value.microsecond else "seconds"
    return value.replace(tzinfo=None).isoformat(timespec=spec) + "Z"


def _to_row(obj: dict, columns: tuple[str, ...]) -> dict:
    row = {}
    for key in columns:
        if key not in obj:
            continue
        value = obj[key]
        if value is not None and key in _UUIDS:
            value = uuid.UUID(value)
        elif value is not None and key in _TIMES:
            value = parse_time(value)
        row[key] = value
    return row


def _to_contract(row, columns: tuple[str, ...]) -> dict:
    out = {}
    for key in columns:
        value = row[key]
        if value is None:
            continue
        if isinstance(value, uuid.UUID):
            value = str(value)
        elif isinstance(value, datetime):
            value = format_time(value)
        out[key] = value
    return out


def document_to_row(doc: dict) -> dict:
    row = _to_row(doc, DOCUMENT_COLUMNS)
    row["payload"] = {k: doc[k] for k in DOCUMENT_PAYLOAD if k in doc}
    return row


def document_to_contract(row) -> dict:
    out = _to_contract(row, DOCUMENT_COLUMNS)
    for key, value in (row["payload"] or {}).items():
        if key in DOCUMENT_PAYLOAD:
            out[key] = value
    return out


def finding_to_row(finding: dict) -> dict:
    return _to_row(finding, FINDING_COLUMNS)


def finding_to_contract(row) -> dict:
    return _to_contract(row, FINDING_COLUMNS)


def source_to_row(source: dict) -> dict:
    return _to_row(source, SOURCE_COLUMNS)


def source_to_contract(row) -> dict:
    return _to_contract(row, SOURCE_COLUMNS)
