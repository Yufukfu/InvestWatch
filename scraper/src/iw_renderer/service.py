"""The renderer's HTTP interface: `POST /render` for one viewport of one page, `GET /health`.

The scraper is the only caller (private `render` network). Every field is validated before any navigation. Nothing
that identifies the page or the proxy is logged: logs carry the source host, the viewport and the outcome. The response
echoes only the final URL, which the scraper already knows.
"""

import base64
import json
import logging
import re
import time
from urllib.parse import urlsplit

from aiohttp import web

from iw_renderer.confine import _same_site
from iw_renderer.render import RenderBlocked, RenderFailed, RenderRefused, Renderer, RenderRequest
from iw_renderer.settings import DEFAULT_TIMEOUT_SECONDS
from iw_renderer.viewports import VIEWPORTS

_log = logging.getLogger(__name__)

MAX_BODY_BYTES = 64 * 1024
MAX_URL_LENGTH = 2048
MAX_HEADERS = 40
MAX_HEADER_LENGTH = 2048
MAX_PORTS = 10
MAX_TIMEOUT_SECONDS = 300.0
_PROXY_SCHEMES = ("http", "https", "socks5")
_RENDERER = web.AppKey("renderer", Renderer)


class InvalidRequest(ValueError):
    """The request body is not acceptable; the message names the field and never its value."""


def _text(data: dict, field: str, maximum: int) -> str:
    value = data.get(field)
    if not isinstance(value, str) or not value or len(value) > maximum:
        raise InvalidRequest(f"field '{field}' must be a non-empty string of at most {maximum} characters")
    return value


def _url(value: str, field: str, schemes: tuple[str, ...]) -> None:
    try:
        parts = urlsplit(value)
        parts.port  # noqa: B018 (raises ValueError on a bad port)
    except ValueError:
        raise InvalidRequest(f"field '{field}' is not a readable URL") from None
    if parts.scheme not in schemes or not parts.hostname or "@" in parts.netloc and field == "url":
        raise InvalidRequest(f"field '{field}' must be a {'/'.join(schemes)} URL" + (" without credentials" if field == "url" else ""))


_HOSTNAME = re.compile(r"[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)*")


def _source_host(data: dict, url: str) -> str:
    """A bare hostname, and the same site as the page URL: the renderer's confinement is built from it."""
    host = _text(data, "source_host", 253).lower()
    if not _HOSTNAME.fullmatch(host):
        raise InvalidRequest("field 'source_host' must be a hostname")
    if not _same_site((urlsplit(url).hostname or "").lower(), host):
        raise InvalidRequest("field 'source_host' must be the site of 'url'")
    return host


def _headers(data: dict) -> tuple[tuple[str, str], ...]:
    raw = data.get("headers")
    if not isinstance(raw, dict) or not 0 < len(raw) <= MAX_HEADERS:
        raise InvalidRequest(f"field 'headers' must be an object of 1 to {MAX_HEADERS} entries")
    pairs = []
    for name, value in raw.items():
        if not isinstance(value, str) or len(value) > MAX_HEADER_LENGTH or not name or len(name) > 100:
            raise InvalidRequest("field 'headers' must map names to strings of limited length")
        if any(ord(char) < 32 for char in name + value):
            raise InvalidRequest("field 'headers' must not hold control characters")
        pairs.append((name.lower(), value))
    if "user-agent" not in {name for name, _ in pairs}:
        raise InvalidRequest("field 'headers' must include user-agent")
    return tuple(pairs)


def _ports(data: dict) -> tuple[int, ...]:
    raw = data.get("ports")
    if not isinstance(raw, list) or not 0 < len(raw) <= MAX_PORTS:
        raise InvalidRequest(f"field 'ports' must be a list of 1 to {MAX_PORTS} ports")
    if any(isinstance(port, bool) or not isinstance(port, int) or not 0 < port < 65536 for port in raw):
        raise InvalidRequest("field 'ports' must hold integers from 1 to 65535")
    return tuple(raw)


def parse_request(data: object) -> RenderRequest:
    if not isinstance(data, dict):
        raise InvalidRequest("the body must be a JSON object")
    url = _text(data, "url", MAX_URL_LENGTH)
    _url(url, "url", ("http", "https"))
    viewport = _text(data, "viewport", 20)
    if viewport not in VIEWPORTS:
        raise InvalidRequest(f"field 'viewport' must be one of {', '.join(VIEWPORTS)}")
    proxy = data.get("proxy")
    if proxy is not None:
        if not isinstance(proxy, str) or len(proxy) > MAX_URL_LENGTH:
            raise InvalidRequest("field 'proxy' must be a string or null")
        _url(proxy, "proxy", _PROXY_SCHEMES)
    timeout = data.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS)
    if isinstance(timeout, bool) or not isinstance(timeout, int | float) or not 0 < timeout <= MAX_TIMEOUT_SECONDS:
        raise InvalidRequest(f"field 'timeout_seconds' must be a number above 0 and at most {MAX_TIMEOUT_SECONDS:g}")
    source_host = _source_host(data, url)
    return RenderRequest(
        url=url,
        source_host=source_host,
        viewport=viewport,
        headers=_headers(data),
        proxy=proxy,
        ports=_ports(data),
        timeout_seconds=float(timeout),
    )


def _error(status: int, kind: str, detail: str, **extra: object) -> web.Response:
    return web.json_response({"error": {"kind": kind, "detail": detail, **extra}}, status=status)


async def _render(request: web.Request) -> web.Response:
    renderer = request.app[_RENDERER]
    try:
        body = await request.read()
    except web.HTTPRequestEntityTooLarge:
        return _error(413, "invalid_request", f"the body is larger than {MAX_BODY_BYTES} bytes")
    try:
        parsed = parse_request(_load_json(body))
    except InvalidRequest as invalid:
        return _error(400, "invalid_request", str(invalid))

    started = time.monotonic()
    outcome = "ok"
    try:
        result = await renderer.render(parsed)
    except RenderBlocked as blocked:
        outcome = "blocked"
        return _error(403, "blocked", blocked.detail, retry_after=blocked.retry_after)
    except RenderRefused as refused:
        outcome = "refused"
        return _error(422, "refused", refused.detail)
    except RenderFailed as failed:
        outcome = "failed"
        return _error(502, "failed", failed.detail)
    except Exception as error:  # the service stays up; the type name is the only thing that is safe to say
        outcome = f"error:{type(error).__name__}"
        return _error(502, "failed", "unexpected renderer error")
    finally:
        _log.info(
            "render viewport=%s host=%s outcome=%s ms=%d",
            parsed.viewport,
            parsed.source_host,
            outcome,
            (time.monotonic() - started) * 1000,
        )
    return web.json_response(
        {
            "viewport": parsed.viewport,
            "status": result.status,
            "final_url": result.final_url,
            "png_base64": base64.b64encode(result.png).decode("ascii"),
            "truncated": result.truncated,
            "browser_version": renderer.browser.version,
        }
    )


def _load_json(body: bytes) -> object:
    try:
        return json.loads(body)
    except ValueError:  # includes a body that is empty or not UTF-8
        raise InvalidRequest("the body is not valid JSON") from None


async def _health(request: web.Request) -> web.Response:
    browser = request.app[_RENDERER].browser
    if not browser.is_connected():
        return web.json_response({"status": "unhealthy"}, status=503)
    return web.json_response({"status": "ok", "browser_version": browser.version})


def create_app(renderer: Renderer) -> web.Application:
    app = web.Application(client_max_size=MAX_BODY_BYTES)
    app[_RENDERER] = renderer
    app.add_routes([web.post("/render", _render), web.get("/health", _health)])
    return app
