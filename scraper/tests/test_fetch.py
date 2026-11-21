import tempfile
import time
from pathlib import Path

import pytest
from noble_tls import Session
from noble_tls.exceptions.exceptions import TLSClientException

import iw_scraper.fetch as fetch_module
from iw_scraper.fetch import MAX_REDIRECTS, FetchFailure, Identity, _transport_failure, fetch
from iw_scraper.parsing import parse_page
from iw_scraper.types import Reason

IDENTITY = Identity(
    tls_profile="CHROME_146_PSK",
    headers=(
        ("accept-language", "pl-PL,pl;q=0.9"),
        ("user-agent", "iw-test-agent/1.0"),
        ("accept", "text/html"),
    ),
)
PAGE = "<html><head><title>T</title></head><body><p>zażółć</p></body></html>"


async def failure_of(*args, **kwargs) -> FetchFailure:
    with pytest.raises(FetchFailure) as err:
        await fetch(*args, **kwargs)
    return err.value


async def test_successful_fetch_returns_body_status_and_final_url(stub):
    stub.route("/ok", body=PAGE.encode())

    result = await fetch(stub.url("/ok"), IDENTITY, None)

    assert result.status == 200
    assert result.url == stub.url("/ok")
    assert result.body == PAGE.encode()


async def test_identity_headers_are_sent_instead_of_client_defaults(stub):
    stub.route("/ok", body=PAGE.encode())

    await fetch(stub.url("/ok"), IDENTITY, None)

    sent = dict(stub.requests[0].headers)
    assert sent["user-agent"] == "iw-test-agent/1.0"
    assert sent["accept-language"] == "pl-PL,pl;q=0.9"
    assert "noble-tls" not in sent["user-agent"]
    assert "Connection" not in sent
    names = [name for name, _ in stub.requests[0].headers]
    assert names[:3] == ["accept-language", "user-agent", "accept"]


@pytest.mark.parametrize(
    "content_type, markup",
    [
        ("text/html; charset=windows-1250", PAGE),
        ("text/html", '<meta charset="windows-1250">' + PAGE),
        ("text/html; charset=iso-8859-2", PAGE),
    ],
)
async def test_polish_charsets_decode_end_to_end(stub, content_type, markup):
    encoding = "iso-8859-2" if "8859" in content_type else "cp1250"
    stub.route("/pl", body=markup.encode(encoding), content_type=content_type)

    result = await fetch(stub.url("/pl"), IDENTITY, None)
    page = parse_page(result.body, result.content_type, result.url)

    assert "zażółć" in page.text


async def test_utf8_body_is_not_decoded_twice(stub):
    stub.route("/u", body=PAGE.encode(), content_type="text/html; charset=utf-8")

    result = await fetch(stub.url("/u"), IDENTITY, None)

    assert "zażółć" in parse_page(result.body, result.content_type, result.url).text


async def test_timeout_is_reported_as_timeout(stub):
    stub.route("/slow", body=PAGE.encode(), delay=2.0)
    started = time.monotonic()

    failure = await failure_of(stub.url("/slow"), IDENTITY, None, timeout=0.3)

    assert failure.reason is Reason.TIMEOUT
    assert time.monotonic() - started < 1.5


@pytest.mark.parametrize("status", [404, 500])
async def test_error_status_is_http_error(stub, status):
    stub.route("/e", status=status, body=b"nope")

    failure = await failure_of(stub.url("/e"), IDENTITY, None)

    assert failure.reason is Reason.HTTP_ERROR
    assert str(status) in failure.detail


async def test_fetch_never_retries(stub):
    stub.route("/down", status=503, body=b"busy")

    failure = await failure_of(stub.url("/down"), IDENTITY, None)

    assert failure.reason is Reason.HTTP_ERROR
    assert len(stub.requests) == 1


async def test_refused_connection_is_http_error():
    failure = await failure_of("http://127.0.0.1:1/", IDENTITY, None, timeout=2)

    assert failure.reason is Reason.HTTP_ERROR


async def test_oversized_body_is_parse_error_and_leaves_no_file(stub, tmp_path, monkeypatch):
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    stub.route("/big", body=b"<p>" + b"x" * 2000)

    failure = await failure_of(stub.url("/big"), IDENTITY, None, max_bytes=1000)

    assert failure.reason is Reason.PARSE_ERROR
    assert list(tmp_path.iterdir()) == []


async def test_body_at_the_cap_is_accepted(stub):
    body = b"<p>" + b"x" * 97
    stub.route("/edge", body=body)

    result = await fetch(stub.url("/edge"), IDENTITY, None, max_bytes=100)

    assert result.body == body


async def test_non_html_response_is_parse_error_and_leaves_no_file(stub, tmp_path, monkeypatch):
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    stub.route("/doc.pdf", body=b"%PDF-1.4", content_type="application/pdf")

    failure = await failure_of(stub.url("/doc.pdf"), IDENTITY, None)

    assert failure.reason is Reason.PARSE_ERROR
    assert list(tmp_path.iterdir()) == []


async def test_redirect_is_followed_hop_by_hop(stub):
    stub.route("/start", status=302, headers={"Location": "/next"}, content_type=None)
    stub.route("/next", status=301, headers={"Location": stub.url("/end")}, content_type=None)
    stub.route("/end", body=PAGE.encode())

    result = await fetch(stub.url("/start"), IDENTITY, None)

    assert result.url == stub.url("/end")
    assert [r.path for r in stub.requests] == ["/start", "/next", "/end"]


async def test_redirect_loop_gives_up_after_the_hop_limit(stub):
    stub.route("/loop", status=302, headers={"Location": "/loop"}, content_type=None)

    failure = await failure_of(stub.url("/loop"), IDENTITY, None)

    assert failure.reason is Reason.HTTP_ERROR
    assert len(stub.requests) == MAX_REDIRECTS + 1


async def test_redirect_without_location_is_http_error(stub):
    stub.route("/odd", status=302, content_type=None)

    failure = await failure_of(stub.url("/odd"), IDENTITY, None)

    assert failure.reason is Reason.HTTP_ERROR


async def test_guard_is_asked_about_every_hop(stub):
    stub.route("/a", status=302, headers={"Location": "/b"}, content_type=None)
    stub.route("/b", body=PAGE.encode())
    asked: list[str] = []

    async def guard(url: str) -> str | None:
        asked.append(url)
        return None

    await fetch(stub.url("/a"), IDENTITY, None, guard=guard)

    assert asked == [stub.url("/a"), stub.url("/b")]


async def test_guard_refusal_makes_no_request(stub):
    async def guard(url: str) -> str | None:
        raise FetchFailure(Reason.BLOCKED_TARGET, "refused")

    failure = await failure_of(stub.url("/a"), IDENTITY, None, guard=guard)

    assert failure.reason is Reason.BLOCKED_TARGET
    assert stub.requests == []


async def test_guard_refusal_on_a_redirect_hop_stops_the_chain(stub):
    stub.route("/a", status=302, headers={"Location": "/b"}, content_type=None)
    stub.route("/b", body=PAGE.encode())

    async def guard(url: str) -> str | None:
        if url.endswith("/b"):
            raise FetchFailure(Reason.BLOCKED_TARGET, "refused")
        return None

    failure = await failure_of(stub.url("/a"), IDENTITY, None, guard=guard)

    assert failure.reason is Reason.BLOCKED_TARGET
    assert [r.path for r in stub.requests] == ["/a"]


async def test_connection_goes_to_the_address_the_guard_returned(stub):
    stub.route("/ok", body=PAGE.encode())

    async def guard(url: str) -> str | None:
        return "127.0.0.1"

    # example.test does not resolve; only the pinned address can make this succeed
    result = await fetch(stub.url("/ok", host="example.test"), IDENTITY, None, guard=guard)

    assert result.status == 200
    assert dict(stub.requests[0].headers)["Host"] == f"example.test:{stub.port}"


async def test_unpinned_connection_to_an_unresolvable_host_fails(stub):
    stub.route("/ok", body=PAGE.encode())

    failure = await failure_of(stub.url("/ok", host="example.test"), IDENTITY, None, timeout=2)

    assert failure.reason is Reason.HTTP_ERROR
    assert stub.requests == []


@pytest.mark.parametrize("url", ["file:///etc/passwd", "ftp://example.pl/x", "javascript:alert(1)"])
async def test_non_http_scheme_is_refused_without_a_request(url):
    failure = await failure_of(url, IDENTITY, None)

    assert failure.reason is Reason.BLOCKED_TARGET


async def test_request_goes_through_the_proxy(stub):
    stub.route("/ok", body=PAGE.encode())

    result = await fetch("http://example.test/ok", IDENTITY, stub.url("/"))

    assert result.status == 200
    assert stub.requests[0].connect is True  # example.test does not resolve; only the proxy can serve it
    assert stub.requests[0].path == "example.test:80"
    assert stub.requests[1].path == "/ok"


async def test_proxy_credentials_never_appear_in_a_failure():
    failure = await failure_of(
        "http://example.test/ok", IDENTITY, "http://user:secret@127.0.0.1:1", timeout=2
    )

    assert failure.reason is Reason.HTTP_ERROR
    assert "secret" not in failure.detail


@pytest.mark.parametrize("status", [403, 429])
async def test_forbidden_and_rate_limited_are_blocked(stub, status):
    stub.route("/b", status=status, body=b"<p>denied</p>")

    failure = await failure_of(stub.url("/b"), IDENTITY, None)

    assert failure.reason is Reason.BLOCKED
    assert str(status) in failure.detail


@pytest.mark.parametrize(
    "marker",
    [
        '<div class="g-recaptcha" data-sitekey="k"></div>',
        '<div class="h-captcha"></div>',
        '<div class="cf-turnstile"></div>',
        '<script src="/cdn-cgi/challenge-platform/h/b/orchestrate.js"></script>',
        '<iframe src="https://geo.captcha-delivery.com/captcha/"></iframe>',
        '<div id="px-captcha"></div>',
    ],
)
async def test_captcha_page_served_with_200_is_blocked(stub, marker):
    stub.route("/c", body=f"<html><body><p>Verify you are human</p>{marker}</body></html>".encode())

    failure = await failure_of(stub.url("/c"), IDENTITY, None)

    assert failure.reason is Reason.BLOCKED
    assert "marker" in failure.detail


async def test_marker_match_ignores_case(stub):
    stub.route("/c", body=b'<html><body><p>x</p><DIV CLASS="G-ReCaptcha"></DIV></body></html>')

    failure = await failure_of(stub.url("/c"), IDENTITY, None)

    assert failure.reason is Reason.BLOCKED


async def test_empty_200_body_is_blocked(stub):
    stub.route("/empty", body=b"")

    failure = await failure_of(stub.url("/empty"), IDENTITY, None)

    assert failure.reason is Reason.BLOCKED
    assert "empty" in failure.detail


async def test_prose_that_mentions_captcha_is_not_a_block(stub):
    stub.route("/ok", body=b"<html><body><p>Ten artykul opisuje captcha i inne zabezpieczenia.</p></body></html>")

    result = await fetch(stub.url("/ok"), IDENTITY, None)

    assert result.status == 200


async def test_saved_knf_page_is_not_a_block(stub):
    stub.route("/knf", body=(Path(__file__).parent / "fixtures" / "knf_warnings.html").read_bytes())

    result = await fetch(stub.url("/knf"), IDENTITY, None)

    assert len(result.body) > 800_000


async def test_other_error_statuses_stay_http_errors(stub):
    stub.route("/gone", status=410, body=b"gone")

    failure = await failure_of(stub.url("/gone"), IDENTITY, None)

    assert failure.reason is Reason.HTTP_ERROR


@pytest.mark.parametrize(
    "marker",
    [
        '<script src="https://js.hcaptcha.com/1/api.js"></script>',
        '<div class="cf-chl-widget"></div>',
    ],
)
async def test_other_challenge_vendors_are_blocked(stub, marker):
    stub.route("/c", body=f"<html><body><p>x</p>{marker}</body></html>".encode())

    failure = await failure_of(stub.url("/c"), IDENTITY, None)

    assert failure.reason is Reason.BLOCKED


@pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
async def test_every_redirect_status_is_followed(stub, status):
    stub.route("/from", status=status, headers={"Location": "/to"}, content_type=None)
    stub.route("/to", body=PAGE.encode())

    result = await fetch(stub.url("/from"), IDENTITY, None)

    assert result.url == stub.url("/to")


async def test_body_one_byte_over_the_cap_is_refused(stub):
    stub.route("/over", body=b"<p>" + b"x" * 98)  # 101 bytes

    failure = await failure_of(stub.url("/over"), IDENTITY, None, max_bytes=100)

    assert failure.reason is Reason.PARSE_ERROR


async def test_response_without_content_type_is_accepted_and_reported_as_utf8_html(stub):
    stub.route("/bare", body=PAGE.encode(), content_type=None)

    result = await fetch(stub.url("/bare"), IDENTITY, None)

    assert result.content_type == "text/html; charset=utf-8"


async def test_unknown_tls_profile_is_a_configuration_error():
    with pytest.raises(ValueError):
        await fetch("http://example.pl/", Identity("CHROME_999", (("user-agent", "x"),)), None)


@pytest.mark.parametrize("url", ["http:///nohost", "http://example.pl:99999/x"])
async def test_url_without_host_or_with_bad_port_is_refused(url):
    failure = await failure_of(url, IDENTITY, None)

    assert failure.reason is Reason.BLOCKED_TARGET


class RecordingSession(Session):
    """Real session that notes what each request was given, then performs it."""

    calls: list[dict] = []
    stop_after_recording = False  # a malformed URL would abort the Go library, so some tests never send

    async def execute_request(self, method, url, **kwargs):
        RecordingSession.calls.append(
            {"url": url, "server_name": self.server_name_overwrite, "host": kwargs.get("request_host_override")}
        )
        if RecordingSession.stop_after_recording:
            raise TLSClientException("recorded, not sent")
        return await super().execute_request(method, url, **kwargs)


@pytest.fixture
def recorded(monkeypatch):
    RecordingSession.calls = []
    monkeypatch.setattr(RecordingSession, "stop_after_recording", False)
    monkeypatch.setattr(fetch_module, "Session", RecordingSession)
    return RecordingSession.calls


async def test_pinned_request_overrides_host_and_certificate_name(stub, recorded):
    stub.route("/ok", body=PAGE.encode())

    async def guard(url: str) -> str | None:
        return "127.0.0.1"

    await fetch(stub.url("/ok", host="example.test"), IDENTITY, None, guard=guard)

    assert recorded == [
        {"url": f"http://127.0.0.1:{stub.port}/ok", "server_name": "example.test", "host": f"example.test:{stub.port}"}
    ]


async def test_unpinned_request_overrides_nothing(stub, recorded):
    stub.route("/ok", body=PAGE.encode())

    await fetch(stub.url("/ok"), IDENTITY, None)

    assert recorded == [{"url": stub.url("/ok"), "server_name": None, "host": None}]


async def test_pin_is_cleared_again_on_a_hop_the_guard_does_not_pin(stub, recorded):
    stub.route("/a", status=302, headers={"Location": "/b"}, content_type=None)
    stub.route("/b", body=PAGE.encode())

    async def guard(url: str) -> str | None:
        return "127.0.0.1" if url.endswith("/a") else None

    await fetch(stub.url("/a", host="localhost"), IDENTITY, None, guard=guard)

    assert [c["server_name"] for c in recorded] == ["localhost", None]


async def test_ipv6_address_is_bracketed_in_the_request_url(stub, recorded, monkeypatch):
    monkeypatch.setattr(RecordingSession, "stop_after_recording", True)

    async def guard(url: str) -> str | None:
        return "::1"

    with pytest.raises(FetchFailure):  # the request is recorded, never sent
        await fetch(stub.url("/ok", host="example.test"), IDENTITY, None, guard=guard)

    assert recorded[0]["url"] == f"http://[::1]:{stub.port}/ok"
    assert recorded[0]["host"] == f"example.test:{stub.port}"


async def test_a_proxy_resolves_the_host_so_no_address_is_pinned(stub):
    stub.route("/ok", body=PAGE.encode())

    async def guard(url: str) -> str | None:
        return "127.0.0.2"

    await fetch("http://example.test/ok", IDENTITY, stub.url("/"), guard=guard)

    assert stub.requests[0].path == "example.test:80"


@pytest.mark.parametrize(
    "message",
    [
        'failed to do request: Get "http://x/": context deadline exceeded',
        "net/http: request canceled (Client.Timeout exceeded while reading body)",
    ],
)
def test_timeout_messages_map_to_timeout(message):
    assert _transport_failure(TLSClientException(message)).reason is Reason.TIMEOUT


def test_other_transport_messages_map_to_http_error():
    failure = _transport_failure(TLSClientException("dial tcp 127.0.0.1:1: connect: connection refused"))

    assert failure.reason is Reason.HTTP_ERROR


def test_transport_failure_text_never_carries_proxy_credentials():
    failure = _transport_failure(TLSClientException("proxyconnect tcp: dial http://user:secret@proxy:8080 failed"))

    assert "secret" not in failure.detail


async def test_error_status_with_a_non_html_body_is_still_http_error(stub):
    stub.route("/api", status=500, body=b'{"error": "boom"}', content_type="application/json")

    failure = await failure_of(stub.url("/api"), IDENTITY, None)

    assert failure.reason is Reason.HTTP_ERROR
