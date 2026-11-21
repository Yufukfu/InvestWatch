import asyncio

import pytest

from iw_scraper.config import target_settings
from iw_scraper.fetch import FetchFailure, fetch
from iw_scraper.identities import TABLE
from iw_scraper.targets import AddressGuard, UrlGuard, select_sources, target_guard
from iw_scraper.types import Reason, Source

PUBLIC = "93.184.216.34"
PUBLIC_HEX = "5db8:d822"  # the same address in the last 32 bits of an IPv6 one


def source(url: str = "https://example.pl/", *, active=True, platform="web", cron="0 * * * *", kind="official", id="s") -> Source:
    return Source(
        id=id, name=id, platform=platform, url=url, source_kind=kind,
        target_modules=("m1",), active=active, schedule_cron=cron,
    )


def refused(call, *args, **kwargs) -> FetchFailure:
    with pytest.raises(FetchFailure) as caught:
        call(*args, **kwargs)
    assert caught.value.reason is Reason.BLOCKED_TARGET
    return caught.value


async def refused_async(awaitable) -> FetchFailure:
    with pytest.raises(FetchFailure) as caught:
        await awaitable
    assert caught.value.reason is Reason.BLOCKED_TARGET
    return caught.value


# ---- 5.1 selection -------------------------------------------------------------------------------------------


def test_an_inactive_source_is_never_selected():
    assert select_sources([source(active=False)], scheduled=False) == []


def test_a_source_of_another_platform_is_skipped_silently():
    assert select_sources([source(platform="facebook")], scheduled=False) == []


def test_a_manual_only_source_is_not_scheduled_but_can_be_run_by_hand():
    manual = source(cron=None)

    assert select_sources([manual], scheduled=True) == []
    assert select_sources([manual], scheduled=False) == [manual]


def test_selection_keeps_order_and_the_source_kind_of_each_record():
    first, second = source(id="a", kind="regulator"), source(id="b", kind="official")
    skipped = source(id="c", active=False)

    chosen = select_sources([first, skipped, second], scheduled=True)

    assert [(s.id, s.source_kind) for s in chosen] == [("a", "regulator"), ("b", "official")]


# ---- 5.2 URL guard -------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "allowed, url",
    [
        ("example.pl", "https://example.pl/page"),
        ("example.pl", "https://www.example.pl/page"),  # apex to www
        ("www.example.pl", "https://example.pl/page"),  # www to apex
        ("example.pl", "https://WWW.Example.PL/page"),
        ("example.pl", "http://example.pl/page"),
        ("Example.PL", "https://example.pl/page"),
        ("WWW.Example.PL", "https://example.pl/page"),
    ],
)
def test_hosts_on_the_list_and_their_www_twin_pass(allowed, url):
    UrlGuard([allowed]).check(url)


@pytest.mark.parametrize(
    "url",
    [
        "https://evil.example/",
        "https://example.pl.evil.example/",
        "https://notexample.pl/",
        "https://sub.example.pl/",
        "https://example.pl@evil.example/",
        "https://[::1]/",
    ],
)
def test_a_host_off_the_list_is_refused(url):
    refused(UrlGuard(["example.pl"]).check, url)


def test_configured_extra_hosts_are_on_the_list():
    UrlGuard(["example.pl", "cdn.example.org"]).check("https://cdn.example.org/a")


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd", "ftp://example.pl/x", "javascript:alert(1)", "//example.pl/x", "example.pl/x", "",
        "gopher://example.pl/", "http:///x", "https://:443/",
    ],
)
def test_only_http_and_https_are_fetched(url):
    refused(UrlGuard(["example.pl"]).check, url, enforce_host=False)


def test_the_source_url_skips_the_host_list_but_not_the_scheme_or_port_checks():
    guard = UrlGuard(["other.pl"])

    guard.check("https://example.pl/", enforce_host=False)
    refused(guard.check, "file:///etc/passwd", enforce_host=False)
    refused(guard.check, "https://example.pl:6379/", enforce_host=False)


@pytest.mark.parametrize(
    "url", ["http://example.pl/", "https://example.pl/", "https://example.pl:443/", "http://example.pl:80/", "http://example.pl:443/"]
)
def test_default_and_explicit_web_ports_pass(url):
    UrlGuard(["example.pl"]).check(url)


@pytest.mark.parametrize(
    "url",
    [
        "https://example.pl:6379/",
        "http://example.pl:8080/",
        "https://example.pl:8443/",
        "https://example.pl:0/",
        "https://example.pl:99999/",
        "https://example.pl:abc/",
    ],
)
def test_other_ports_are_refused(url):
    refused(UrlGuard(["example.pl"]).check, url)


def test_a_configured_extra_port_passes_and_a_default_port_no_longer_listed_is_refused():
    UrlGuard(["example.pl"], allowed_ports=[80, 443, 8443]).check("https://example.pl:8443/")
    refused(UrlGuard(["example.pl"], allowed_ports=[8443]).check, "https://example.pl/")


def test_a_scheme_uses_its_own_default_port():
    UrlGuard(["example.pl"], allowed_ports=[80]).check("http://example.pl/")
    refused(UrlGuard(["example.pl"], allowed_ports=[80]).check, "https://example.pl/")
    UrlGuard(["example.pl"], allowed_ports=[443]).check("https://example.pl/")
    refused(UrlGuard(["example.pl"], allowed_ports=[443]).check, "http://example.pl/")


def test_the_guard_applies_to_a_canonical_url_and_a_scraped_link_alike():
    guard = UrlGuard(["example.pl"])

    guard.check("https://www.example.pl/canonical")
    refused(guard.check, "https://attacker.example/link")
    refused(guard.check, "https://example.pl:6379/link")


def test_a_refusal_never_echoes_credentials_or_the_query():
    failure = refused(UrlGuard(["example.pl"]).check, "https://user:secret@evil.example/path?token=abc")

    assert "secret" not in failure.detail and "token" not in failure.detail


def test_a_foreign_host_is_named_in_the_refusal():
    failure = refused(UrlGuard(["example.pl"]).check, "https://evil.example/path")

    assert "evil.example" in failure.detail


def test_a_url_with_credentials_is_refused_even_on_an_allowed_host():
    failure = refused(UrlGuard(["example.pl"]).check, "https://user:secret@example.pl/")

    assert "secret" not in failure.detail


def test_the_list_is_built_from_collectable_sources_only():
    sources = [source("https://one.pl/"), source("https://two.pl/", active=False), source("https://three.pl/", platform="x")]
    guard = UrlGuard.for_sources(sources, extra_hosts=["extra.pl"])

    guard.check("https://www.one.pl/")
    guard.check("https://extra.pl/")
    refused(guard.check, "https://two.pl/")
    refused(guard.check, "https://three.pl/")


# ---- 5.3 address guard ---------------------------------------------------------------------------------------


class Resolver:
    def __init__(self, *answers: list[str] | Exception) -> None:
        self.answers = list(answers)
        self.calls: list[str] = []

    async def __call__(self, host: str) -> list[str]:
        self.calls.append(host)
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer


async def test_a_public_address_passes_and_is_the_one_to_connect_to():
    resolver = Resolver([PUBLIC])

    assert await AddressGuard(resolver).check("example.pl") == PUBLIC


@pytest.mark.parametrize(
    "address",
    [
        "127.0.0.1", "::1", "10.0.0.5", "169.254.169.254", "::ffff:127.0.0.1", "0.0.0.0", "::",
        "192.168.1.1", "172.16.0.1", "fe80::1", "fc00::1", "fd12:3456::1", "224.0.0.1", "ff02::1",
        "100.64.0.1", "::ffff:10.0.0.5", "::ffff:169.254.169.254",
        "64:ff9b::7f00:1", "64:ff9b::a9fe:a9fe", "64:ff9b::a00:5", "2002:7f00:1::", "2002:a9fe:a9fe::",
        "::127.0.0.1", "::10.0.0.5", "fec0::1", "192.0.0.9", "192.0.0.1", f"2002:{PUBLIC_HEX}::",
    ],
)
async def test_an_internal_answer_is_refused(address):
    await refused_async(AddressGuard(Resolver([address])).check("example.pl"))


async def test_an_ipv4_mapped_public_address_is_still_public():
    mapped = f"::ffff:{PUBLIC}"

    assert await AddressGuard(Resolver([mapped])).check("example.pl") == mapped


@pytest.mark.parametrize("address", [f"64:ff9b::{PUBLIC_HEX}", "2606:4700::1111"])
async def test_a_translated_public_address_and_a_public_ipv6_address_pass(address):
    assert await AddressGuard(Resolver([address])).check("example.pl") == address


class Hung:
    async def __call__(self, host: str) -> list[str]:
        await asyncio.sleep(3600)
        return []


async def test_a_resolver_that_never_answers_is_a_transport_failure(monkeypatch):
    monkeypatch.setattr("iw_scraper.targets.RESOLVE_TIMEOUT_SECONDS", 0.2)

    with pytest.raises(FetchFailure) as caught:
        await asyncio.wait_for(AddressGuard(Hung()).check("example.pl"), 2)  # the outer limit only stops a mutant

    assert caught.value.reason is Reason.HTTP_ERROR


async def test_an_answer_that_is_not_an_address_is_refused():
    await refused_async(AddressGuard(Resolver(["not-an-ip"])).check("example.pl"))


async def test_the_first_answer_is_the_one_to_connect_to():
    other = "93.184.216.35"

    assert await AddressGuard(Resolver([PUBLIC, other])).check("example.pl") == PUBLIC


async def test_one_internal_answer_among_public_ones_refuses_the_host():
    await refused_async(AddressGuard(Resolver([PUBLIC, "127.0.0.1"])).check("example.pl"))


async def test_a_literal_internal_address_is_refused_without_a_lookup():
    resolver = Resolver()

    for host in ("127.0.0.1", "::1", "::ffff:127.0.0.1", "169.254.169.254"):
        await refused_async(AddressGuard(resolver).check(host))

    assert resolver.calls == []


async def test_a_literal_public_address_passes_without_a_lookup():
    resolver = Resolver()

    assert await AddressGuard(resolver).check(PUBLIC) == PUBLIC
    assert resolver.calls == []


@pytest.mark.parametrize("host", ["redis", "postgres", "localhost", "minio", "Redis", "redis."])
async def test_bare_service_names_are_refused_without_a_lookup(host):
    resolver = Resolver()

    await refused_async(AddressGuard(resolver).check(host))

    assert resolver.calls == []


async def test_hosts_listed_as_internal_are_refused_whatever_their_case():
    guard = AddressGuard(Resolver(), internal_hosts=["Api.Internal.example.pl"])

    await refused_async(guard.check("api.internal.EXAMPLE.pl"))


async def test_an_empty_answer_is_refused():
    await refused_async(AddressGuard(Resolver([])).check("example.pl"))


async def test_a_failed_lookup_is_a_transport_failure_not_a_refusal():
    with pytest.raises(FetchFailure) as caught:
        await AddressGuard(Resolver(OSError("no such host"))).check("example.pl")

    assert caught.value.reason is Reason.HTTP_ERROR


# ---- combined guard for fetch() ------------------------------------------------------------------------------


async def test_the_guard_returns_the_checked_address_and_resolves_once():
    resolver = Resolver([PUBLIC], ["127.0.0.1"])  # a second lookup would be the rebinding answer
    guard = target_guard(UrlGuard(["example.pl"]), AddressGuard(resolver), "https://example.pl/")

    assert await guard("https://example.pl/") == PUBLIC
    assert resolver.calls == ["example.pl"]


async def test_the_source_url_is_exempt_from_the_host_list_but_a_redirect_is_not():
    guard = target_guard(UrlGuard(["other.pl"]), AddressGuard(Resolver([PUBLIC], [PUBLIC])), "https://example.pl/start")

    assert await guard("https://example.pl/start") == PUBLIC
    await refused_async(guard("https://example.pl/elsewhere"))


async def test_a_redirect_to_an_internal_literal_or_a_foreign_host_makes_no_lookup():
    resolver = Resolver()
    guard = target_guard(UrlGuard(["example.pl"]), AddressGuard(resolver), "https://example.pl/")

    for url in ("http://127.0.0.1/", "https://evil.example/", "https://example.pl:6379/", "file:///etc/passwd"):
        await refused_async(guard(url))

    assert resolver.calls == []


async def test_fetch_stops_at_a_redirect_to_a_host_off_the_list(stub):
    start = stub.url("/start")
    stub.route("/start", status=302, headers={"Location": f"http://localhost:{stub.port}/next"}, content_type=None)
    stub.route("/next", body=b"<html><body>x</body></html>")
    urls = UrlGuard(["127.0.0.1"], allowed_ports=[stub.port])

    async def guard(url: str):
        urls.check(url, enforce_host=url != start)  # the address check is covered above; the stub is on loopback

    with pytest.raises(FetchFailure) as caught:
        await fetch(start, TABLE[0], None, guard=guard)

    assert caught.value.reason is Reason.BLOCKED_TARGET
    assert [r.path for r in stub.requests] == ["/start"]


async def test_apex_to_www_is_followed():
    guard = target_guard(UrlGuard(["example.pl"]), AddressGuard(Resolver([PUBLIC])), "https://example.pl/")

    assert await guard("https://www.example.pl/") == PUBLIC


async def test_an_internal_source_url_is_refused_by_the_address_check():
    guard = target_guard(UrlGuard(["example.pl"]), AddressGuard(Resolver(["10.0.0.5"])), "https://example.pl/")

    await refused_async(guard("https://example.pl/"))


# ---- settings ------------------------------------------------------------------------------------------------


def test_settings_default_to_web_ports_and_no_extras(monkeypatch):
    for name in ("ALLOWED_PORTS", "COMPOSE_INTERNAL_HOSTS", "FETCH_EXTRA_HOSTS"):
        monkeypatch.delenv(name, raising=False)

    assert target_settings() == ((80, 443), frozenset(), frozenset())


def test_settings_read_the_environment(monkeypatch):
    monkeypatch.setenv("ALLOWED_PORTS", "80, 443,8443")
    monkeypatch.setenv("COMPOSE_INTERNAL_HOSTS", "Api.Internal, db.internal")
    monkeypatch.setenv("FETCH_EXTRA_HOSTS", "cdn.example.org,WWW.Other.pl")

    ports, internal, extras = target_settings()

    assert ports == (80, 443, 8443)
    assert internal == frozenset({"api.internal", "db.internal"})
    assert extras == frozenset({"cdn.example.org", "other.pl"})


@pytest.mark.parametrize("value", ["abc", "0", "65536", "70000", "-1", "80,,x", "80.5"])
def test_unusable_ports_are_refused_by_name(monkeypatch, value):
    monkeypatch.setenv("ALLOWED_PORTS", value)

    with pytest.raises(ValueError, match="ALLOWED_PORTS"):
        target_settings()


def test_settings_keep_internal_hosts_as_written_and_drop_duplicate_ports(monkeypatch):
    monkeypatch.setenv("ALLOWED_PORTS", "80,443,80,65535")
    monkeypatch.setenv("COMPOSE_INTERNAL_HOSTS", "www.admin.internal")

    ports, internal, _ = target_settings()

    assert ports == (80, 443, 65535)
    assert internal == frozenset({"www.admin.internal"})


def test_an_empty_port_list_is_refused(monkeypatch):
    monkeypatch.setenv("ALLOWED_PORTS", " , ")

    with pytest.raises(ValueError, match="ALLOWED_PORTS"):
        target_settings()
