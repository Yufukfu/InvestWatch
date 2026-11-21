import random
import re
import socket
import threading
from dataclasses import replace

import pytest
from noble_tls import Client

from iw_scraper.fetch import Identity, fetch
from iw_scraper.identities import CHROME_VERSION, TABLE, check_pairing, draw_identity, load_table

PAGE = b"<html><body><p>ok</p></body></html>"


class RawStub:
    """A socket server that records each request's header lines exactly as they arrive."""

    def __init__(self) -> None:
        self.requests: list[list[str]] = []
        self._sock = socket.socket()
        self._sock.bind(("127.0.0.1", 0))
        self._sock.listen(5)
        self.port = self._sock.getsockname()[1]
        threading.Thread(target=self._serve, daemon=True).start()

    def _serve(self) -> None:
        while True:
            try:
                conn, _ = self._sock.accept()
            except OSError:
                return
            with conn:
                data = b""
                while b"\r\n\r\n" not in data:
                    chunk = conn.recv(4096)
                    if not chunk:
                        break
                    data += chunk
                lines = data.decode("latin-1").split("\r\n\r\n")[0].split("\r\n")
                self.requests.append(lines[1:])  # drop the request line
                head = f"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nContent-Length: {len(PAGE)}\r\nConnection: close\r\n\r\n"
                conn.sendall(head.encode() + PAGE)

    def close(self) -> None:
        self._sock.close()


@pytest.fixture
def raw():
    server = RawStub()
    yield server
    server.close()


def header(identity: Identity, name: str) -> str:
    return dict(identity.headers)[name]


def with_header(identity: Identity, name: str, value: str) -> Identity:
    return replace(identity, headers=tuple((n, value if n == name else v) for n, v in identity.headers))


def without_header(identity: Identity, name: str) -> Identity:
    return replace(identity, headers=tuple((n, v) for n, v in identity.headers if n != name))


CHROME = TABLE[0]


@pytest.mark.parametrize("identity", TABLE, ids=lambda i: header(i, "sec-ch-ua-platform"))
async def test_header_names_arrive_in_the_profile_order(raw, identity):
    await fetch(f"http://127.0.0.1:{raw.port}/", identity, None)

    sent = [line.split(":", 1) for line in raw.requests[0]]
    names = [name.lower() for name, _ in sent]
    expected = [name for name, _ in identity.headers]
    assert names[: len(expected)] == expected
    assert dict((n.lower(), v.strip()) for n, v in sent)["user-agent"] == header(identity, "user-agent")


def test_user_agent_client_hints_and_tls_profile_share_one_version():
    for identity in TABLE:
        assert f"Chrome/{CHROME_VERSION}." in header(identity, "user-agent")
        assert f'v="{CHROME_VERSION}"' in header(identity, "sec-ch-ua")
        assert identity.tls_profile.startswith(f"CHROME_{CHROME_VERSION}")


def test_every_header_name_is_lowercase_and_listed_once():
    for identity in TABLE:
        names = [n for n, _ in identity.headers]
        assert names == [n.lower() for n in names]
        assert len(names) == len(set(names))


def test_the_shipped_table_passes_its_own_pairing_check():
    assert load_table(TABLE) == TABLE


MISMATCHES = [
    ("family", replace(CHROME, tls_profile="FIREFOX_147"), "different browsers"),
    (
        "ua-version",
        with_header(CHROME, "user-agent", header(CHROME, "user-agent").replace("Chrome/146", "Chrome/131")),
        "user agent version",
    ),
    ("client-hints-version", with_header(CHROME, "sec-ch-ua", '"Chromium";v="131", "Google Chrome";v="131"'), "sec-ch-ua"),
    (
        "ua-family",
        with_header(CHROME, "user-agent", "Mozilla/5.0 (X11; Linux x86_64; rv:147.0) Gecko/20100101 Firefox/147.0"),
        "different browsers",
    ),
    ("unrecognised-ua", with_header(CHROME, "user-agent", "curl/8.4.0"), "unrecognised"),
    ("no-ua", without_header(CHROME, "user-agent"), "no user-agent"),
    ("no-hints", without_header(CHROME, "sec-ch-ua"), "sec-ch-ua"),
    (
        "uppercase-name",
        replace(CHROME, headers=(("User-Agent", header(CHROME, "user-agent")),) + CHROME.headers[1:]),
        "lowercase",
    ),
    ("duplicate-name", replace(CHROME, headers=CHROME.headers + (("accept", "*/*"),)), "listed once"),
    ("unknown-profile", replace(CHROME, tls_profile="CHROME_999"), "unknown TLS profile"),
    (
        "not-a-browser-profile",
        replace(CHROME, tls_profile=next(n for n in Client.__members__ if not re.match(r"^(CHROME|FIREFOX|SAFARI)_\d+", n))),
        "cannot read a browser",
    ),
]


@pytest.mark.parametrize("broken, message", [(b, m) for _, b, m in MISMATCHES], ids=[i for i, _, _ in MISMATCHES])
def test_a_mismatched_entry_is_rejected_at_load_for_its_own_reason(broken, message):
    with pytest.raises(ValueError, match=message):
        load_table((CHROME, broken))


def test_an_empty_table_is_refused():
    with pytest.raises(ValueError, match="empty"):
        load_table(())


def test_a_stale_profile_is_rejected_even_when_consistent():
    ua = header(CHROME, "user-agent").replace("Chrome/146", "Chrome/131")
    hints = header(CHROME, "sec-ch-ua").replace('v="146"', 'v="131"')
    stale = with_header(with_header(replace(CHROME, tls_profile="CHROME_131"), "user-agent", ua), "sec-ch-ua", hints)

    with pytest.raises(ValueError, match="stale|older"):
        check_pairing(stale)


def test_firefox_entry_must_not_send_client_hints():
    firefox = Identity(
        "FIREFOX_147",
        (
            ("user-agent", "Mozilla/5.0 (X11; Linux x86_64; rv:147.0) Gecko/20100101 Firefox/147.0"),
            ("sec-ch-ua", '"Chromium";v="147"'),
        ),
    )

    with pytest.raises(ValueError):
        check_pairing(firefox)


def test_an_identity_is_drawn_from_the_table():
    assert draw_identity() in TABLE


def test_draws_are_random_and_a_seeded_generator_is_reproducible():
    first = [draw_identity(random.Random(7)) for _ in range(3)]
    spread = {draw_identity(random.Random(seed)) for seed in range(60)}

    assert first[0] == first[1] == first[2]
    assert len(spread) == len(TABLE)


async def test_no_cookie_is_carried_into_the_next_run(stub):
    stub.route("/set", body=PAGE, headers={"Set-Cookie": "sid=abc; Path=/"})
    stub.route("/page", body=PAGE)

    await fetch(stub.url("/set"), CHROME, None)
    await fetch(stub.url("/page"), CHROME, None)

    assert "cookie" not in {name.lower() for name, _ in stub.requests[1].headers}


async def test_cookies_set_during_a_run_are_kept_within_that_run(stub):
    stub.route("/set", status=302, headers={"Set-Cookie": "sid=abc; Path=/", "Location": "/page"}, content_type=None)
    stub.route("/page", body=PAGE)

    await fetch(stub.url("/set"), CHROME, None)

    assert dict((n.lower(), v) for n, v in stub.requests[1].headers)["cookie"] == "sid=abc"
