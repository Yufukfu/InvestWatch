"""Keep the browser inside the page it was asked to render (design decisions 3 and 11).

`RequestPolicy` decides, for each request the browser makes, whether it may leave the machine. `confined_page` attaches
that decision to a Playwright context together with the browser-side switches (websockets, popups; Playwright
dismisses dialogs itself when nobody listens).
The checks cannot pin the address Chromium finally connects to, so DNS rebinding stays a residual risk (ADR 0105).
"""

import asyncio
from collections.abc import Awaitable, Callable, Iterable
from urllib.parse import urlsplit

from playwright.async_api import BrowserContext, Page, Route, WebSocketRoute
from playwright.async_api import Error as PlaywrightError

from iw_scraper.addresses import AddressRefused

ALLOWED_PORTS = (80, 443)
BLOCKED_RESOURCE_TYPES = frozenset({"media", "eventsource", "websocket"})
CONTEXT_OPTIONS = {"service_workers": "block", "accept_downloads": False}  # permissions are never granted
# `service_workers="block"` only stops a worker from intercepting requests (measured: `register()` still resolves in
# the headless shell), and a worker's own fetches would bypass the policy, so `navigator.serviceWorker` is removed
# from every frame, before any page script runs (no instance of the container is left to call `register` on).
NO_SERVICE_WORKERS = """
(() => {
  Object.defineProperty(Navigator.prototype, 'serviceWorker', { get: () => undefined, configurable: false });
})();
"""

AddressCheck = Callable[[str], Awaitable[str]]


def _same_site(host: str, source_host: str) -> bool:
    """`www.x.com`, `x.com` and `app.x.com` are one site; without a public-suffix list this is deliberately simple."""
    return host == source_host or host.endswith(f".{source_host}") or source_host.endswith(f".{host}")


class RequestPolicy:
    def __init__(
        self, source_host: str, address_check: AddressCheck, allowed_ports: Iterable[int] = ALLOWED_PORTS
    ) -> None:
        self._source_host = source_host.lower().rstrip(".")
        self._address_check = address_check
        self._ports = frozenset(allowed_ports)
        self.refusals: list[str] = []  # why each refused request was refused, for the render's meta and errors
        self.navigation_refusal: str | None = None  # the first refused navigation: the page may never have loaded

    async def verdict(self, url: str, resource_type: str, *, is_navigation: bool) -> str | None:
        """Why the request must be aborted, or `None` when it may go ahead. The reason never holds a query string."""
        try:
            parts = urlsplit(url)
            host, port = (parts.hostname or "").lower().rstrip("."), parts.port
        except ValueError:
            return "unreadable URL"
        if parts.scheme not in ("http", "https") or not host:
            return f"scheme not allowed: {parts.scheme or 'none'}"
        effective = port if port is not None else (443 if parts.scheme == "https" else 80)
        if effective not in self._ports:
            return f"port not allowed: {effective}"
        if resource_type in BLOCKED_RESOURCE_TYPES:
            return f"resource type not allowed: {resource_type}"
        if is_navigation and not _same_site(host, self._source_host):
            return f"navigation away from the source: {host}"
        try:
            await self._address_check(host)
        except AddressRefused as refused:
            return refused.detail
        return None


_background: set[asyncio.Task] = set()  # a task nobody references can be collected before it finishes


def _spawn(action: Awaitable[None]) -> None:
    """Run a close or dismiss from an event handler; the page may already be gone, which is the goal anyway."""

    async def quietly() -> None:
        try:
            await action
        except PlaywrightError:
            pass

    task = asyncio.ensure_future(quietly())
    _background.add(task)
    task.add_done_callback(_background.discard)


async def confined_page(context: BrowserContext, policy: RequestPolicy) -> Page:
    """The one page of a context, with every request routed through `policy`; any other page it opens is closed.

    A refused navigation is answered `204 No Content`, which leaves the document in place; an abort would replace it
    with the browser's error page and the render would measure that. Every other refusal is an abort.
    """

    async def handle(route: Route) -> None:
        request = route.request
        try:
            try:
                navigation = request.is_navigation_request() and request.frame.parent_frame is None
            except PlaywrightError:  # the frame does not exist yet: the first navigation of a popup
                navigation = request.is_navigation_request()
            reason = await policy.verdict(request.url, request.resource_type, is_navigation=navigation)
        except Exception as error:  # fail closed: a request that cannot be judged does not go out
            reason, navigation = f"request could not be checked: {type(error).__name__}", False
        if reason is None:
            await route.continue_()
            return
        policy.refusals.append(reason)
        if navigation:
            policy.navigation_refusal = policy.navigation_refusal or reason
            await route.fulfill(status=204)
        else:
            await route.abort("blockedbyclient")

    async def refuse_websocket(socket: WebSocketRoute) -> None:
        policy.refusals.append("websocket not allowed")
        await socket.close()  # `route` does not see websockets, `route_web_socket` does

    await context.add_init_script(NO_SERVICE_WORKERS)
    await context.route("**/*", handle)
    await context.route_web_socket("**/*", refuse_websocket)
    page = await context.new_page()  # created before the listener, so only later pages (popups) are closed
    context.on("page", lambda extra: _spawn(extra.close()))
    return page
