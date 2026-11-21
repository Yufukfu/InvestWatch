import random
from datetime import datetime, timedelta, timezone

import pytest

from iw_scraper.config import proxy_settings
from noble_tls.exceptions.exceptions import TLSClientException

from iw_scraper.fetch import FetchDeferred, FetchFailure, ProxyAuthFailure, _transport_failure, fetch
from iw_scraper.identities import TABLE
from iw_scraper.proxy import PER_REQUEST, PER_SESSION, ProxyChoice, ProxyRotator, proxy_identifier
from iw_scraper.types import Deferral, Reason

URLS = ["http://u1:secret1@p1.example:8080", "http://u2:secret2@p2.example:8080", "http://u3:secret3@p3.example:8080"]
START = datetime(2026, 11, 21, 12, 0, tzinfo=timezone.utc)
IDENTITY = TABLE[0]
PAGE = b"<html><body><p>ok</p></body></html>"


class Clock:
    def __init__(self) -> None:
        self.now = START

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += timedelta(seconds=seconds)


class First:
    """A 'random' generator that always takes the first candidate."""

    def choice(self, seq):
        return seq[0]


def rotator(urls=URLS, mode=PER_REQUEST, cooldown=90.0, clock=None, rng=None) -> ProxyRotator:
    return ProxyRotator(urls, mode, cooldown, clock or Clock(), rng or random.Random(1))


def picks(run, n):
    return [run.pick() for _ in range(n)]


def choice_of(url: str) -> ProxyChoice:
    return ProxyChoice(url, proxy_identifier(url))


def test_consecutive_requests_never_share_a_proxy():
    for seed in range(40):
        run = rotator(rng=random.Random(seed)).start_run()
        urls = [c.url for c in picks(run, 12)]
        assert all(a != b for a, b in zip(urls, urls[1:]))


def test_two_proxies_alternate():
    run = rotator(URLS[:2], rng=First()).start_run()

    assert [c.url for c in picks(run, 4)] == [URLS[0], URLS[1], URLS[0], URLS[1]]


def test_single_proxy_is_used_every_time():
    run = rotator(URLS[:1]).start_run()

    assert {c.url for c in picks(run, 5)} == {URLS[0]}


def test_unknown_rotation_mode_is_refused():
    with pytest.raises(ValueError):
        rotator(mode="sometimes")


def test_empty_list_means_direct_requests():
    assert rotator([]).start_run().pick() is None


def test_first_proxy_of_a_run_is_random():
    firsts = {rotator(rng=random.Random(seed)).start_run().pick().url for seed in range(60)}

    assert firsts == set(URLS)


def test_proxy_that_answered_407_is_skipped_until_the_cooldown_ends():
    clock = Clock()
    rot = rotator(clock=clock, rng=First())
    first = rot.start_run().pick()
    rot.penalize(first)

    during = {c.url for c in picks(rot.start_run(), 20)}
    clock.advance(89)
    just_before = {c.url for c in picks(rot.start_run(), 20)}
    clock.advance(1)
    after = rot.start_run().pick()

    assert first.url not in during and first.url not in just_before
    assert after.url == first.url


def test_every_proxy_cooling_gives_a_deferral_until_the_earliest_end():
    clock = Clock()
    rot = rotator(URLS[:2], clock=clock, rng=First())
    rot.penalize(choice_of(URLS[0]))  # cools until START + 90
    clock.advance(30)
    rot.penalize(choice_of(URLS[1]))  # cools until START + 120

    outcome = rot.start_run().pick()

    assert outcome == Deferral(until=START + timedelta(seconds=90))


def test_the_previous_proxy_is_not_repeated_when_every_other_proxy_is_cooling():
    rot = rotator(URLS[:2], rng=First())
    run = rot.start_run()
    assert run.pick().url == URLS[0]
    rot.penalize(choice_of(URLS[1]))

    outcome = run.pick()

    assert outcome == Deferral(until=START + timedelta(seconds=90))


def test_per_session_keeps_one_proxy_for_the_whole_run():
    run = rotator(mode=PER_SESSION).start_run()

    assert len({c.url for c in picks(run, 3)}) == 1


def test_per_session_moves_on_only_when_its_proxy_cools():
    rot = rotator(mode=PER_SESSION, rng=First())
    run = rot.start_run()
    first = run.pick()
    rot.penalize(first)

    second = run.pick()

    assert second.url != first.url
    assert run.pick().url == second.url


def test_identifier_is_stable_and_never_carries_credentials():
    ident = proxy_identifier(URLS[0])

    assert ident == proxy_identifier(URLS[0])
    assert ident != proxy_identifier(URLS[1])
    assert "secret1" not in ident and "u1" not in ident and "p1.example" not in ident


def test_settings_default_to_per_request_and_90_seconds(monkeypatch):
    for name in ("PROXY_LIST", "PROXY_ROTATION", "PROXY_COOLDOWN_SECONDS"):
        monkeypatch.delenv(name, raising=False)

    assert proxy_settings() == ([], PER_REQUEST, 90.0)


def test_settings_are_read_from_the_environment(monkeypatch):
    monkeypatch.setenv("PROXY_LIST", " http://a:1 ,http://b:2,, ")
    monkeypatch.setenv("PROXY_ROTATION", "per_session")
    monkeypatch.setenv("PROXY_COOLDOWN_SECONDS", "15")

    assert proxy_settings() == (["http://a:1", "http://b:2"], PER_SESSION, 15.0)


def test_unknown_rotation_mode_is_a_configuration_error(monkeypatch):
    monkeypatch.setenv("PROXY_ROTATION", "sometimes")

    with pytest.raises(ValueError):
        proxy_settings()


# --- through fetch, with stub servers acting as CONNECT proxies --------------------------------


async def test_request_is_served_through_the_picked_proxy_and_reports_its_identifier(stub):
    stub.route("/ok", body=PAGE)
    url = stub.url("/")

    result = await fetch("http://example.test/ok", IDENTITY, rotator([url]).start_run())

    assert result.status == 200
    assert result.proxy_id == proxy_identifier(url)
    assert stub.requests[0].connect is True


async def test_direct_request_reports_no_proxy(stub):
    stub.route("/ok", body=PAGE)

    result = await fetch(stub.url("/ok"), IDENTITY, rotator([]).start_run())

    assert result.proxy_id is None


async def test_407_cools_the_proxy_and_the_request_goes_through_another(stub, stub2):
    stub.connect_status = 407
    stub2.route("/ok", body=PAGE)
    rot = rotator([stub.url("/"), stub2.url("/")], rng=First())

    result = await fetch("http://example.test/ok", IDENTITY, rot.start_run())

    assert result.proxy_id == proxy_identifier(stub2.url("/"))
    assert [r.connect for r in stub.requests] == [True]  # tried once, then skipped
    assert rot.start_run().pick().url == stub2.url("/")  # still cooling for the next run


async def test_every_proxy_cooling_defers_without_a_request_or_an_error(stub):
    stub.route("/ok", body=PAGE)
    rot = rotator([stub.url("/")])
    rot.penalize(choice_of(stub.url("/")))

    with pytest.raises(FetchDeferred) as outcome:
        await fetch("http://example.test/ok", IDENTITY, rot.start_run())

    assert outcome.value.deferral == Deferral(until=START + timedelta(seconds=90))
    assert stub.requests == []


async def test_a_single_proxy_answering_407_defers_the_run(stub):
    stub.connect_status = 407
    rot = rotator([stub.url("/")])

    with pytest.raises(FetchDeferred):
        await fetch("http://example.test/ok", IDENTITY, rot.start_run())


async def test_proxy_credentials_never_appear_in_a_failure():
    rot = rotator(["http://user:secret@127.0.0.1:1"])

    with pytest.raises(FetchFailure) as failure:
        await fetch("http://example.test/ok", IDENTITY, rot.start_run(), timeout=2)

    assert failure.value.reason is Reason.HTTP_ERROR
    assert "secret" not in failure.value.detail


async def test_a_proxy_error_other_than_407_fails_the_request_and_does_not_cool_the_proxy(stub):
    stub.connect_status = 502
    rot = rotator([stub.url("/")], rng=First())

    with pytest.raises(FetchFailure) as failure:
        await fetch("http://example.test/ok", IDENTITY, rot.start_run())

    assert failure.value.reason is Reason.HTTP_ERROR
    assert rot.start_run().pick().url == stub.url("/")


def test_the_clients_407_wording_is_a_proxy_authentication_failure():
    message = 'failed to do request: Get "http://x/": Proxy responded with non 200 code: 407 Proxy Authentication Required'

    assert isinstance(_transport_failure(TLSClientException(message)), ProxyAuthFailure)


@pytest.mark.parametrize(
    "message",
    [
        'failed to do request: Get "http://example.pl/page407": dial tcp: connection refused',
        "failed to do request: Proxy responded with non 200 code: 502 Bad Gateway",
    ],
)
def test_other_errors_are_not_proxy_authentication_failures(message):
    assert not isinstance(_transport_failure(TLSClientException(message)), ProxyAuthFailure)


def test_duplicate_proxy_entries_count_as_one_proxy():
    run = rotator(["http://a:1", "http://a:1"]).start_run()

    assert {c.url for c in picks(run, 4)} == {"http://a:1"}


@pytest.mark.parametrize("value", ["0", "-5", "nan", "inf"])
def test_cooldown_setting_must_be_positive_and_finite(monkeypatch, value):
    monkeypatch.setenv("PROXY_COOLDOWN_SECONDS", value)

    with pytest.raises(ValueError):
        proxy_settings()


@pytest.mark.parametrize("value", [0, -1, float("nan"), float("inf")])
def test_rotator_refuses_a_cooldown_that_would_never_cool(value):
    with pytest.raises(ValueError):
        rotator(cooldown=value)


@pytest.mark.parametrize("entry", ["host:8080", "ftp://h:1", "http://", "not a url", "http://u:secret@"])
def test_malformed_proxy_entry_is_refused_without_echoing_it(monkeypatch, entry):
    monkeypatch.setenv("PROXY_LIST", entry)

    with pytest.raises(ValueError) as err:
        proxy_settings()

    assert entry not in str(err.value) and "secret" not in str(err.value)


@pytest.mark.parametrize("entry", ["http://p:1", "https://u:pw@p:2", "socks5://p:3"])
def test_supported_proxy_schemes_are_accepted(monkeypatch, entry):
    monkeypatch.setenv("PROXY_LIST", entry)

    assert proxy_settings()[0] == [entry]


@pytest.mark.parametrize(
    "echo",
    [
        "dial http://user:p%2Fa%20ss@proxy.example:8080 failed",
        "auth failed for password p/a ss",
        "auth failed for password p%2Fa%20ss",
    ],
)
def test_proxy_url_and_password_are_scrubbed_from_client_errors(echo):
    choice = choice_of("http://user:p%2Fa%20ss@proxy.example:8080")

    detail = _transport_failure(TLSClientException(echo), choice).detail

    assert "p/a ss" not in detail and "p%2Fa%20ss" not in detail
    assert "user:" not in detail
    assert choice.identifier in detail


def test_client_errors_without_a_proxy_are_left_readable():
    detail = _transport_failure(TLSClientException("dial tcp 10.0.0.1:80: connection refused"), None).detail

    assert "connection refused" in detail


async def test_a_407_answer_from_the_target_is_an_http_error_and_cools_no_proxy(stub, stub2):
    stub.route("/ok", status=407, body=b"the target wants credentials")
    stub2.route("/ok", body=PAGE)
    rot = rotator([stub.url("/"), stub2.url("/")], rng=First())

    with pytest.raises(FetchFailure) as failure:
        await fetch("http://example.test/ok", IDENTITY, rot.start_run())

    assert failure.value.reason is Reason.HTTP_ERROR
    assert [r.connect for r in stub.requests] == [True, False]  # one attempt, through one proxy
    assert stub2.requests == []
    assert {c.url for c in picks(rot.start_run(), 20)} == {stub.url("/"), stub2.url("/")}  # nothing is cooling


def test_a_proxy_choice_never_prints_its_url():
    choice = choice_of("http://user:p%2Fa%20ss@proxy.example:8080")

    assert "user" not in repr(choice) and "proxy.example" not in repr(choice)
    assert choice.identifier in repr(choice)


def test_a_url_quoted_in_a_client_error_loses_its_path_and_query():
    message = 'failed to do request: Get "http://127.0.0.1:1/secret/path?token=abc": dial tcp 127.0.0.1:1: refused'

    detail = _transport_failure(TLSClientException(message), None).detail

    assert "secret" not in detail and "token" not in detail
    assert "refused" in detail


async def test_a_407_without_a_proxy_is_just_an_http_error(stub):
    stub.route("/ok", status=407, body=b"nope")

    with pytest.raises(FetchFailure) as failure:
        await fetch(stub.url("/ok"), IDENTITY, None)

    assert failure.value.reason is Reason.HTTP_ERROR


async def test_a_failure_through_a_proxy_names_that_proxy(stub):
    stub.route("/ok", status=403, body=b"denied")
    url = stub.url("/")

    with pytest.raises(FetchFailure) as failure:
        await fetch("http://example.test/ok", IDENTITY, rotator([url]).start_run())

    assert failure.value.reason is Reason.BLOCKED
    assert failure.value.proxy_id == proxy_identifier(url)


async def test_a_transport_failure_through_a_proxy_names_that_proxy(stub):
    stub.connect_status = 502
    url = stub.url("/")

    with pytest.raises(FetchFailure) as failure:
        await fetch("http://example.test/ok", IDENTITY, rotator([url]).start_run())

    assert failure.value.proxy_id == proxy_identifier(url)


async def test_a_direct_failure_names_no_proxy(stub):
    stub.route("/ok", status=404, body=b"x")

    with pytest.raises(FetchFailure) as failure:
        await fetch(stub.url("/ok"), IDENTITY, None)

    assert failure.value.proxy_id is None


def test_a_quoted_url_holding_an_escaped_quote_is_scrubbed_to_its_end():
    message = r'failed to do request: Get "http://x.test/a\"b?token=abc": dial tcp: refused'

    detail = _transport_failure(TLSClientException(message), None).detail

    assert "token" not in detail and "a\\" not in detail
    assert "refused" in detail


def test_an_unterminated_quoted_url_is_scrubbed_to_the_end_of_the_message():
    message = 'failed to do request: Get "http://x.test/a?token=abc'

    detail = _transport_failure(TLSClientException(message), None).detail

    assert "token" not in detail and "x.test" not in detail


def test_a_run_reports_a_deferral_up_front_only_when_every_proxy_is_cooling():
    clock = Clock()
    rot = rotator(URLS[:2], clock=clock, rng=First())
    rot.penalize(choice_of(URLS[0]))
    assert rot.start_run().deferral() is None  # one proxy is still usable
    rot.penalize(choice_of(URLS[1]))

    assert rot.start_run().deferral() == Deferral(until=START + timedelta(seconds=90))


def test_a_run_without_proxies_never_defers():
    assert rotator([]).start_run().deferral() is None


def test_looking_for_a_deferral_does_not_use_up_the_rotation():
    rot = rotator(URLS[:2], rng=First())
    run = rot.start_run()

    run.deferral()

    assert run.pick().url == URLS[0]
