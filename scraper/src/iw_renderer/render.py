"""Render one page in one viewport: a fresh context, one navigation, and a verdict on what came back.

The scraper calls this once per viewport (design decisions 1 and 4), so it can pace each navigation. Nothing here
keeps state between calls, and no failure detail holds a proxy URL, a query string or page content.
"""

import asyncio
import re
from dataclasses import dataclass, replace
from urllib.parse import unquote, urlsplit

from playwright.async_api import Browser, Page, Request
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from iw_renderer.confine import ALLOWED_PORTS, CONTEXT_OPTIONS, AddressCheck, RequestPolicy, confined_page
from iw_renderer.identity import browser_identity
from iw_renderer.settings import (
    DEFAULT_MAX_PAGE_HEIGHT,
    DEFAULT_MAX_PNG_BYTES,
    DEFAULT_TIMEOUT_SECONDS,
    RenderLimits,
)
from iw_renderer.viewports import VIEWPORTS
from iw_scraper.blocking import BLOCK_STATUSES, block_marker

BACKSTOP_GRACE_SECONDS = 2.0
SETTLE_TIMEOUT_MS = 3000  # how long to wait for the network to go quiet after `load`; a busy page is shot anyway
_BRAND = re.compile(r'"([^"]+)";v="(\d+)"')


class RenderFailed(Exception):
    """The page could not be rendered for a reason that is not a block. `detail` is safe to log and store."""

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class RenderBlocked(RenderFailed):
    """The site refused the browser (403, 429 or a challenge page). `retry_after` is the raw header, if any."""

    def __init__(self, detail: str, retry_after: str | None = None) -> None:
        super().__init__(detail)
        self.retry_after = retry_after


@dataclass(frozen=True)
class RenderRequest:
    url: str
    source_host: str
    viewport: str
    headers: tuple[tuple[str, str], ...]  # the identity for this viewport (the scraper chose it)
    proxy: str | None = None
    ports: tuple[int, ...] = ALLOWED_PORTS
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS  # for this call; the scraper passes the time left
    max_page_height: int = DEFAULT_MAX_PAGE_HEIGHT
    max_png_bytes: int = DEFAULT_MAX_PNG_BYTES


@dataclass(frozen=True)
class RenderResult:
    status: int
    final_url: str
    png: bytes
    truncated: bool  # the image was cut by the height or the byte cap


def playwright_proxy(url: str) -> dict[str, str]:
    """Playwright wants the credentials apart from the server address, and decoded (`%40` is `@`)."""
    parts = urlsplit(url)
    proxy = {"server": f"{parts.scheme}://{parts.netloc.rpartition('@')[2]}"}  # netloc keeps an IPv6 host's brackets
    if parts.username:
        proxy["username"] = unquote(parts.username)
        proxy["password"] = unquote(parts.password or "")
    return proxy


def _language_tags(accept_language: str) -> str:
    """Chromium takes the tags and writes the q-values itself: `pl-PL,pl;q=0.9` becomes `pl-PL,pl`."""
    return ",".join(part.split(";")[0].strip() for part in accept_language.split(",") if part.strip())


def _user_agent_override(by_name: dict[str, str]) -> dict:
    """The one place the user agent, client hints and language are set, so each header goes out once.

    Playwright's `locale` and `extra_http_headers` would add a second `Accept-Language` and `sec-ch-ua` to the ones
    Chromium builds itself; this override replaces what Chromium builds.
    """
    brands = [{"brand": brand, "version": version} for brand, version in _BRAND.findall(by_name.get("sec-ch-ua", ""))]
    return {
        "userAgent": by_name["user-agent"],
        "acceptLanguage": _language_tags(by_name.get("accept-language", "")),
        "userAgentMetadata": {
            "brands": brands,
            "fullVersionList": [{"brand": b["brand"], "version": f"{b['version']}.0.0.0"} for b in brands],
            "platform": by_name.get("sec-ch-ua-platform", '""').strip('"'),
            "platformVersion": "",
            "architecture": "",
            "model": "",
            "mobile": by_name.get("sec-ch-ua-mobile") == "?1",
        },
    }


def _failure(error: Exception) -> RenderFailed:
    if isinstance(error, PlaywrightTimeoutError):
        return RenderFailed("navigation timed out")
    return RenderFailed(f"browser error: {type(error).__name__}")  # never the message: it can carry URLs and proxies


async def _refuse_redirect_away(request: Request, policy: RequestPolicy) -> None:
    """Fail the render when any hop of the navigation's redirect chain left the source site or is internal.

    Chromium follows redirects inside its network stack, so the route handler sees only the first request (measured,
    ADR 0105). The hop may already have been requested; what the render keeps is decided here, so nothing the
    redirect led to is ever screenshotted or stored.
    """
    hop: Request | None = request
    while hop is not None:
        reason = await policy.verdict(hop.url, "document", is_navigation=True)
        if reason:
            raise RenderFailed(reason)
        hop = hop.redirected_from


async def _screenshot(
    page: Page, width: int, height: int, request: RenderRequest, deadline: float
) -> tuple[bytes, bool]:
    """A full-page PNG, cut at `max_page_height` and shortened until it fits `max_png_bytes`."""
    try:
        await page.wait_for_load_state("networkidle", timeout=min(SETTLE_TIMEOUT_MS, _remaining_ms(deadline)))
    except PlaywrightTimeoutError:
        pass  # a page that keeps polling is still shot
    await page.evaluate("document.fonts.ready.then(() => true)")
    page_height = await page.evaluate(
        "Math.max(document.documentElement.scrollHeight, document.body ? document.body.scrollHeight : 0)"
    )
    shot_height = min(page_height, request.max_page_height)
    truncated = shot_height < page_height
    while True:
        clip = {"x": 0, "y": 0, "width": width, "height": shot_height}
        png = await page.screenshot(type="png", full_page=True, clip=clip, timeout=_remaining_ms(deadline))
        if len(png) <= request.max_png_bytes:
            return png, truncated
        if shot_height <= height:
            raise RenderFailed("screenshot exceeds size cap")
        shot_height, truncated = max(height, shot_height // 2), True


class Renderer:
    """The limits and the queue around `render_viewport`: `concurrency` renders at a time, the rest wait."""

    def __init__(self, browser: Browser, address_check: AddressCheck, limits: RenderLimits | None = None) -> None:
        self._browser = browser
        self._address_check = address_check
        self._limits = limits or RenderLimits()
        self._slots = asyncio.Semaphore(self._limits.concurrency)
        self._render = render_viewport

    async def render(self, request: RenderRequest) -> RenderResult:
        bounded = replace(
            request,
            timeout_seconds=min(request.timeout_seconds, self._limits.timeout_seconds),
            max_page_height=min(request.max_page_height, self._limits.max_page_height),
            max_png_bytes=min(request.max_png_bytes, self._limits.max_png_bytes),
        )
        async with self._slots:
            return await self._render(self._browser, bounded, self._address_check)


async def render_viewport(browser: Browser, request: RenderRequest, address_check: AddressCheck) -> RenderResult:
    """One viewport of one page within `request.timeout_seconds`; the context is closed whatever happens."""
    deadline = asyncio.get_running_loop().time() + request.timeout_seconds
    try:
        # Playwright's own timeouts (below) end a render cleanly; cancelling a pending call leaves noise in its
        # connection, so the cancel at `deadline + grace` is only the backstop for a page that ignores them.
        return await asyncio.wait_for(
            _render(browser, request, address_check, deadline), request.timeout_seconds + BACKSTOP_GRACE_SECONDS
        )
    except TimeoutError:
        raise RenderFailed("render timed out") from None


def _remaining_ms(deadline: float) -> int:
    return max(1, int((deadline - asyncio.get_running_loop().time()) * 1000))


async def _render(
    browser: Browser, request: RenderRequest, address_check: AddressCheck, deadline: float
) -> RenderResult:
    viewport = VIEWPORTS.get(request.viewport)
    if viewport is None:
        raise RenderFailed(f"unknown viewport: {request.viewport}")
    try:
        headers = browser_identity(request.headers, browser.version)
    except ValueError as error:
        raise RenderFailed(str(error)) from None
    by_name = dict(headers)

    options = {
        **CONTEXT_OPTIONS,
        "viewport": {"width": viewport.width, "height": viewport.height},
        "device_scale_factor": 1,
        "is_mobile": viewport.is_mobile,
        "has_touch": viewport.has_touch,
        "user_agent": by_name["user-agent"],
    }
    if request.proxy:
        options["proxy"] = playwright_proxy(request.proxy)

    policy = RequestPolicy(request.source_host, address_check, request.ports)
    context = await browser.new_context(**options)
    try:
        page = await confined_page(context, policy)
        session = await context.new_cdp_session(page)
        await session.send("Emulation.setUserAgentOverride", _user_agent_override(by_name))
        try:
            response = await page.goto(request.url, wait_until="load", timeout=_remaining_ms(deadline))
        except PlaywrightError as error:
            if policy.navigation_refusal:
                raise RenderFailed(policy.navigation_refusal) from None
            raise _failure(error) from None
        if response is None:
            raise RenderFailed(policy.navigation_refusal or "navigation produced no document")
        await _refuse_redirect_away(response.request, policy)  # Playwright does not route redirect hops: check them here
        if response.status in BLOCK_STATUSES:
            raise RenderBlocked(f"HTTP {response.status}", response.headers.get("retry-after"))
        if response.status >= 400:
            raise RenderFailed(f"HTTP {response.status}")
        if marker := block_marker(await response.body()):
            raise RenderBlocked(f"block page marker: {marker}")
        try:
            png, truncated = await _screenshot(page, viewport.width, viewport.height, request, deadline)
        except PlaywrightError as error:
            raise _failure(error) from None
        return RenderResult(status=response.status, final_url=page.url, png=png, truncated=truncated)
    finally:
        await context.close()
