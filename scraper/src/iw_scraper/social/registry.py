"""Social collectors keyed by host, beside the page-parser registry (`ParserRegistry`)."""

from collections.abc import Callable
from urllib.parse import urlsplit

from iw_scraper.ratelimit import host_key
from iw_scraper.social import telegram

# (body, final_url) -> Channel; a collector raises `ParseFailure` for a page it cannot read
Collector = Callable[[bytes, str], telegram.Channel]


class CollectorRegistry:
    def __init__(self) -> None:
        self._by_host: dict[str, Collector] = {}

    def register(self, host: str, collector: Collector) -> None:
        key = host_key(host.lower())
        if key in self._by_host:
            raise ValueError(f"a collector is already registered for {key}")
        self._by_host[key] = collector

    def for_url(self, url: str) -> Collector | None:
        return self._by_host.get(host_key((urlsplit(url).hostname or "").lower()))


registry = CollectorRegistry()
registry.register("t.me", telegram.parse)
