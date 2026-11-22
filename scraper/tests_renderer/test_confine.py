import asyncio

import pytest

from iw_renderer.confine import CONTEXT_OPTIONS, RequestPolicy, confined_page
from iw_scraper.addresses import AddressChecker

SOURCE = "source.test"


@pytest.fixture
def policy(server, address_check):
    return RequestPolicy(SOURCE, address_check, allowed_ports=[server.port])


@pytest.fixture
async def page(browser, policy):
    context = await browser.new_context(**CONTEXT_OPTIONS)
    yield await confined_page(context, policy)
    await context.close()


async def settle() -> None:
    await asyncio.sleep(0.4)  # aborted requests have no event to await


# --- the verdict, without a browser ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url, kind, nav, why",
    [
        ("file:///etc/passwd", "document", True, "scheme not allowed"),
        ("ftp://source.test/x", "other", False, "scheme not allowed"),
        ("http://source.test:6379/", "xhr", False, "port not allowed"),
        ("http://source.test/", "media", False, "resource type not allowed"),
        ("http://source.test/", "eventsource", False, "resource type not allowed"),
        ("http://other.test/", "document", True, "navigation away"),
        ("http://169.254.169.254/latest/meta-data/", "xhr", False, "address not allowed"),
        ("http://10.0.0.5/", "image", False, "address not allowed"),
        ("http://minio/", "xhr", False, "internal host name"),
    ],
)
async def test_the_verdict_names_why_a_request_is_refused(address_check, url, kind, nav, why):
    policy = RequestPolicy(SOURCE, address_check, allowed_ports=[80, 443, 12345])

    reason = await policy.verdict(url, kind, is_navigation=nav)

    assert reason is not None and why in reason


async def test_third_party_styles_and_fonts_are_allowed(address_check):
    policy = RequestPolicy(SOURCE, address_check, allowed_ports=[80])

    assert await policy.verdict("http://third.test/site.css", "stylesheet", is_navigation=False) is None
    assert await policy.verdict("http://third.test/f.woff2", "font", is_navigation=False) is None


async def test_a_navigation_within_the_site_is_allowed(address_check):
    policy = RequestPolicy(SOURCE, address_check, allowed_ports=[80])

    assert await policy.verdict("http://source.test/other", "document", is_navigation=True) is None
    assert await RequestPolicy("www.x.com", AddressChecker(), [80]).verdict("http://other.com/", "document", is_navigation=True)


@pytest.mark.parametrize("source, target", [("bank.co.uk", "co.uk"), ("foo.github.io", "github.io"), ("app.x.com", "x.com")])
async def test_a_navigation_to_a_parent_domain_is_refused(source, target):
    async def public(host: str) -> str:
        return "93.184.216.34"

    policy = RequestPolicy(source, public, allowed_ports=[80])

    reason = await policy.verdict(f"http://{target}/", "document", is_navigation=True)

    assert reason is not None and "navigation away" in reason


async def test_the_reason_never_holds_a_query_string(address_check):
    policy = RequestPolicy(SOURCE, address_check, allowed_ports=[80])

    reason = await policy.verdict("http://10.0.0.5/p?token=SECRET", "xhr", is_navigation=False)

    assert reason is not None and "SECRET" not in reason and "token" not in reason


# --- in the browser ----------------------------------------------------------------------------------------------


async def test_a_private_address_from_the_page_is_aborted_and_the_render_continues(server, page):
    url = server.serve(SOURCE, "/", "<p id=a>x</p><script>window.r = fetch('http://169.254.169.254/').then(() => 'reached', () => 'refused')</script>")

    await page.goto(url)

    assert await page.evaluate("window.r") == "refused"
    assert await page.text_content("#a") == "x"


async def test_navigation_to_another_host_leaves_the_document_in_place(server, page, policy):
    server.serve("other.test", "/", "other")
    url = server.serve(SOURCE, "/", f"<p id=a>stay</p><script>setTimeout(() => location.href = 'http://other.test:{server.port}/', 50)</script>")

    await page.goto(url)
    await settle()

    assert page.url == url
    assert await page.text_content("#a") == "stay"
    assert server.hits("other.test") == []
    assert any("navigation away" in reason for reason in policy.refusals)


async def test_third_party_styles_are_loaded_and_applied(server, page):
    server.serve("third.test", "/site.css", "p { color: rgb(1, 2, 3) }", "text/css")
    url = server.serve(SOURCE, "/", f'<link rel=stylesheet href="http://third.test:{server.port}/site.css"><p id=a>x</p>')

    await page.goto(url)

    assert await page.evaluate("getComputedStyle(document.getElementById('a')).color") == "rgb(1, 2, 3)"
    assert server.hits("third.test") == ["third.test/site.css"]


async def test_websockets_and_event_streams_never_reach_the_network(server, page):
    url = server.serve(
        SOURCE,
        "/",
        f"<script>new WebSocket('ws://source.test:{server.port}/ws'); new EventSource('http://source.test:{server.port}/events')</script>",
    )

    await page.goto(url)
    await settle()

    assert server.hits(SOURCE) == [f"{SOURCE}/"]


async def test_a_popup_is_closed(server, page):
    server.serve(SOURCE, "/popup", "<p>popup</p>")
    url = server.serve(SOURCE, "/", "<a id=a target=_blank href='/popup'>open</a>")
    await page.goto(url)

    await page.click("#a")  # a user gesture, so the browser's own popup blocker does not hide the case
    await settle()

    assert len(page.context.pages) == 1


async def test_a_dialog_is_dismissed_instead_of_blocking_the_page(server, page):
    url = server.serve(SOURCE, "/", "<p>x</p>")

    await page.goto(url)

    assert await asyncio.wait_for(page.evaluate("alert('hi'), confirm('ok') === false"), 5) is True


async def test_a_service_worker_cannot_register_from_the_page_or_a_frame(server, browser, address_check):
    policy = RequestPolicy("localhost", address_check, allowed_ports=[server.port])
    context = await browser.new_context(**CONTEXT_OPTIONS)
    page = await confined_page(context, policy)
    server.serve("localhost", "/sw.js", "self.addEventListener('fetch', () => {})", "text/javascript")
    url = server.serve("localhost", "/", "<iframe id=f srcdoc='<p>x</p>'></iframe>")

    await page.goto(url)
    in_page = await page.evaluate("typeof navigator.serviceWorker")
    in_frame = await page.evaluate("typeof document.getElementById('f').contentWindow.navigator.serviceWorker")
    await context.close()

    assert (in_page, in_frame) == ("undefined", "undefined")


async def test_a_download_is_not_kept(server, page):
    server.serve(SOURCE, "/file.bin", b"payload", "application/octet-stream", **{"Content-Disposition": "attachment; filename=file.bin"})
    url = server.serve(SOURCE, "/", "<a id=a href='/file.bin'>get</a>")
    await page.goto(url)

    async with page.expect_download() as download:
        await page.click("#a")

    with pytest.raises(Exception, match="(?i)download|accept"):
        await (await download.value).path()


async def test_a_navigation_between_the_bare_domain_and_its_subdomains_is_allowed():
    async def public(host: str) -> str:
        return "93.184.216.34"

    policy = RequestPolicy("www.source.test", public, allowed_ports=[80])

    assert await policy.verdict("http://source.test/", "document", is_navigation=True) is None
    assert await policy.verdict("http://app.www.source.test/", "document", is_navigation=True) is None
    assert await policy.verdict("http://notsource.test/", "document", is_navigation=True) is not None


async def test_a_request_that_cannot_be_checked_does_not_go_out(server, browser):
    async def broken(host: str) -> str:
        if host == "third.test":
            raise RuntimeError("resolver exploded")
        return "127.0.0.1"

    policy = RequestPolicy(SOURCE, broken, allowed_ports=[server.port])
    context = await browser.new_context(**CONTEXT_OPTIONS)
    page = await confined_page(context, policy)
    server.serve("third.test", "/x", "x")
    url = server.serve(SOURCE, "/", f"<script>window.r = fetch('http://third.test:{server.port}/x').then(() => 'sent', () => 'refused')</script>")

    await page.goto(url)
    outcome = await page.evaluate("window.r")
    await context.close()

    assert outcome == "refused" and server.hits("third.test") == []


async def test_a_third_party_iframe_is_loaded_because_only_the_top_frame_must_stay(server, page):
    server.serve("third.test", "/widget", "<p>widget</p>")
    url = server.serve(SOURCE, "/", f"<iframe src='http://third.test:{server.port}/widget'></iframe>")

    await page.goto(url)
    await settle()

    assert server.hits("third.test") == ["third.test/widget"]


@pytest.mark.parametrize(
    "script",
    [
        "typeof RTCPeerConnection",
        "typeof webkitRTCPeerConnection",
        "typeof WebTransport",
        "typeof SharedWorker",  # a shared worker's own fetches do not pass through `route` at all
    ],
)
async def test_realtime_network_apis_that_the_route_cannot_see_are_gone(server, page, script):
    url = server.serve(SOURCE, "/", "<iframe id=f srcdoc='<p>x</p>'></iframe>")
    await page.goto(url)

    in_page = await page.evaluate(script)
    in_frame = await page.evaluate(f"document.getElementById('f').contentWindow.eval({script!r})")

    assert (in_page, in_frame) == ("undefined", "undefined")


async def test_a_shared_worker_cannot_reach_an_internal_host(server, page):
    server.serve("internal.test", "/secret", "SECRET")
    shared = f"new SharedWorker(URL.createObjectURL(new Blob([\"fetch('http://internal.test:{server.port}/secret')\"])))"
    url = server.serve(SOURCE, "/", f"<script>try {{ {shared} }} catch (e) {{}}</script>")

    await page.goto(url)
    await settle()

    assert server.hits("internal.test") == []
