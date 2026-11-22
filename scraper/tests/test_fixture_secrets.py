"""No committed fixture holds a credential, a session token or the client's address (spec `social-collection`)."""

import re
from pathlib import Path

import pytest

FIXTURES = sorted((Path(__file__).parent / "fixtures").iterdir())
FORBIDDEN = {
    "auth_token": re.compile(r"auth_token"),
    "ct0 with a value": re.compile(r"""\bct0["']?\s*[=:]\s*["']?[\w-]{6,}"""),
    "a cookie header": re.compile(r"(?i)\bcookie\s*:"),
    "visitorData": re.compile(r"visitorData"),
    "user:password@ URL": re.compile(r"://[^/\s\"'@:]+:[^/\s\"'@]+@"),
    "a signed caption URL": re.compile(r"[?&](?:signature|sig|expire|pot)="),
    "an IPv4 address in a query": re.compile(r"[?&]ip=\d"),
}


@pytest.mark.parametrize("path", FIXTURES, ids=lambda p: p.name)
def test_fixture_holds_no_credentials_or_session_tokens(path):
    text = path.read_text(encoding="utf-8", errors="replace")

    found = [name for name, pattern in FORBIDDEN.items() if pattern.search(text)]

    assert found == [], f"{path.name} holds: {found}"


def test_the_scan_sees_the_social_fixtures_it_is_meant_to_guard():
    names = {path.name for path in FIXTURES}

    assert {"x_timeline_uknf.json", "youtube_channel_uknf.html", "youtube_watch_uknf.html"} <= names
