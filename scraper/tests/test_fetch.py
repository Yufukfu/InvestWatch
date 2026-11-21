import tempfile
import time
from pathlib import Path

import pytest
from noble_tls import Session
from noble_tls.exceptions.exceptions import TLSClientException

import iw_scraper.fetch as fetch_module
from iw_scraper.config import fetch_settings
from iw_scraper.fetch import MAX_REDIRECTS, FetchFailure, Identity, _transport_failure, fetch
from iw_scraper.parsing import parse_page
from iw_scraper.proxy import PER_REQUEST, ProxyRotator
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
    assert failure.http_status == 503
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






@pytest.mark.parametrize("status", [403, 429])
async def test_forbidden_and_rate_limited_are_blocked(stub, status):
    stub.route("/b", status=status, body=b"<p>denied</p>")

    failure = await failure_of(stub.url("/b"), IDENTITY, None)

    assert failure.reason is Reason.BLOCKED
    assert failure.http_status == status
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

    await fetch("http://example.test/ok", IDENTITY, ProxyRotator([stub.url("/")], PER_REQUEST, 90.0).start_run(), guard=guard)

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


async def test_large_page_that_embeds_a_captcha_widget_is_not_a_block(stub):
    widget = b'<form><div class="g-recaptcha" data-sitekey="k"></div></form>'
    stub.route("/contact", body=b"<html><body><p>" + b"tresc " * 6000 + b"</p>" + widget + b"</body></html>")

    result = await fetch(stub.url("/contact"), IDENTITY, None)

    assert result.status == 200


async def test_small_page_with_a_captcha_widget_is_a_block(stub):
    stub.route("/c", body=b'<html><body><div class="g-recaptcha"></div></body></html>')

    failure = await failure_of(stub.url("/c"), IDENTITY, None)

    assert failure.reason is Reason.BLOCKED


@pytest.mark.parametrize("url", ["http://user:pw@example.pl/x", "http://:pw@example.pl/x", "http://user@example.pl/x"])
async def test_url_with_credentials_is_refused_without_a_request(url):
    failure = await failure_of(url, IDENTITY, None)

    assert failure.reason is Reason.BLOCKED_TARGET
    assert "pw" not in failure.detail


async def test_redirect_to_a_url_with_credentials_is_refused(stub):
    stub.route("/a", status=302, headers={"Location": "http://user:pw@example.pl/x"}, content_type=None)

    failure = await failure_of(stub.url("/a"), IDENTITY, None)

    assert failure.reason is Reason.BLOCKED_TARGET
    assert len(stub.requests) == 1


@pytest.mark.parametrize("location", ["file:///etc/passwd", "ftp://example.pl/x", "javascript:alert(1)"])
async def test_redirect_to_a_non_http_scheme_is_refused(stub, location):
    stub.route("/a", status=302, headers={"Location": location}, content_type=None)

    failure = await failure_of(stub.url("/a"), IDENTITY, None)

    assert failure.reason is Reason.BLOCKED_TARGET
    assert len(stub.requests) == 1


async def test_scheme_relative_redirect_is_resolved_and_shown_to_the_guard(stub):
    stub.route("/a", status=302, headers={"Location": "//other.test/x"}, content_type=None)
    asked: list[str] = []

    async def guard(url: str) -> str | None:
        asked.append(url)
        if "other.test" in url:
            raise FetchFailure(Reason.BLOCKED_TARGET, "refused")
        return None

    failure = await failure_of(stub.url("/a"), IDENTITY, None, guard=guard)

    assert failure.reason is Reason.BLOCKED_TARGET
    assert asked[-1] == "http://other.test/x"


async def test_library_errors_other_than_tls_exceptions_become_http_error_without_credentials(monkeypatch):
    class Exploding(Session):
        async def execute_request(self, method, url, **kwargs):
            raise ValueError("bad payload for http://user:secret@proxy:8080")

    monkeypatch.setattr(fetch_module, "Session", Exploding)

    failure = await failure_of("http://example.pl/", IDENTITY, None)

    assert failure.reason is Reason.HTTP_ERROR
    assert "secret" not in failure.detail


async def test_a_failing_session_close_does_not_hide_the_real_outcome(stub, monkeypatch):
    class BadClose(Session):
        async def close(self):
            raise RuntimeError("close failed")

    monkeypatch.setattr(fetch_module, "Session", BadClose)
    stub.route("/missing", status=404, body=b"nope")

    failure = await failure_of(stub.url("/missing"), IDENTITY, None)

    assert failure.reason is Reason.HTTP_ERROR
    assert "404" in failure.detail


@pytest.mark.parametrize("size, blocked", [(20_000, True), (20_001, False)])
async def test_marker_scan_applies_up_to_the_size_threshold(stub, size, blocked):
    widget = b'<div class="g-recaptcha"></div>'
    stub.route("/edge", body=widget + b"x" * (size - len(widget)))

    if blocked:
        assert (await failure_of(stub.url("/edge"), IDENTITY, None)).reason is Reason.BLOCKED
    else:
        assert (await fetch(stub.url("/edge"), IDENTITY, None)).status == 200


async def test_a_failed_close_is_logged_without_credentials(stub, monkeypatch, caplog):
    class BadClose(Session):
        async def close(self):
            raise RuntimeError("close failed for http://user:secret@proxy:8080")

    monkeypatch.setattr(fetch_module, "Session", BadClose)
    stub.route("/ok", body=PAGE.encode())

    with caplog.at_level("WARNING", logger="iw_scraper.fetch"):
        await fetch(stub.url("/ok"), IDENTITY, None)

    assert "closing the session failed" in caplog.text
    assert "secret" not in caplog.text


@pytest.mark.parametrize("status, reason", [(429, Reason.BLOCKED), (503, Reason.HTTP_ERROR), (403, Reason.BLOCKED)])
async def test_a_failure_carries_the_retry_after_the_source_sent(stub, status, reason):
    stub.route("/slow", status=status, body=b"later", headers={"Retry-After": "30"})

    with pytest.raises(FetchFailure) as caught:
        await fetch(stub.url("/slow"), IDENTITY, None)

    assert caught.value.reason is reason
    assert caught.value.retry_after == "30"


async def test_a_failure_without_retry_after_carries_none(stub):
    stub.route("/slow", status=429, body=b"later")

    with pytest.raises(FetchFailure) as caught:
        await fetch(stub.url("/slow"), IDENTITY, None)

    assert caught.value.retry_after is None


async def test_a_failure_on_a_redirect_target_carries_that_hops_retry_after(stub):
    stub.route("/start", status=302, headers={"Location": "/slow", "Retry-After": "999"}, content_type=None)
    stub.route("/slow", status=429, body=b"later", headers={"Retry-After": "45"})

    with pytest.raises(FetchFailure) as caught:
        await fetch(stub.url("/start"), IDENTITY, None)

    assert caught.value.retry_after == "45"


def test_fetch_settings_default_to_20_seconds_and_5_mib(monkeypatch):
    monkeypatch.delenv("FETCH_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("FETCH_MAX_BYTES", raising=False)

    assert fetch_settings() == (20.0, 5 * 1024 * 1024)


def test_fetch_settings_read_the_environment(monkeypatch):
    monkeypatch.setenv("FETCH_TIMEOUT_SECONDS", "7.5")
    monkeypatch.setenv("FETCH_MAX_BYTES", "1000")

    assert fetch_settings() == (7.5, 1000)


@pytest.mark.parametrize(
    "name, value",
    [
        ("FETCH_TIMEOUT_SECONDS", "0"),
        ("FETCH_TIMEOUT_SECONDS", "inf"),
        ("FETCH_TIMEOUT_SECONDS", "nan"),
        ("FETCH_TIMEOUT_SECONDS", "abc"),
        ("FETCH_MAX_BYTES", "0"),
        ("FETCH_MAX_BYTES", "-5"),
        ("FETCH_MAX_BYTES", "2.5"),
        ("FETCH_MAX_BYTES", "abc"),
    ],
)
def test_unusable_fetch_settings_are_refused_by_name(monkeypatch, name, value):
    monkeypatch.setenv(name, value)

    with pytest.raises(ValueError, match=name):
        fetch_settings()


async def test_a_redirect_location_with_a_space_is_percent_encoded(stub):
    stub.route("/start", status=302, headers={"Location": "/menu page"})
    stub.route("/menu%20page", body=PAGE.encode(), content_type="text/html; charset=utf-8")

    result = await fetch(stub.url("/start"), IDENTITY, None)

    assert result.url == stub.url("/menu%20page")
