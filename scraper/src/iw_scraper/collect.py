"""`run_source`: one attempt to collect one source, joining the guards, robots, fetch, parse and ingest stages.

The collector reports; the queue decides (`jobs.py`). Nothing here retries, sleeps for a backoff or keeps state
between attempts: a failure becomes an `AttemptResult`, and a `Retry-After` is passed on for the queue to honour.
Request starts are spaced by the shared `DomainLimiter`, once before `robots.txt` and once before the page.
"""

import logging
import math
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import partial
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit

from iw_scraper.document import build_document
from iw_scraper.fetch import FetchDeferred, FetchFailure, close_session, fetch, open_session
from iw_scraper.identities import draw_identity
from iw_scraper.jobs import AttemptResult
from iw_scraper.parsing import ParseFailure, parse_page
from iw_scraper.rendering import PageRenderer, wants_render
from iw_scraper.robots import check_robots
from iw_scraper.social.model import FlowContext, build_author, build_page
from iw_scraper.social.registry import registry as social_registry
from iw_scraper.sources import SourceStore, domain_of
from iw_scraper.targets import AddressGuard, UrlGuard, target_guard
from iw_scraper.types import JobError, Reason, Source

DEFAULT_TIMEOUT_SECONDS = 20.0
DEFAULT_MAX_BYTES = 5 * 1024 * 1024
DEFAULT_SOCIAL_MAX_POSTS = 40  # `SOCIAL_MAX_POSTS`: two pages of twenty
_log = logging.getLogger(__name__)
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
        social_max_posts: int = DEFAULT_SOCIAL_MAX_POSTS,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self._store, self._ingestor = store, ingestor
        self._urls_now, self._addresses, self._rotator, self._limiter = urls, addresses, rotator, limiter
        self._stages, self._timeout, self._max_bytes, self._clock = stages, timeout, max_bytes, clock
        self._renderer = renderer  # None while `SCRAPER_RENDER_ENABLED` is off
        self._social_max_posts = social_max_posts

    async def run_source(self, source_id: str, started: Callable[[], Awaitable[None]]) -> AttemptResult:
        source = await self._store.get(source_id)
        if source is None or not source.collectable:  # the queue checks too; this keeps a stray caller from fetching
            return _failed(source_id, Reason.INVALID_REQUEST, "source does not exist or is not collectable")
        registration = None if source.platform == "web" else social_registry.for_url(source.url)
        if registration is not None and not registration.valid_url(source.url):
            return _failed(source_id, Reason.INVALID_REQUEST, "source URL is not a valid channel URL for its host")
        urls = await self._urls_now()
        try:
            urls.check(source.url, enforce_host=False)
        except FetchFailure as failure:
            return _failed(source_id, failure.reason, failure.detail)
        if registration is not None and registration.home_ip:
            try:  # the flow connects on its own, so the address check of the fetch layer runs here once
                await target_guard(urls, self._addresses, source.url)(source.url)
            except FetchFailure as failure:
                return _failed(source_id, failure.reason, failure.detail)
            return await self._run_home_flow(source, registration.flow, started)
        proxy = self._rotator.start_run()
        if (deferral := proxy.deferral()) is not None:  # nothing is announced for a run that has to wait
            return AttemptResult(deferral=deferral)
        await started()  # the guards passed and nothing has been requested yet
        stages = self._stages
        identity = stages.draw_identity()
        session = stages.open_session(identity)
        try:
            return await self._attempt(source_id, self._collect(source, identity, session, urls, proxy, registration))
        finally:
            await stages.close_session(session)

    async def _attempt(self, source_id: str, attempt: Awaitable[AttemptResult]) -> AttemptResult:
        """Await one attempt and map the failures it raises to the `AttemptResult` the queue reads."""
        try:
            return await attempt
        except FetchDeferred as deferred:
            return AttemptResult(deferral=deferred.deferral)
        except FetchFailure as failure:
            return _failed(
                source_id, failure.reason, failure.detail,
                http_status=failure.http_status, retry_after=retry_after_seconds(failure.retry_after, self._clock()),
            )
        except ParseFailure as failure:
            return _failed(source_id, failure.reason, failure.detail)

    async def _run_home_flow(self, source: Source, flow, started: Callable[[], Awaitable[None]]) -> AttemptResult:
        """A flow that runs from the home IP: no identity, session, proxy rotation or robots check (ADR 0109).

        The URL guard has passed; the per-domain limiter is waited once here before the flow's first request.
        """
        await started()
        domain = domain_of(source)
        await self._limiter.wait_turn(domain)
        context = FlowContext(
            source=source, domain=domain, ingest=self._ingestor.ingest, clock=self._clock,
            wait_turn=lambda: self._limiter.wait_turn(domain), max_posts=self._social_max_posts,
        )
        return await self._attempt(source.id, flow(context))

    async def _check_robots(self, source: Source, identity, session, proxy, guard, domain: str) -> AttemptResult | None:
        """One limiter turn, then `robots.txt`: None when the path is allowed, else the `blocked` result."""
        await self._limiter.wait_turn(domain)
        verdict = await self._stages.check_robots(
            source.url, identity, proxy, guard=guard, timeout=self._timeout, session=session
        )
        if not verdict.allowed:  # not a block signal: no identity is blamed
            return _failed(source.id, Reason.BLOCKED, verdict.detail)
        return None

    async def _fetch_page(self, url: str, identity, session, proxy, guard, domain: str, cookie: str | None = None):
        # one cookie `name=value` for this request only: it goes to `fetch` as a cookie, because the run's shared
        # session keeps the headers of the identity it was opened with
        cookies = {cookie.partition("=")[0]: cookie.partition("=")[2]} if cookie else None
        await self._limiter.wait_turn(domain)
        return await self._stages.fetch(
            url, identity, proxy, guard=guard, timeout=self._timeout, max_bytes=self._max_bytes, session=session,
            **({"cookies": cookies} if cookies else {}),
        )

    async def _collect(
        self, source: Source, identity, session, urls: UrlGuard, proxy, registration=None
    ) -> AttemptResult:
        stages = self._stages
        domain = domain_of(source)
        guard = target_guard(urls, self._addresses, source.url)

        if registration is not None and registration.flow is not None:  # a flow on the fetch path asks for robots itself
            return await registration.flow(self._flow_context(source, domain, identity, session, proxy, guard))
        if (refusal := await self._check_robots(source, identity, session, proxy, guard, domain)) is not None:
            return refusal
        if source.platform != "web":
            return await self._collect_social(source, identity, session, proxy, guard, domain)

        began = time.monotonic()
        result = await self._fetch_page(source.url, identity, session, proxy, guard, domain)
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

    def _flow_context(self, source: Source, domain: str, identity, session, proxy, guard) -> FlowContext:
        return FlowContext(
            source=source, domain=domain, ingest=self._ingestor.ingest, clock=self._clock,
            wait_turn=lambda: self._limiter.wait_turn(domain), max_posts=self._social_max_posts,
            identity=identity, session=session, proxy=proxy,
            check_robots=lambda: self._check_robots(source, identity, session, proxy, guard, domain),
            fetch=lambda url, cookie=None: self._fetch_page(url, identity, session, proxy, guard, domain, cookie),
            known_urls=self._store.known_urls,
        )

    async def _collect_social(self, source: Source, identity, session, proxy, guard, domain: str) -> AttemptResult:
        """Read a channel's pages, newest first, through the same fetch path as a web page.

        Paging is stateless: follow the older-posts link until `social_max_posts` posts were seen, there is no
        older link, or a page brought nothing new. A failure on a later page keeps the earlier documents.
        """
        stages = self._stages
        parse = social_registry.for_url(source.url).parse
        url, seen, stored = source.url, 0, 0
        while True:
            await self._limiter.wait_turn(domain)
            began = time.monotonic()
            try:
                result = await stages.fetch(
                    url, identity, proxy, guard=guard, timeout=self._timeout, max_bytes=self._max_bytes, session=session
                )
                final, origin = urlsplit(result.url), urlsplit(source.url)
                if final.hostname != origin.hostname or final.path.lower() != origin.path.lower():
                    # the host redirected to the profile page (no preview) or somewhere else: not this channel's preview
                    raise ParseFailure(Reason.PARSE_ERROR, "no public preview for this channel")
                channel = parse(result.body, result.url)
            except (FetchDeferred, FetchFailure, ParseFailure) as failure:
                if stored == 0:
                    raise
                return self._partial(source.id, failure, stored)
            duration_ms = int((time.monotonic() - began) * 1000)
            fetched_at = self._clock()
            inserted, author = 0, build_author(channel)
            for post in channel.posts:
                outcome = await self._ingestor.ingest(
                    build_page(channel, post, http_status=result.status), source,
                    fetched_at=fetched_at, duration_ms=duration_ms, proxy=result.proxy_id, author=author,
                )
                if outcome.outcome == "failed":  # the ingestor has recorded it in `job_errors`
                    return AttemptResult(documents=stored + inserted, error=outcome.error, recorded=True)
                inserted += outcome.outcome == "inserted"
            stored += inserted
            seen += channel.seen
            _log.info(
                "social page of %s: %d posts with text, %d skipped without text, %d new",
                domain, len(channel.posts), channel.skipped, inserted,
            )
            # nothing new (already stored, or a page of posts without text) ends the run: no older page is requested
            if inserted == 0 or channel.older_url is None or seen >= self._social_max_posts:
                return AttemptResult(documents=stored)
            url = channel.older_url

    def _partial(self, source_id: str, failure: Exception, documents: int) -> AttemptResult:
        """A later page failed: the documents of the earlier pages stay, the failure is reported once."""
        if isinstance(failure, FetchDeferred):
            return AttemptResult(documents=documents, deferral=failure.deferral)
        if isinstance(failure, FetchFailure):
            return _failed(
                source_id, failure.reason, failure.detail, documents=documents, http_status=failure.http_status,
                retry_after=retry_after_seconds(failure.retry_after, self._clock()),
            )
        return _failed(source_id, failure.reason, failure.detail, documents=documents)
