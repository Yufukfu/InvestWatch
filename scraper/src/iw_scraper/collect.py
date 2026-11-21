"""`run_source`: one attempt to collect one source, joining the guards, robots, fetch, parse and ingest stages.

The collector reports; the queue decides (`jobs.py`). Nothing here retries, sleeps for a backoff or keeps state
between attempts: a failure becomes an `AttemptResult`, and a `Retry-After` is passed on for the queue to honour.
Request starts are spaced by the shared `DomainLimiter`, once before `robots.txt` and once before the page.
"""

import math
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import partial
from email.utils import parsedate_to_datetime

from iw_scraper.document import build_document
from iw_scraper.fetch import FetchDeferred, FetchFailure, close_session, fetch, open_session
from iw_scraper.identities import draw_identity
from iw_scraper.jobs import AttemptResult
from iw_scraper.parsing import ParseFailure, parse_page
from iw_scraper.rendering import PageRenderer, wants_render
from iw_scraper.robots import check_robots
from iw_scraper.sources import SourceStore, domain_of
from iw_scraper.targets import AddressGuard, UrlGuard, target_guard
from iw_scraper.types import JobError, Reason, Source

DEFAULT_TIMEOUT_SECONDS = 20.0
DEFAULT_MAX_BYTES = 5 * 1024 * 1024
_MAX_DIGITS = 15  # more digits than this is beyond any cap; `int()` also refuses 4300+ digits


@dataclass(frozen=True)
class Stages:
    """The collection stages, replaceable so the order and the failure mapping are tested without a network."""

    open_session: Callable = open_session
    close_session: Callable = close_session
    check_robots: Callable = check_robots
    fetch: Callable = fetch
    parse: Callable = parse_page
    draw_identity: Callable = draw_identity


def retry_after_seconds(header: str | None, now: datetime) -> float | None:
    """A `Retry-After` header (delay seconds or an HTTP date) as seconds from `now`; None when unusable."""
    if not header:
        return None
    value = header.strip()
    if value.isascii() and value.isdigit():
        return float(int(value)) if len(value) <= _MAX_DIGITS else None
    try:
        moment = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    seconds = (moment - now).total_seconds()
    return max(0.0, seconds) if math.isfinite(seconds) else None


def _failed(source_id: str, reason: Reason, detail: str, **extra) -> AttemptResult:
    return AttemptResult(error=JobError(reason, detail, source_id), **extra)


class Collector:
    def __init__(
        self,
        store: SourceStore,
        ingestor,
        *,
        urls: Callable[[], Awaitable[UrlGuard]],
        addresses: AddressGuard,
        rotator,
        limiter,
        stages: Stages = Stages(),
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        max_bytes: int = DEFAULT_MAX_BYTES,
        renderer: PageRenderer | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self._store, self._ingestor = store, ingestor
        self._urls_now, self._addresses, self._rotator, self._limiter = urls, addresses, rotator, limiter
        self._stages, self._timeout, self._max_bytes, self._clock = stages, timeout, max_bytes, clock
        self._renderer = renderer  # None while `SCRAPER_RENDER_ENABLED` is off

    async def run_source(self, source_id: str, started: Callable[[], Awaitable[None]]) -> AttemptResult:
        source = await self._store.get(source_id)
        if source is None or not source.collectable:  # the queue checks too; this keeps a stray caller from fetching
            return _failed(source_id, Reason.INVALID_REQUEST, "source does not exist or is not collectable")
        urls = await self._urls_now()
        try:
            urls.check(source.url, enforce_host=False)
        except FetchFailure as failure:
            return _failed(source_id, failure.reason, failure.detail)
        proxy = self._rotator.start_run()
        if (deferral := proxy.deferral()) is not None:  # nothing is announced for a run that has to wait
            return AttemptResult(deferral=deferral)
        await started()  # the guards passed and nothing has been requested yet
        stages = self._stages
        identity = stages.draw_identity()
        session = stages.open_session(identity)
        try:
            return await self._collect(source, identity, session, urls, proxy)
        except FetchDeferred as deferred:
            return AttemptResult(deferral=deferred.deferral)
        except FetchFailure as failure:
            return _failed(
                source_id, failure.reason, failure.detail,
                http_status=failure.http_status, retry_after=retry_after_seconds(failure.retry_after, self._clock()),
            )
        except ParseFailure as failure:
            return _failed(source_id, failure.reason, failure.detail)
        finally:
            await stages.close_session(session)

    async def _collect(self, source: Source, identity, session, urls: UrlGuard, proxy) -> AttemptResult:
        stages = self._stages
        domain = domain_of(source)
        guard = target_guard(urls, self._addresses, source.url)

        await self._limiter.wait_turn(domain)
        verdict = await stages.check_robots(
            source.url, identity, proxy, guard=guard, timeout=self._timeout, session=session
        )
        if not verdict.allowed:  # not a block signal: no identity is blamed
            return _failed(source.id, Reason.BLOCKED, verdict.detail)

        await self._limiter.wait_turn(domain)
        began = time.monotonic()
        result = await stages.fetch(
            source.url, identity, proxy, guard=guard, timeout=self._timeout, max_bytes=self._max_bytes, session=session
        )
        duration_ms = int((time.monotonic() - began) * 1000)

        page = stages.parse(result.body, result.content_type, result.url)
        fetched_at = self._clock()
        document = build_document(source, result, page, fetched_at)
        document["html"] = result.body.decode("utf-8", errors="replace")  # the body is already UTF-8 (`FetchResult`)
        if self._renderer is not None and wants_render(source):  # ingest runs it after the duplicate check
            document["render"] = partial(self._renderer.render, source, source.url, identity, proxy)
        stored = await self._ingestor.ingest(
            document, source, fetched_at=fetched_at, duration_ms=duration_ms, proxy=result.proxy_id
        )
        if stored.outcome == "failed":  # the ingestor has recorded it in `job_errors`
            return AttemptResult(error=stored.error, recorded=True)
        return AttemptResult(documents=1 if stored.outcome == "inserted" else 0)
