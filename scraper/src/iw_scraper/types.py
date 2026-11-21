"""Shared value types: the interface between the three scraper changes.

`scraper-v1` (fetch and parse), `scraper-ingest` (store and announce) and
`scraper-orchestration` (queue, schedule, scan requests) agree on these only.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class Reason(StrEnum):
    """Closed set of job error reasons (`web-collection` spec)."""

    BLOCKED = "blocked"
    BLOCKED_TARGET = "blocked_target"
    TIMEOUT = "timeout"
    HTTP_ERROR = "http_error"
    PARSE_ERROR = "parse_error"
    EMPTY_TEXT = "empty_text"
    SCHEMA_INVALID = "schema_invalid"
    STORAGE_ERROR = "storage_error"
    PUBLISH_FAILED = "publish_failed"
    INVALID_REQUEST = "invalid_request"
    RENDER_FAILED = "render_failed"


@dataclass(frozen=True)
class JobError:
    """One failed outcome. `detail` never holds credentials."""

    reason: Reason
    detail: str
    source_id: str | None = None

    def __post_init__(self) -> None:
        # a plain string must not slip past the closed set
        if not isinstance(self.reason, Reason):
            raise ValueError(f"reason must be a Reason, got {self.reason!r}")


@dataclass(frozen=True)
class Source:
    """A `sources` row (`contracts/schemas/source.schema.json`)."""

    id: str
    name: str
    platform: str
    url: str
    source_kind: str
    target_modules: tuple[str, ...]
    active: bool
    schedule_cron: str | None = None

    @property
    def collectable(self) -> bool:
        return self.active and self.platform == "web"


@dataclass(frozen=True)
class Deferral:
    """A run reports this instead of fetching; the queue requeues until `until`."""

    until: datetime
