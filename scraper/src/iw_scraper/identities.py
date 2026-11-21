"""The identity table: user agent, ordered headers and TLS profile that belong to one browser version.

An identity is drawn once per run (`draw_identity`) and never mixed: the table is checked at import, so a
Chrome user agent on a Firefox TLS profile, or a version that differs between the user agent, the client
hints and the TLS profile, stops the process before any request is made.
"""

import random
import re
from collections.abc import Iterable

from noble_tls import Client

from iw_scraper.fetch import Identity

# One constant drives the user agent, `sec-ch-ua` and the TLS profile of every Chrome entry.
CHROME_VERSION = 146
# Older profiles are reset by KNF (ADR 0101 spike: Chrome 117 and 131 got EOF, 146 got 200).
MIN_VERSION = {"chrome": 146, "firefox": 147, "safari": 18}

_PROFILE = re.compile(r"^(CHROME|FIREFOX|SAFARI)_(\d+)")
_UA_VERSION = {
    "chrome": re.compile(r"Chrome/(\d+)\."),
    "firefox": re.compile(r"Firefox/(\d+)\."),
    "safari": re.compile(r"Version/(\d+)\."),
}


def _family_of(user_agent: str) -> str:
    # order matters: Chrome user agents also say "Safari/"
    if "Firefox/" in user_agent:
        return "firefox"
    if "Chrome/" in user_agent:
        return "chrome"
    if "Safari/" in user_agent:
        return "safari"
    raise ValueError(f"unrecognised browser family in user agent {user_agent!r}")


def check_pairing(identity: Identity) -> None:
    """Raise `ValueError` when the user agent, client hints and TLS profile are not one browser version."""
    names = [name for name, _ in identity.headers]
    if names != [name.lower() for name in names] or len(names) != len(set(names)):
        raise ValueError("header names must be lowercase and listed once")
    headers = dict(identity.headers)
    if "user-agent" not in headers:
        raise ValueError("identity has no user-agent header")
    if identity.tls_profile not in Client.__members__:
        raise ValueError(f"unknown TLS profile {identity.tls_profile!r}")

    profile = _PROFILE.match(identity.tls_profile)
    if profile is None:
        raise ValueError(f"cannot read a browser from TLS profile {identity.tls_profile!r}")
    family, version = profile.group(1).lower(), int(profile.group(2))

    user_agent = headers["user-agent"]
    if _family_of(user_agent) != family:
        raise ValueError(f"user agent and TLS profile are different browsers: {identity.tls_profile}")
    ua_version = _UA_VERSION[family].search(user_agent)
    if ua_version is None or int(ua_version.group(1)) != version:
        raise ValueError(f"user agent version differs from TLS profile {identity.tls_profile}")

    hints = headers.get("sec-ch-ua")
    if family == "chrome":
        if hints is None or f'v="{version}"' not in hints:
            raise ValueError(f"sec-ch-ua is missing or not version {version}")
    elif hints is not None:
        raise ValueError(f"{family} does not send client hints")

    if version < MIN_VERSION[family]:
        raise ValueError(f"stale profile {identity.tls_profile}: older than {family} {MIN_VERSION[family]}")


def load_table(identities: Iterable[Identity]) -> tuple[Identity, ...]:
    table = tuple(identities)
    if not table:
        raise ValueError("the identity table is empty")
    for identity in table:
        check_pairing(identity)
    return table


def _chrome(platform_token: str, hints_platform: str) -> Identity:
    """Chrome's navigation request headers in the order Chrome puts them on the wire."""
    return Identity(
        tls_profile=f"CHROME_{CHROME_VERSION}_PSK",
        headers=(
            ("sec-ch-ua", f'"Chromium";v="{CHROME_VERSION}", "Not-A.Brand";v="24", "Google Chrome";v="{CHROME_VERSION}"'),
            ("sec-ch-ua-mobile", "?0"),
            ("sec-ch-ua-platform", f'"{hints_platform}"'),
            ("upgrade-insecure-requests", "1"),
            (
                "user-agent",
                f"Mozilla/5.0 ({platform_token}) AppleWebKit/537.36 (KHTML, like Gecko) "
                f"Chrome/{CHROME_VERSION}.0.0.0 Safari/537.36",
            ),
            (
                "accept",
                "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,"
                "*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            ),
            ("sec-fetch-site", "none"),
            ("sec-fetch-mode", "navigate"),
            ("sec-fetch-user", "?1"),
            ("sec-fetch-dest", "document"),
            ("accept-encoding", "gzip, deflate, br"),  # no zstd: not verified to be decoded by the client
            ("accept-language", "pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7"),
            ("priority", "u=0, i"),
        ),
    )


TABLE: tuple[Identity, ...] = load_table(
    (
        _chrome("Windows NT 10.0; Win64; x64", "Windows"),
        _chrome("Macintosh; Intel Mac OS X 10_15_7", "macOS"),
        _chrome("X11; Linux x86_64", "Linux"),
    )
)


def draw_identity(rng: random.Random | None = None) -> Identity:
    """One identity for one run. Pass a seeded generator for a reproducible draw."""
    return (rng or random).choice(TABLE)
