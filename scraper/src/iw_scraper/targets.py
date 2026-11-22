"""What may be fetched: which sources are collected, which URLs and which addresses are allowed.

`select_sources` is a pure function over source records. `UrlGuard` checks the scheme, port and host list of every
URL the scraper would request (the source URL, each redirect hop) or would take from scraped content (`canonical_url`,
`links`). `AddressGuard` resolves the host itself, refuses internal addresses and returns the address that was
checked, so the caller connects to it and never resolves a second time (the checks live in `addresses`, which the
renderer shares; this class maps its refusals to `FetchFailure`). `target_guard` joins them into the
`TargetGuard` that `fetch` asks about every hop. Every refusal is `blocked_target`, and a refusal never echoes
credentials, a query string or a path.
"""

from collections.abc import Iterable
from urllib.parse import urlsplit

from iw_scraper.addresses import RESOLVE_TIMEOUT_SECONDS, AddressChecker, AddressRefused, Resolver, system_resolver
from iw_scraper.fetch import FetchFailure, TargetGuard
from iw_scraper.ratelimit import host_key
from iw_scraper.types import Reason, Source

_DEFAULT_PORTS = {"http": 80, "https": 443}


def select_sources(sources: Iterable[Source], *, scheduled: bool) -> list[Source]:
    """The collectable sources, in order. A scheduled run skips the manual-only ones (`schedule_cron` is null)."""
    return [s for s in sources if s.collectable and (s.schedule_cron is not None or not scheduled)]


def _refuse(detail: str) -> FetchFailure:
    return FetchFailure(Reason.BLOCKED_TARGET, detail)


class UrlGuard:
    def __init__(self, allowed_hosts: Iterable[str], allowed_ports: Iterable[int] = (80, 443)) -> None:
        self._hosts = frozenset(host_key(host.lower()) for host in allowed_hosts)
        self._ports = frozenset(allowed_ports)

    @classmethod
    def for_sources(
        cls, sources: Iterable[Source], extra_hosts: Iterable[str] = (), allowed_ports: Iterable[int] = (80, 443)
    ) -> "UrlGuard":
        """The allow-list is the host of every collectable source plus the configured extras."""
        hosts = [host for s in sources if s.collectable and (host := urlsplit(s.url).hostname)]
        return cls([*hosts, *extra_hosts], allowed_ports)

    def check(self, url: str, *, enforce_host: bool = True) -> None:
        """Raise `FetchFailure(BLOCKED_TARGET)` unless `url` may be requested. The source URL passes `enforce_host=False`."""
        try:
            parts = urlsplit(url)
            hostname, port = parts.hostname, parts.port  # `.port` raises ValueError on a bad port
        except ValueError:
            raise _refuse("URL cannot be parsed") from None
        if parts.scheme not in _DEFAULT_PORTS or not hostname:
            raise _refuse(f"scheme not allowed: {parts.scheme or 'none'}")
        if "@" in parts.netloc:  # userinfo of any kind
            raise _refuse("URL carries credentials")
        effective = port if port is not None else _DEFAULT_PORTS[parts.scheme]
        if effective not in self._ports:
            raise _refuse(f"port not allowed: {effective}")
        if enforce_host and host_key(hostname) not in self._hosts:
            raise _refuse(f"host not allowed: {hostname}")


class AddressGuard:
    def __init__(self, resolver: Resolver = system_resolver, internal_hosts: Iterable[str] = ()) -> None:
        self._checker = AddressChecker(resolver, internal_hosts)

    async def check(self, host: str) -> str:
        """The public address to connect to for `host`; raises `FetchFailure` for an internal one."""
        try:
            return await self._checker.check(host, RESOLVE_TIMEOUT_SECONDS)
        except AddressRefused as refused:
            reason = Reason.HTTP_ERROR if refused.lookup_failed else Reason.BLOCKED_TARGET
            raise FetchFailure(reason, refused.detail) from None


def target_guard(urls: UrlGuard, addresses: AddressGuard, source_url: str) -> TargetGuard:
    """The guard `fetch` asks about every hop: the URL checks first (the source URL skips the host list), then the address."""

    async def guard(url: str) -> str | None:
        urls.check(url, enforce_host=url != source_url)
        return await addresses.check(urlsplit(url).hostname)

    return guard
