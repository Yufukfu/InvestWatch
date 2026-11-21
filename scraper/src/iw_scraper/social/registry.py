"""Social collectors keyed by host, beside the page-parser registry (`ParserRegistry`)."""

from collections.abc import Callable
from urllib.parse import urlsplit

from iw_scraper.ratelimit import host_key
from iw_scraper.social import telegram
from iw_scraper.social.model import Channel

# (body, final_url) -> Channel; a collector raises `ParseFailure` for a page it cannot read
Collector = Callable[[bytes, str], Channel]


class CollectorRegistry:
    def __init__(self) -> None:
        self._by_host: dict[str, tuple[Collector, str]] = {}

    def register(self, host: str, collector: Collector, *, platform: str = "other") -> None:
        """`platform` is the one `sources.platform` value this collector accepts for the host."""
        key = host_key(host.lower())
        if key in self._by_host:
            raise ValueError(f"a collector is already registered for {key}")
        self._by_host[key] = (collector, platform)

    def _entry(self, url: str) -> tuple[Collector, str] | None:
        return self._by_host.get(host_key((urlsplit(url).hostname or "").lower()))

    def for_url(self, url: str) -> Collector | None:
        entry = self._entry(url)
        return entry[0] if entry else None

    def accepts(self, platform: str, url: str) -> bool:
        """A collector is registered for the host of `url` and takes this `platform`."""
        entry = self._entry(url)
        return entry is not None and entry[1] == platform


registry = CollectorRegistry()
registry.register("t.me", telegram.parse)
