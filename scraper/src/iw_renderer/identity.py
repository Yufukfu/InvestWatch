"""Make the identity a request names true for the browser that actually runs it.

The scraper draws one identity per run for a Chrome version (`CHROME_VERSION`). Playwright's Chromium may be a
different major (ADR 0107), and it sends its own TLS handshake, so a user agent that claims another version
would be a false claim. The renderer therefore rewrites the version in the user agent and client hints to its
browser's and keeps everything else (platform, mobile flag, `accept-language`).
"""

import re

_UA_CHROME = re.compile(r"Chrome/(\d+)\.")


def browser_identity(headers: tuple[tuple[str, str], ...], browser_version: str) -> tuple[tuple[str, str], ...]:
    """Headers whose Chrome major is the browser's. Raise `ValueError` for anything that is not Chrome."""
    user_agent = dict(headers).get("user-agent", "")
    match = _UA_CHROME.search(user_agent)
    if match is None:
        raise ValueError("the renderer only emulates Chrome identities")
    claimed, actual = match.group(1), browser_version.split(".")[0]
    if claimed == actual:
        return headers
    rewritten = {
        "user-agent": user_agent.replace(f"Chrome/{claimed}.", f"Chrome/{actual}."),
        "sec-ch-ua": dict(headers).get("sec-ch-ua", "").replace(f'v="{claimed}"', f'v="{actual}"'),
    }
    return tuple((name, rewritten.get(name, value)) for name, value in headers)
