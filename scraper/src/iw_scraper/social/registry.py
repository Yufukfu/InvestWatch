"""Social collectors keyed by host, beside the page-parser registry (`ParserRegistry`)."""

from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import urlsplit

from iw_scraper.ratelimit import host_key
from iw_scraper.social import telegram, x
from iw_scraper.social.model import Channel, Flow

# (body, final_url) -> Channel; a collector raises `ParseFailure` for a page it cannot read
Collector = Callable[[bytes, str], Channel]


@dataclass(frozen=True)
class Registration:
    parse: Collector | None  # a page parser (Telegram); None when `flow` runs the whole collection
    platform: str  # the one `sources.platform` value this collector accepts for its host
    valid_url: Callable[[str], bool]  # the URL form a source of this platform must have
    flow: Flow | None = None  # a dedicated flow `run_source` dispatches to instead of the page-parser path
    home_ip: bool = False  # the flow runs before identity, session and proxy: from the home IP, no robots check


class CollectorRegistry:
    def __init__(self) -> None:
        self._by_host: dict[str, Registration] = {}

    def register(
        self,
        host: str,
        parse: Collector | None = None,
        *,
        platform: str = "other",
        valid_url: Callable[[str], bool] = lambda url: True,
        flow: Flow | None = None,
        home_ip: bool = False,
    ) -> None:
        if (parse is None) == (flow is None):
            raise ValueError("a registration names a page parser or a flow, not both and not neither")
        if home_ip and flow is None:
            raise ValueError("home_ip applies to a flow only")
        key = host_key(host.lower())
        if key in self._by_host:
            raise ValueError(f"a collector is already registered for {key}")
        self._by_host[key] = Registration(parse, platform, valid_url, flow, home_ip)

    def for_url(self, url: str) -> Registration | None:
        return self._by_host.get(host_key((urlsplit(url).hostname or "").lower()))

    def accepts(self, platform: str, url: str) -> bool:
        """A collector is registered for the host of `url` and takes this `platform`."""
        registration = self.for_url(url)
        return registration is not None and registration.platform == platform


registry = CollectorRegistry()
registry.register("t.me", telegram.parse, valid_url=telegram.valid_url)
registry.register("x.com", flow=x.flow, platform="x", valid_url=x.valid_url, home_ip=True)
