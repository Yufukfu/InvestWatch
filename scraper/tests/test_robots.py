import random
from datetime import datetime, timedelta, timezone

import pytest

from iw_scraper.fetch import MAX_REDIRECTS, FetchDeferred, FetchFailure, _new_session, close_session, fetch
from iw_scraper.identities import TABLE
from iw_scraper.proxy import ProxyRotator
from iw_scraper.robots import ROBOTS_AGENT, check_robots
from iw_scraper.types import Reason

IDENTITY = TABLE[0]
PLAIN = "text/plain; charset=utf-8"


def robots(stub, body: str = "", status: int = 200, **kwargs) -> None:
    stub.route("/robots.txt", status=status, body=body.encode(), content_type=PLAIN, **kwargs)


async def verdict(stub, path: str = "/warnings/page", proxy=None, **kwargs):
    return await check_robots(stub.url(path), IDENTITY, proxy, **kwargs)


async def test_a_disallowed_path_is_refused_and_only_robots_txt_is_requested(stub):
    robots(stub, "User-agent: *\nDisallow: /warnings/\n")

    result = await verdict(stub)

    assert result.allowed is False
    assert "disallow" in result.detail
    assert [r.path for r in stub.requests] == ["/robots.txt"]


async def test_a_path_the_file_permits_is_allowed(stub):
    robots(stub, "User-agent: *\nDisallow: /private/\n")

    assert (await verdict(stub, "/warnings/page")).allowed is True


async def test_a_rule_for_our_agent_applies_and_a_rule_for_another_agent_does_not(stub):
    robots(stub, f"User-agent: {ROBOTS_AGENT}\nDisallow: /\n\nUser-agent: SomeoneElse\nDisallow:\n")
    assert (await verdict(stub)).allowed is False

    robots(stub, "User-agent: SomeoneElse\nDisallow: /\n")
    assert (await verdict(stub)).allowed is True


@pytest.mark.parametrize(
    "rules, path, allowed",
    [
        ("Disallow: /*?session=", "/x?session=1", False),
        ("Disallow: /*?session=", "/x?page=2", True),
        ("Disallow: /private$", "/private", False),
        ("Disallow: /private$", "/private/x", True),
        ("Disallow: /docs/\nAllow: /docs/public/", "/docs/public/a", True),
        ("Disallow: /docs/\nAllow: /docs/public/", "/docs/secret", False),
    ],
)
async def test_rfc_9309_wildcards_end_anchors_and_longest_match_decide(stub, rules, path, allowed):
    robots(stub, f"User-agent: *\n{rules}\n")

    assert (await verdict(stub, path)).allowed is allowed


@pytest.mark.parametrize("status", [401, 403, 404, 410, 400])
async def test_an_unavailable_robots_txt_means_no_restrictions(stub, status):
    robots(stub, "User-agent: *\nDisallow: /\n", status=status)  # a body on an error page must be ignored

    result = await verdict(stub)

    assert result.allowed is True


@pytest.mark.parametrize("status", [429, 500, 502, 503])
async def test_a_busy_or_broken_robots_txt_disallows_the_path_for_this_run(stub, status):
    robots(stub, "", status=status)

    result = await verdict(stub)

    assert result.allowed is False
    assert str(status) in result.detail


async def test_a_robots_txt_that_times_out_disallows_the_path(stub):
    robots(stub, "", delay=1.5)

    result = await verdict(stub, timeout=0.3)

    assert result.allowed is False
    assert "unreachable" in result.detail


async def test_an_unreachable_host_disallows_the_path():
    result = await check_robots("http://127.0.0.1:1/page", IDENTITY, None, timeout=2.0)

    assert result.allowed is False


async def test_an_oversized_robots_txt_disallows_the_path(stub):
    robots(stub, "User-agent: *\nDisallow: /nothing\n" + "# padding\n" * 100)

    result = await verdict(stub, max_bytes=100)

    assert result.allowed is False


async def test_a_redirected_robots_txt_is_followed_to_the_file_that_decides(stub):
    stub.route("/robots.txt", status=301, headers={"Location": "/real-robots.txt"}, content_type=None)
    stub.route("/real-robots.txt", body=b"User-agent: *\nDisallow: /private/\n", content_type=PLAIN)
    assert (await verdict(stub)).allowed is True

    stub.route("/real-robots.txt", body=b"User-agent: *\nDisallow: /\n", content_type=PLAIN)
    assert (await verdict(stub)).allowed is False


async def test_a_redirect_loop_in_robots_txt_disallows_the_path(stub):
    stub.route("/robots.txt", status=302, headers={"Location": "/robots.txt"}, content_type=None)

    result = await verdict(stub)

    assert result.allowed is False
    assert len(stub.requests) == MAX_REDIRECTS + 1


async def test_robots_txt_is_requested_through_the_runs_proxy(stub):
    robots(stub, "")
    run = ProxyRotator([stub.url("/")], "per_request", 90.0).start_run()

    result = await check_robots("http://example.test/page", IDENTITY, run)

    assert result.allowed is True
    assert stub.requests[0].connect is True


async def test_when_every_proxy_is_cooling_the_deferral_is_not_turned_into_a_refusal(stub):
    now = datetime(2026, 11, 21, 12, 0, tzinfo=timezone.utc)
    rotator = ProxyRotator([stub.url("/")], "per_request", 90.0, clock=lambda: now, rng=random.Random(1))
    run = rotator.start_run()
    rotator.penalize(run.pick())

    with pytest.raises(FetchDeferred) as caught:
        await check_robots("http://example.test/page", IDENTITY, run)

    assert caught.value.deferral.until == now + timedelta(seconds=90)
    assert stub.requests == []


async def test_the_target_guard_still_applies_to_robots_txt(stub):
    async def refuse(url: str):
        raise FetchFailure(Reason.BLOCKED_TARGET, "refused")

    robots(stub, "")
    with pytest.raises(FetchFailure) as caught:
        await verdict(stub, guard=refuse)

    assert caught.value.reason is Reason.BLOCKED_TARGET
    assert stub.requests == []


async def test_robots_txt_is_read_from_the_origin_of_the_target(stub):
    robots(stub, "")

    await check_robots(stub.url("/deep/path?q=1#frag"), IDENTITY, None)

    assert [r.path for r in stub.requests] == ["/robots.txt"]


async def test_a_403_on_robots_txt_is_never_reported_as_a_block(stub):
    robots(stub, "", status=403)

    result = await verdict(stub)  # must return a verdict, not raise FetchFailure(BLOCKED)

    assert result.allowed is True


async def test_a_cookie_set_by_robots_txt_reaches_the_page_request_of_the_same_session(stub):
    robots(stub, "", headers={"Set-Cookie": "run=1"})
    stub.route(
        "/page",
        body=b"<html><body><p>ok</p></body></html>",
        content_type="text/html; charset=utf-8",
        headers={"Set-Cookie": "page=1"},
    )
    session = _new_session(IDENTITY)
    try:
        await check_robots(stub.url("/page"), IDENTITY, None, session=session)
        await fetch(stub.url("/page"), IDENTITY, None, session=session)
        page_request = stub.requests[-1]
        again = await check_robots(stub.url("/page"), IDENTITY, None, session=session)  # both left it open
    finally:
        await close_session(session)

    assert page_request.path == "/page"
    assert dict(page_request.headers).get("Cookie") == "run=1"
    assert again.allowed
    assert "page=1" in dict(stub.requests[-1].headers).get("Cookie", "")  # the page's cookie survived `fetch`
