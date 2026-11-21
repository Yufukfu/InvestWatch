"""Which addresses a request may reach: resolve a host, refuse every internal answer, return the one checked.

No dependency on the fetch client, so the renderer image can carry this one module (ADR 0105). `AddressRefused`
says why; `targets.AddressGuard` maps it to `FetchFailure` for the scraper and the renderer maps it to an aborted
browser request.
"""

import asyncio
import ipaddress
import socket
from collections.abc import Awaitable, Callable, Iterable

RESOLVE_TIMEOUT_SECONDS = 5.0  # a resolver that does not answer is a transport failure, not a stalled worker

_NAT64 = ipaddress.ip_network("64:ff9b::/96")  # carries an IPv4 address in its last 32 bits
_V4_COMPATIBLE = ipaddress.ip_network("::/96")  # deprecated, same layout
_IETF_PROTOCOL_V4 = ipaddress.ip_network("192.0.0.0/24")  # holds `192.0.0.9`, which `is_global` calls global

Resolver = Callable[[str], Awaitable[list[str]]]


class AddressRefused(Exception):
    """The host is internal or cannot be resolved. `lookup_failed` marks a DNS failure (transport), not a refusal."""

    def __init__(self, detail: str, *, lookup_failed: bool = False) -> None:
        super().__init__(detail)
        self.detail = detail
        self.lookup_failed = lookup_failed


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
        raise AddressRefused(f"address not allowed for host {host}")


class AddressChecker:
    def __init__(
        self,
        resolver: Resolver = system_resolver,
        internal_hosts: Iterable[str] = (),
        timeout: float = RESOLVE_TIMEOUT_SECONDS,
    ) -> None:
        self._resolver = resolver
        self._internal = frozenset(host.lower() for host in internal_hosts)
        self._timeout = timeout

    async def check(self, host: str, timeout: float | None = None) -> str:
        """The public address to connect to for `host`; raises `AddressRefused` for an internal one."""
        name = host.lower().rstrip(".")
        literal = _parse_ip(name)
        if literal is not None:
            _require_public(literal, name)
            return name
        if name in self._internal or "." not in name:  # a bare name is a compose service or `localhost`
            raise AddressRefused(f"internal host name: {name}")
        try:
            answers = await asyncio.wait_for(self._resolver(name), self._timeout if timeout is None else timeout)
        except UnicodeError:  # an empty or over-long label; not an OSError, and not a lookup failure
            raise AddressRefused("host name is not valid") from None
        except OSError as exc:
            raise AddressRefused(f"DNS lookup failed: {type(exc).__name__}", lookup_failed=True) from None
        if not answers:
            raise AddressRefused(f"host does not resolve: {name}")
        for answer in answers:  # one internal answer refuses the host, whatever else it returns
            address = _parse_ip(answer)
            if address is None:
                raise AddressRefused(f"unreadable address for host {name}")
            _require_public(address, name)
        return answers[0]
