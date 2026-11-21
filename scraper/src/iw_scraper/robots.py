"""`robots.txt`: may this run fetch the target path?

RFC 9309: a 4xx answer other than 429 (401, 403, 404, 410 ...) means the file is unavailable, so there are no
restrictions. A 429, a 5xx, a timeout or any transport failure means we cannot tell, so the path is disallowed for
this run. An answer to `robots.txt` is never a block signal: nothing here penalises an identity or a proxy.
The request goes through the run's own `ProxyRun` and target guard like any other hop.
"""

from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

from noble_tls import Session
from protego import Protego

from iw_scraper.fetch import (
    _REDIRECT_STATUSES,
    DEFAULT_TIMEOUT_SECONDS,
    MAX_REDIRECTS,
    FetchFailure,
    Identity,
    TargetGuard,
    _new_session,
    _request_through_proxies,
    close_session,
)
from iw_scraper.proxy import ProxyRun
from iw_scraper.types import Reason

ROBOTS_AGENT = "InvestWatch"  # the product token a site can address in its rules
ROBOTS_MAX_BYTES = 512 * 1024  # RFC 9309 asks parsers to read at least 500 KiB


@dataclass(frozen=True)
class RobotsVerdict:
    allowed: bool
    detail: str


def _verdict(status: int, body: bytes, url: str) -> RobotsVerdict:
    if 200 <= status < 300:
        rules = Protego.parse(body.decode("utf-8", errors="replace"))  # RFC 9309: `*`, `$`, longest match
        if rules.can_fetch(url, ROBOTS_AGENT):
            return RobotsVerdict(True, "allowed by robots.txt")
        return RobotsVerdict(False, "disallowed by robots.txt")
    if 400 <= status < 500 and status != 429:
        return RobotsVerdict(True, f"no robots.txt (HTTP {status})")
    return RobotsVerdict(False, f"robots.txt answered HTTP {status}")


async def check_robots(
    url: str,
    identity: Identity,
    proxy: ProxyRun | None,
    *,
    guard: TargetGuard | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    max_bytes: int = ROBOTS_MAX_BYTES,
    session: Session | None = None,
) -> RobotsVerdict:
    """Fetch `robots.txt` from the origin of `url` and say whether `url` may be fetched.

    Raises `FetchDeferred` (every proxy cooling) and a `FetchFailure` for a refused target, like `fetch`;
    every other failure is a verdict of "disallowed".
    """
    try:
        parts = urlsplit(url)
    except ValueError as exc:
        raise FetchFailure(Reason.BLOCKED_TARGET, "URL cannot be parsed") from exc
    current = f"{parts.scheme}://{parts.netloc}/robots.txt"
    owned = session is None
    session = session or _new_session(identity)  # a passed one is the run's, shared with `fetch`
    try:
        for _ in range(MAX_REDIRECTS + 1):
            try:
                status, headers, body, _ = await _request_through_proxies(
                    session, current, proxy, guard, timeout, max_bytes, html_only=False
                )
            except FetchFailure as failure:
                if failure.reason is Reason.BLOCKED_TARGET:
                    raise
                return RobotsVerdict(False, f"robots.txt unreachable: {failure.detail}")
            if status in _REDIRECT_STATUSES and "location" in headers:
                current = urljoin(current, headers["location"])
                continue
            return _verdict(status, body, url)
        return RobotsVerdict(False, f"robots.txt redirected more than {MAX_REDIRECTS} times")
    finally:
        if owned:
            await close_session(session)
