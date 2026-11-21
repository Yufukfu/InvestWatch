"""What may be fetched: which sources are collected, which URLs and which addresses are allowed.

`select_sources` is a pure function over source records. `UrlGuard` checks the scheme, port and host list of every
URL the scraper would request (the source URL, each redirect hop) or would take from scraped content (`canonical_url`,
`links`). `AddressGuard` resolves the host itself, refuses internal addresses and returns the address that was
checked, so the caller connects to it and never resolves a second time. `target_guard` joins them into the
`TargetGuard` that `fetch` asks about every hop. Every refusal is `blocked_target`, and a refusal never echoes
credentials, a query string or a path.
"""

import asyncio
import ipaddress
import socket
from collections.abc import Awaitable, Callable, Iterable
from urllib.parse import urlsplit

from iw_scraper.fetch import FetchFailure, TargetGuard
from iw_scraper.ratelimit import host_key
from iw_scraper.types import Reason, Source

_DEFAULT_PORTS = {"http": 80, "https": 443}
RESOLVE_TIMEOUT_SECONDS = 5.0  # a resolver that does not answer is a transport failure, not a stalled worker

_NAT64 = ipaddress.ip_network("64:ff9b::/96")  # carries an IPv4 address in its last 32 bits
_V4_COMPATIBLE = ipaddress.ip_network("::/96")  # deprecated, same layout
_IETF_PROTOCOL_V4 = ipaddress.ip_network("192.0.0.0/24")  # holds `192.0.0.9`, which `is_global` calls global

Resolver = Callable[[str], Awaitable[list[str]]]


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


async def system_resolver(host: str) -> list[str]:
    infos = await asyncio.get_running_loop().getaddrinfo(host, None, type=socket.SOCK_STREAM)
    return list(dict.fromkeys(info[4][0] for info in infos))


def _parse_ip(text: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    try:
        return ipaddress.ip_address(text)
    except ValueError:
        return None


def _embedded_ipv4(address: ipaddress.IPv6Address) -> ipaddress.IPv4Address | None:
    """The IPv4 address an IPv6 one stands for (mapped, 6to4, NAT64, IPv4-compatible), if any."""
    if address.ipv4_mapped:
        return address.ipv4_mapped  # `::ffff:127.0.0.1` is 127.0.0.1
    if address.sixtofour:
        return address.sixtofour
    if address in _NAT64 or address in _V4_COMPATIBLE:
        return ipaddress.IPv4Address(int(address) & 0xFFFFFFFF)
    return None


def _in_refused_range(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    # not global covers loopback, private, link-local, unique-local, unspecified and shared (100.64/10) ranges
    if not address.is_global or address.is_multicast:
        return True
    if isinstance(address, ipaddress.IPv4Address):
        return address in _IETF_PROTOCOL_V4
    return address.is_site_local


def _require_public(address: ipaddress.IPv4Address | ipaddress.IPv6Address, host: str) -> None:
    candidates = [address]
    if isinstance(address, ipaddress.IPv6Address) and (embedded := _embedded_ipv4(address)):
        candidates.append(embedded)  # a translator would carry the request to that IPv4 address
    if any(_in_refused_range(candidate) for candidate in candidates):
        raise _refuse(f"address not allowed for host {host}")


class AddressGuard:
    def __init__(self, resolver: Resolver = system_resolver, internal_hosts: Iterable[str] = ()) -> None:
        self._resolver = resolver
        self._internal = frozenset(host.lower() for host in internal_hosts)

    async def check(self, host: str) -> str:
        """The public address to connect to for `host`; raises `FetchFailure` for an internal one."""
        name = host.lower().rstrip(".")
        literal = _parse_ip(name)
        if literal is not None:
            _require_public(literal, name)
            return name
        if name in self._internal or "." not in name:  # a bare name is a compose service or `localhost`
            raise _refuse(f"internal host name: {name}")
        try:
            answers = await asyncio.wait_for(self._resolver(name), RESOLVE_TIMEOUT_SECONDS)
        except OSError as exc:
            raise FetchFailure(Reason.HTTP_ERROR, f"DNS lookup failed: {type(exc).__name__}") from None
        if not answers:
            raise _refuse(f"host does not resolve: {name}")
        for answer in answers:  # one internal answer refuses the host, whatever else it returns
            address = _parse_ip(answer)
            if address is None:
                raise _refuse(f"unreadable address for host {name}")
            _require_public(address, name)
        return answers[0]


def target_guard(urls: UrlGuard, addresses: AddressGuard, source_url: str) -> TargetGuard:
    """The guard `fetch` asks about every hop: the URL checks first (the source URL skips the host list), then the address."""

    async def guard(url: str) -> str | None:
        urls.check(url, enforce_host=url != source_url)
        return await addresses.check(urlsplit(url).hostname)

    return guard
