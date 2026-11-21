"""Social collectors keyed by host, beside the page-parser registry (`ParserRegistry`)."""

from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import urlsplit

from iw_scraper.ratelimit import host_key
from iw_scraper.social import telegram
from iw_scraper.social.model import Channel

# (body, final_url) -> Channel; a collector raises `ParseFailure` for a page it cannot read
Collector = Callable[[bytes, str], Channel]


@dataclass(frozen=True)
class Registration:
    parse: Collector
    platform: str  # the one `sources.platform` value this collector accepts for its host
    valid_url: Callable[[str], bool]  # the URL form a source of this platform must have


class CollectorRegistry:
    def __init__(self) -> None:
        self._by_host: dict[str, Registration] = {}

    def register(
        self, host: str, parse: Collector, *, platform: str = "other", valid_url: Callable[[str], bool] = lambda url: True
    ) -> None:
        key = host_key(host.lower())
        if key in self._by_host:
            raise ValueError(f"a collector is already registered for {key}")
        self._by_host[key] = Registration(parse, platform, valid_url)

    def for_url(self, url: str) -> Registration | None:
        return self._by_host.get(host_key((urlsplit(url).hostname or "").lower()))

    def accepts(self, platform: str, url: str) -> bool:
        """A collector is registered for the host of `url` and takes this `platform`."""
        registration = self.for_url(url)
        return registration is not None and registration.platform == platform


registry = CollectorRegistry()
registry.register("t.me", telegram.parse, valid_url=telegram.valid_url)
