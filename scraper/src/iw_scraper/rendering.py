"""The render step: one renderer call per viewport, under the same shared state as a fetch.

`PageRenderer.render` returns what the document gets (screenshots, later blocks), or why it gets nothing: a skip
(`budget`, `paused`) or the job errors of a failed render. It never raises for a render failure: the document is
ingested from the static parse either way (spec `page-rendering`, ADR 0107).
"""

import asyncio
import base64
import binascii
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone

import aiohttp

from iw_scraper.identities import mobile_variant
from iw_scraper.sources import domain_of
from iw_scraper.types import Deferral, JobError, Reason, Source

VIEWPORT_ORDER = ("desktop", "mobile", "tablet")
BUDGET_KEY = "iw:scraper:render:"
BUDGET_KEY_TTL_SECONDS = 2 * 3600  # an hour's counter outlives its hour, so a late increment never meets a new key
MAX_REPLY_BYTES = 16 * 1024 * 1024  # an 8 MB PNG in base64, with room
DEADLINE_SLACK_SECONDS = 5.0  # the HTTP timeout runs a little past the renderer's own deadline, which answers first
_ERROR_REASONS = {"blocked": Reason.BLOCKED, "refused": Reason.BLOCKED_TARGET}


def wants_render(source: Source) -> bool:
    """Only the firm's own pages for M2: its visual rules (R4-R8, R13) are the ones that need layout."""
    return source.collectable and source.source_kind == "firm_own" and "M2" in source.target_modules


class RenderCallError(Exception):
    """A renderer call that did not return a picture. `kind` is the renderer's own (`blocked`, `refused`, `failed`,
    `invalid_request`) or `unreachable`; `detail` is safe to store."""

    def __init__(self, kind: str, detail: str, retry_after: str | None = None) -> None:
        super().__init__(detail)
        self.kind, self.detail, self.retry_after = kind, detail, retry_after


@dataclass(frozen=True)
class RenderReply:
    png: bytes
    browser_version: str
    truncated: bool
    blocks: tuple[dict, ...] = ()


@dataclass(frozen=True)
class RenderOutput:
    screenshots: dict[str, bytes] = field(default_factory=dict)
    browser_version: str | None = None
    truncated: bool = False
    skipped: str | None = None  # `budget` or `paused`: nothing was rendered, and that is not an error
    errors: tuple[JobError, ...] = ()
    blocks: tuple[dict, ...] = ()  # every viewport's, in call order

    def __repr__(self) -> str:  # never the picture bytes
        return f"RenderOutput(viewports={list(self.screenshots)}, skipped={self.skipped}, errors={len(self.errors)})"


class RenderBudget:
    """At most `per_hour` renders per UTC hour across all workers: one Redis counter per hour."""

    def __init__(self, redis, per_hour: int, clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc)) -> None:
        self._redis, self._per_hour, self._clock = redis, per_hour, clock

    async def take(self) -> bool:
        key = f"{BUDGET_KEY}{self._clock():%Y%m%d%H}"
        await self._redis.set(key, 0, ex=BUDGET_KEY_TTL_SECONDS, nx=True)
        return await self._redis.incr(key) <= self._per_hour


class DomainPause:
    """The two shared pauses on a domain: the queue's failure cooldown and the `Retry-After` gate."""

    def __init__(self, gate, health_for: Callable) -> None:
        self._gate, self._health_for = gate, health_for

    async def active(self, domain: str) -> bool:
        if await self._gate.check(domain) is not None:
            return True
        return await self._health_for(domain).paused_for() > 0

    async def defer(self, domain: str, header: str | None) -> None:
        await self._gate.defer_for_retry_after(domain, header)


def http_renderer(base_url: str) -> Callable[[dict, float], Awaitable[RenderReply]]:
    """The call to the renderer service over HTTP. Any transport trouble is `RenderCallError("unreachable")`."""

    async def call(payload: dict, timeout: float) -> RenderReply:
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout + DEADLINE_SLACK_SECONDS)) as http:
                async with http.post(f"{base_url}/render", json=payload) as response:
                    if (response.content_length or 0) > MAX_REPLY_BYTES:
                        raise RenderCallError("failed", "renderer reply is too large")
                    status, data = response.status, await response.json(content_type=None)
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError):
            raise RenderCallError("unreachable", "renderer did not answer") from None
        return _reply(status, data)

    return call


def _reply(status: int, data: object) -> RenderReply:
    if status == 200:
        try:
            blocks = data.get("blocks", [])
            if not isinstance(blocks, list) or not all(isinstance(block, dict) for block in blocks):
                raise TypeError("blocks")
            png = base64.b64decode(data["png_base64"], validate=True)
            return RenderReply(png, str(data["browser_version"]), bool(data["truncated"]), tuple(blocks))
        except (KeyError, TypeError, binascii.Error):
            raise RenderCallError("failed", "renderer reply is malformed") from None
    error = data.get("error") if isinstance(data, dict) else None
    if not isinstance(error, dict):
        raise RenderCallError("failed", f"renderer answered HTTP {status}")
    kind = error.get("kind") if isinstance(error.get("kind"), str) else "failed"
    detail = error.get("detail") if isinstance(error.get("detail"), str) else f"renderer answered HTTP {status}"
    retry_after = error.get("retry_after") if isinstance(error.get("retry_after"), str) else None
    raise RenderCallError(kind, detail[:300], retry_after)


class PageRenderer:
    def __init__(
        self, call, limiter, pause, budget, *, timeout_seconds: float, ports: tuple[int, ...],
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._call, self._limiter, self._pause, self._budget = call, limiter, pause, budget
        self._timeout, self._ports, self._clock = timeout_seconds, list(ports), clock

    async def render(self, source: Source, url: str, identity, proxies) -> RenderOutput:
        domain = domain_of(source)
        if await self._pause.active(domain):
            return RenderOutput(skipped="paused")
        if not await self._budget.take():
            return RenderOutput(skipped="budget")
        deadline = self._clock() + self._timeout
        shots: dict[str, bytes] = {}
        blocks: list[dict] = []
        version, truncated = None, False
        for viewport in VIEWPORT_ORDER:
            await self._limiter.wait_turn(domain)
            if await self._pause.active(domain):
                return RenderOutput(skipped="paused")
            choice = proxies.pick() if proxies else None
            if isinstance(choice, Deferral):
                return RenderOutput(skipped="paused")
            remaining = deadline - self._clock()
            if remaining <= 0:
                return self._failed(source, Reason.RENDER_FAILED, "render exceeded its time")
            payload = self._payload(source, url, identity, viewport, choice, remaining)
            try:
                reply = await self._call(payload, remaining)
            except RenderCallError as error:
                return await self._error(source, domain, error, proxies, choice)
            shots[viewport], version, truncated = reply.png, reply.browser_version, truncated or reply.truncated
            blocks.extend(reply.blocks)
        return RenderOutput(shots, version, truncated, blocks=tuple(blocks))

    def _payload(self, source: Source, url: str, identity, viewport: str, choice, remaining: float) -> dict:
        headers = dict(identity.headers)
        if viewport == "mobile":
            try:
                headers = dict(mobile_variant(identity).headers)
            except ValueError:  # not Chrome: the renderer refuses it, and the render ends as `render_failed`
                pass
        payload = {
            "url": url,
            "source_host": domain_of(source),
            "viewport": viewport,
            "headers": headers,
            "ports": self._ports,
            "timeout_seconds": remaining,
        }
        if choice is not None:
            payload["proxy"] = choice.url
        return payload

    async def _error(self, source: Source, domain: str, error: RenderCallError, proxies, choice) -> RenderOutput:
        reason = _ERROR_REASONS.get(error.kind, Reason.RENDER_FAILED)
        if error.kind == "blocked":
            if choice is not None:
                proxies.penalize(choice)
            await self._pause.defer(domain, error.retry_after)
        return self._failed(source, reason, error.detail)

    @staticmethod
    def _failed(source: Source, reason: Reason, detail: str) -> RenderOutput:
        return RenderOutput(errors=(JobError(reason, detail, source.id),))
