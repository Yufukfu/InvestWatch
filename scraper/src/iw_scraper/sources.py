"""The `sources` table as the orchestration layer sees it (the PostgreSQL implementation comes with `run_source`)."""

from collections.abc import Sequence
from datetime import datetime
from typing import Protocol
from urllib.parse import urlsplit

from iw_scraper.types import Source


class SourceStore(Protocol):
    async def get(self, source_id: str) -> Source | None: ...

    async def mark_running(self, source_id: str) -> None:
        """`last_run_status = 'running'`."""

    async def mark_finished(self, source_id: str, *, at: datetime, status: str) -> None:
        """`last_run_at` and `last_run_status` of the job that just ended."""

    async def schedulable(self) -> Sequence[Source]:
        """Every source the scheduler may look at (it filters on `collectable` and `schedule_cron`)."""

    async def known_urls(self, urls: Sequence[str]) -> set[str]:
        """The given permalinks that already have a stored document, whatever its source or transcript outcome."""


def domain_of(source: Source) -> str:
    """The key of the per-domain controls: the lowercase host without a trailing dot, empty if the URL has none."""
    return (urlsplit(source.url).hostname or "").rstrip(".")
