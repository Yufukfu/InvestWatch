"""Proxy rotation: which proxy serves the next request, and which ones are cooling after a 407.

`ProxyRotator` is long-lived and holds the cooldowns. `ProxyRotator.start_run()` returns the per-run
`ProxyRun`, which remembers the previous request's proxy (never the same twice in a row) and, in
`per_session` mode, the one fixed proxy. Proxy URLs may hold credentials, so everything that leaves this
module (logs, job errors, `scrape_meta.proxy`) uses `proxy_identifier`, never the URL.
"""

import hashlib
import math
import random
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from iw_scraper.types import Deferral

PER_REQUEST = "per_request"
PER_SESSION = "per_session"


def proxy_identifier(url: str) -> str:
    """A stable label that cannot be turned back into the URL or its credentials."""
    return "proxy-" + hashlib.sha256(url.encode()).hexdigest()[:8]


@dataclass(frozen=True)
class ProxyChoice:
    url: str = field(repr=False)  # may hold credentials
    identifier: str


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ProxyRotator:
    def __init__(
        self,
        proxies: list[str],
        mode: str,
        cooldown_seconds: float,
        clock: Callable[[], datetime] = _utc_now,
        rng: random.Random | None = None,
    ) -> None:
        if mode not in (PER_REQUEST, PER_SESSION):
            raise ValueError(f"unknown rotation mode {mode!r}")
        if not math.isfinite(cooldown_seconds) or cooldown_seconds <= 0:
            raise ValueError("the proxy cooldown must be a positive number of seconds")  # 0 would never cool
        self.proxies = list(dict.fromkeys(proxies))  # a duplicated entry is one proxy
        self.mode = mode
        self._cooldown = timedelta(seconds=cooldown_seconds)
        self._clock = clock
        self._rng = rng or random.Random()
        self._cooling_until: dict[str, datetime] = {}

    def start_run(self) -> "ProxyRun":
        return ProxyRun(self)

    def penalize(self, choice: ProxyChoice) -> None:
        """The proxy refused our credentials (407): skip it for the cooldown."""
        self._cooling_until[choice.url] = self._clock() + self._cooldown

    def _cooling(self, now: datetime) -> dict[str, datetime]:
        return {url: until for url, until in self._cooling_until.items() if until > now and url in self.proxies}


class ProxyRun:
    def __init__(self, rotator: ProxyRotator) -> None:
        self._rotator = rotator
        self._last: str | None = None
        self._fixed: str | None = None

    def penalize(self, choice: ProxyChoice) -> None:
        self._rotator.penalize(choice)

    def deferral(self) -> Deferral | None:
        """A `Deferral` when every proxy is cooling, so a run can wait before it announces itself. Uses nothing up."""
        rotator = self._rotator
        if not rotator.proxies:
            return None
        cooling = rotator._cooling(rotator._clock())
        if len(cooling) < len(rotator.proxies):
            return None
        return Deferral(until=min(cooling.values()))

    def pick(self) -> ProxyChoice | Deferral | None:
        """The proxy for the next request; a `Deferral` when none may be used now; None for a direct request."""
        rotator = self._rotator
        if not rotator.proxies:
            return None
        now = rotator._clock()
        cooling = rotator._cooling(now)
        available = [url for url in rotator.proxies if url not in cooling]

        if rotator.mode == PER_SESSION:
            if self._fixed in available:
                return self._choice(self._fixed)
            pool = available
        else:
            repeat_allowed = len(rotator.proxies) == 1
            pool = [url for url in available if repeat_allowed or url != self._last]

        if not pool:
            return Deferral(until=min(cooling.values()))
        url = rotator._rng.choice(pool)
        self._last = url
        if rotator.mode == PER_SESSION:
            self._fixed = url
        return self._choice(url)

    @staticmethod
    def _choice(url: str) -> ProxyChoice:
        return ProxyChoice(url=url, identifier=proxy_identifier(url))
