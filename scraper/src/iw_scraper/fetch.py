"""One fetch attempt: a URL and an identity in, a checked response body out, or a `FetchFailure`.

Facts about the client (`noble-tls` over the Go `tls-client`, ADR 0101) that shape this module:
- the body is streamed to a file and cannot be aborted mid-transfer, so the size cap is checked afterwards;
- the client transcodes a body to UTF-8 whenever it can find a charset (header, then `<meta>`), so the
  result reports `charset=utf-8` and the parser must not decode it a second time;
- headers not listed in `header_order` are appended by the client, so an identity lists every header;
- redirects are followed here, one hop at a time, so every hop can be checked.
"""

import logging
import os
import tempfile
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import SplitResult, unquote, urljoin, urlsplit

from noble_tls import Client, Session

from iw_scraper.parsing import HTML_TYPES, content_type_params
from iw_scraper.proxy import ProxyChoice, ProxyRun
from iw_scraper.reporting import redact
from iw_scraper.types import Deferral, Reason

_log = logging.getLogger(__name__)
DEFAULT_TIMEOUT_SECONDS = 20.0
DEFAULT_MAX_BYTES = 5 * 1024 * 1024
MAX_REDIRECTS = 5
_REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})
_WEB_SCHEMES = frozenset({"http", "https"})
_BLOCK_STATUSES = frozenset({403, 429})
# Challenge pages are small. A large page that merely embeds a captcha widget (a contact or newsletter
# form) is a real page, and `blocked` would not be retried, so the marker scan skips it.
_MARKER_SCAN_MAX_BYTES = 20_000
# Vendor-specific names found in challenge pages. The bare word "captcha" is not a marker: the real KNF
# page contains it in ordinary text.
_BLOCK_MARKERS = (
    b"g-recaptcha",
    b"h-captcha",
    b"hcaptcha.com",
    b"cf-turnstile",
    b"cf-chl-",
    b"/cdn-cgi/challenge-platform",
    b"captcha-delivery.com",
    b"px-captcha",
)


@dataclass(frozen=True)
class Identity:
    """A TLS profile (a `noble_tls.Client` member name) and the headers to send, in wire order.

    The table that pairs user agents with profiles and rejects mismatches is task 4.1.
    """

    tls_profile: str
    headers: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class FetchResult:
    url: str  # final URL after redirects
    status: int
    content_type: str  # media type with `charset=utf-8`: the client already decoded the body
    body: bytes
    headers: dict[str, str]  # lowercase names
    proxy_id: str | None  # identifier (never the URL) of the proxy that served the final request


class FetchFailure(Exception):
    """The fetch produced nothing usable; `reason` is a `Reason` from the closed set."""

    def __init__(self, reason: Reason, detail: str, proxy_id: str | None = None) -> None:
        super().__init__(detail)
        self.reason = reason
        self.detail = detail
        self.proxy_id = proxy_id  # the proxy involved, for `scrape_meta.proxy`; never its URL


class ProxyAuthFailure(FetchFailure):
    """The proxy answered 407: the caller cools that proxy and tries another."""


class FetchDeferred(Exception):
    """Nothing was fetched and nothing failed: no proxy may be used until `deferral.until`."""

    def __init__(self, deferral: Deferral) -> None:
        super().__init__(f"deferred until {deferral.until.isoformat()}")
        self.deferral = deferral


# Asked about every URL before it is requested. Raises `FetchFailure(BLOCKED_TARGET)` to refuse, or returns
# the address to connect to (checked by the caller) or None to let the client resolve the host.
TargetGuard = Callable[[str], Awaitable[str | None]]


def _new_session(identity: Identity) -> Session:
    try:
        client = Client[identity.tls_profile]
    except KeyError as exc:
        raise ValueError(f"unknown TLS profile {identity.tls_profile!r}") from exc
    session = Session(
        client=client,
        header_order=[name for name, _ in identity.headers],
        random_tls_extension_order=True,
    )
    session.headers.clear()  # drop the library's own User-Agent, Accept and Connection defaults
    session.headers.update(dict(identity.headers))
    return session


def _host_header(parts: SplitResult) -> str:
    host = parts.hostname or ""
    host = f"[{host}]" if ":" in host else host
    return f"{host}:{parts.port}" if parts.port else host


def _address_url(parts: SplitResult, address: str) -> str:
    host = f"[{address}]" if ":" in address else address
    netloc = f"{host}:{parts.port}" if parts.port else host
    return parts._replace(netloc=netloc).geturl()


def _scrub_proxy(message: str, choice: ProxyChoice | None) -> str:
    """Swap the proxy URL and its password (raw and percent-decoded) for the identifier."""
    if choice is None:
        return message
    password = urlsplit(choice.url).password
    secrets = [choice.url] + ([password, unquote(password)] if password else [])
    for secret in sorted(set(secrets), key=len, reverse=True):
        message = message.replace(secret, choice.identifier)
    return message


def _transport_failure(exc: Exception, choice: ProxyChoice | None = None) -> FetchFailure:
    message = redact(_scrub_proxy(str(exc), choice))
    lowered = message.lower()
    if "proxy responded with non 200 code: 407" in lowered:  # the client's wording for a refused CONNECT
        return ProxyAuthFailure(Reason.HTTP_ERROR, f"proxy authentication failed: {message}")
    if "timeout" in lowered or "deadline exceeded" in lowered:
        return FetchFailure(Reason.TIMEOUT, f"request timed out: {message}")
    return FetchFailure(Reason.HTTP_ERROR, f"transport error: {message}")


def _headers_of(response) -> dict[str, str]:
    return {
        str(name).lower(): ", ".join(value) if isinstance(value, list) else str(value)
        for name, value in response.headers.items()
    }


def _block_marker(body: bytes) -> str | None:
    if len(body) > _MARKER_SCAN_MAX_BYTES:
        return None
    lowered = body.lower()
    return next((m.decode() for m in _BLOCK_MARKERS if m in lowered), None)


def _read_checked_body(path: str, headers: dict[str, str], max_bytes: int) -> bytes:
    media_type, _ = content_type_params(headers.get("content-type"))
    if media_type is not None and media_type not in HTML_TYPES:
        raise FetchFailure(Reason.PARSE_ERROR, f"not an HTML response: {media_type}")
    size = os.path.getsize(path)
    if size > max_bytes:
        raise FetchFailure(Reason.PARSE_ERROR, f"body of {size} bytes exceeds the {max_bytes} byte cap")
    return Path(path).read_bytes()


async def _request_once(
    session: Session,
    url: str,
    choice: ProxyChoice | None,
    guard: TargetGuard | None,
    timeout: float,
    max_bytes: int,
) -> tuple[int, dict[str, str], bytes]:
    try:
        parts = urlsplit(url)
        hostname, _ = parts.hostname, parts.port  # `.port` raises ValueError on a bad port
    except ValueError as exc:
        raise FetchFailure(Reason.BLOCKED_TARGET, "URL cannot be parsed") from exc
    if parts.scheme not in _WEB_SCHEMES or not hostname:
        raise FetchFailure(Reason.BLOCKED_TARGET, f"scheme not allowed: {parts.scheme or 'none'}")
    if "@" in parts.netloc:  # userinfo of any kind
        raise FetchFailure(Reason.BLOCKED_TARGET, "URL carries credentials")  # never echo them

    address = await guard(url) if guard else None
    request_url, host_override = url, None
    session.server_name_overwrite = None
    if address and choice is None:  # behind a proxy the proxy resolves the host itself
        request_url, host_override = _address_url(parts, address), _host_header(parts)
        session.server_name_overwrite = hostname  # certificate and SNI still use the real host

    fd, path = tempfile.mkstemp(prefix="iw-body-")
    os.close(fd)
    try:
        try:
            response = await session.execute_request(
                "GET",
                request_url,
                allow_redirects=False,
                timeout_milliseconds=int(timeout * 1000),
                proxy=choice.url if choice else None,
                request_host_override=host_override,
                stream_output_path=path,
            )
        except (OSError, ValueError) as exc:  # TLSClientException is an OSError; a library fault may be a ValueError
            raise _transport_failure(exc, choice) from None
        headers = _headers_of(response)
        status = response.status_code
        if status == 407 and choice is not None:  # the proxy itself refused us, whatever the wording
            raise ProxyAuthFailure(Reason.HTTP_ERROR, "proxy answered 407")
        is_redirect = status in _REDIRECT_STATUSES and "location" in headers
        body = b"" if is_redirect or not 200 <= status < 300 else _read_checked_body(path, headers, max_bytes)
        return status, headers, body
    finally:
        if os.path.exists(path):
            os.unlink(path)


async def _request_through_proxies(
    session: Session,
    url: str,
    proxies: ProxyRun | None,
    guard: TargetGuard | None,
    timeout: float,
    max_bytes: int,
) -> tuple[int, dict[str, str], bytes, ProxyChoice | None]:
    """One request, each time through the proxy the run picks. A 407 cools that proxy and tries another."""
    while True:  # every 407 cools one more proxy, so the picks run out in at most len(proxies) rounds
        choice = proxies.pick() if proxies else None
        if isinstance(choice, Deferral):
            raise FetchDeferred(choice)
        try:
            return (*await _request_once(session, url, choice, guard, timeout, max_bytes), choice)
        except ProxyAuthFailure:
            proxies.penalize(choice)
        except FetchFailure as failure:
            failure.proxy_id = failure.proxy_id or (choice.identifier if choice else None)
            raise


async def fetch(
    url: str,
    identity: Identity,
    proxy: ProxyRun | None,
    *,
    guard: TargetGuard | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> FetchResult:
    """Request `url` once, following up to `MAX_REDIRECTS` redirects hop by hop. Never retries."""
    session = _new_session(identity)
    try:
        current = url
        proxy_id = None
        for _ in range(MAX_REDIRECTS + 1):
            status, headers, body, choice = await _request_through_proxies(
                session, current, proxy, guard, timeout, max_bytes
            )
            proxy_id = choice.identifier if choice else None
            if status in _REDIRECT_STATUSES and "location" in headers:
                current = urljoin(current, headers["location"])
                continue
            if status in _BLOCK_STATUSES:
                raise FetchFailure(Reason.BLOCKED, f"HTTP {status}", proxy_id)
            if not 200 <= status < 300:
                raise FetchFailure(Reason.HTTP_ERROR, f"HTTP {status}", proxy_id)
            if not body:
                raise FetchFailure(Reason.BLOCKED, "empty response body", proxy_id)
            if marker := _block_marker(body):
                raise FetchFailure(Reason.BLOCKED, f"block page marker: {marker}", proxy_id)
            media_type, _ = content_type_params(headers.get("content-type"))
            return FetchResult(
                url=current,
                status=status,
                content_type=f"{media_type or 'text/html'}; charset=utf-8",
                body=body,
                headers=headers,
                proxy_id=proxy_id,
            )
        raise FetchFailure(Reason.HTTP_ERROR, f"more than {MAX_REDIRECTS} redirects", proxy_id)
    finally:
        try:
            await session.close()
        except Exception as exc:  # a failed close must not hide the real outcome
            _log.warning("closing the session failed: %s", redact(str(exc)))
