import asyncio
from urllib.parse import parse_qs, urlsplit

import pytest

from iw_renderer.render import RenderBlocked, RenderFailed, RenderRequest, playwright_proxy, render_viewport
from iw_renderer.viewports import VIEWPORTS

CHROME_146 = (
    ("sec-ch-ua", '"Chromium";v="146", "Not-A.Brand";v="24", "Google Chrome";v="146"'),
    ("sec-ch-ua-mobile", "?0"),
    ("sec-ch-ua-platform", '"Windows"'),
    ("user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"),
    ("accept-language", "pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7"),
)
ANDROID_146 = (
    ("sec-ch-ua", '"Chromium";v="146", "Not-A.Brand";v="24", "Google Chrome";v="146"'),
    ("sec-ch-ua-mobile", "?1"),
    ("sec-ch-ua-platform", '"Android"'),
    ("user-agent", "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Mobile Safari/537.36"),
    ("accept-language", "pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7"),
)
PROBE = "<script>fetch('/probe?w=' + document.documentElement.clientWidth + '&coarse=' + matchMedia('(pointer: coarse)').matches)</script>"


def request_for(server, viewport="desktop", headers=CHROME_146, path="/", **extra):
    return RenderRequest(
        url=f"http://source.test:{server.port}{path}",
        source_host="source.test",
        viewport=viewport,
        headers=headers,
        ports=(server.port,),
        **extra,
    )


async def probe(server) -> dict[str, str]:
    await asyncio.sleep(0.3)
    paths = [p for h, p, _ in server.requests if p.startswith("/probe")]
    return {k: v[0] for k, v in parse_qs(urlsplit(paths[-1]).query).items()}


def sent_headers(server, path="/") -> dict[str, str]:
    return {k.lower(): v for k, v in next(h for _, p, h in server.requests if p == path).items()}


async def test_the_desktop_context_sends_the_identity_with_the_browsers_own_major(server, browser, address_check):
    server.serve("source.test", "/", "<p>x</p>")

    await render_viewport(browser, request_for(server), address_check)

    sent = sent_headers(server)
    major = browser.version.split(".")[0]
    assert f"Chrome/{major}.0.0.0 Safari/537.36" in sent["user-agent"]
    assert sent["accept-language"] == "pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7"


async def test_the_mobile_context_is_a_touch_phone_that_honours_the_layout_viewport(server, browser, address_check):
    server.serve("source.test", "/", PROBE)

    await render_viewport(browser, request_for(server, "mobile", ANDROID_146), address_check)

    assert "Android" in sent_headers(server)["user-agent"]
    # without a viewport meta tag a real phone lays the page out 980 px wide; a resized desktop page would say 390
    assert (await probe(server)) == {"w": "980", "coarse": "true"}


async def test_a_page_with_a_viewport_meta_tag_is_laid_out_at_the_device_width(server, browser, address_check):
    server.serve("source.test", "/", '<meta name="viewport" content="width=device-width">' + PROBE)

    await render_viewport(browser, request_for(server, "mobile", ANDROID_146), address_check)

    assert (await probe(server))["w"] == "390"


async def test_the_desktop_context_is_1440_wide_without_touch(server, browser, address_check):
    server.serve("source.test", "/", PROBE)

    await render_viewport(browser, request_for(server), address_check)

    assert (await probe(server)) == {"w": "1440", "coarse": "false"}


async def test_the_tablet_context_is_820_wide_with_touch(server, browser, address_check):
    server.serve("source.test", "/", PROBE)

    await render_viewport(browser, request_for(server, "tablet"), address_check)

    assert (await probe(server)) == {"w": "820", "coarse": "true"}


async def test_each_render_is_one_navigation_in_a_fresh_context(server, browser, address_check):
    server.serve("source.test", "/", "<p>x</p>", **{"Set-Cookie": "seen=1"})

    await render_viewport(browser, request_for(server), address_check)
    await render_viewport(browser, request_for(server, "mobile", ANDROID_146), address_check)

    pages = [h for host, p, h in server.requests if p == "/"]
    assert len(pages) == 2
    assert "Cookie" not in pages[1]


@pytest.mark.parametrize("status, extra, retry_after", [(403, {}, None), (429, {"Retry-After": "120"}, "120")])
async def test_a_block_status_is_reported_with_its_retry_after(server, browser, address_check, status, extra, retry_after):
    server.routes[("source.test", "/")] = (status, {**extra}, b"no")

    with pytest.raises(RenderBlocked) as blocked:
        await render_viewport(browser, request_for(server), address_check)

    assert f"HTTP {status}" in blocked.value.detail
    assert blocked.value.retry_after == retry_after


async def test_a_challenge_page_marker_is_a_block_even_on_a_200(server, browser, address_check):
    server.serve("source.test", "/", "<div class='cf-turnstile'></div>")

    with pytest.raises(RenderBlocked, match="marker"):
        await render_viewport(browser, request_for(server), address_check)


async def test_a_large_page_that_merely_embeds_a_captcha_widget_is_not_a_block(server, browser, address_check):
    server.serve("source.test", "/", "<div class='g-recaptcha'></div>" + "<p>filler</p>" * 3000)

    await render_viewport(browser, request_for(server), address_check)


@pytest.mark.parametrize("status", [400, 404, 500])
async def test_other_error_statuses_fail_the_render_without_blocking(server, browser, address_check, status):
    server.routes[("source.test", "/")] = (status, {}, b"oops")

    with pytest.raises(RenderFailed, match=f"HTTP {status}") as failed:
        await render_viewport(browser, request_for(server), address_check)

    assert not isinstance(failed.value, RenderBlocked)


async def test_an_identity_that_is_not_chrome_is_refused_before_any_navigation(server, browser, address_check):
    server.serve("source.test", "/", "<p>x</p>")
    firefox = (("user-agent", "Mozilla/5.0 (X11; Linux x86_64; rv:147.0) Gecko/20100101 Firefox/147.0"),)

    with pytest.raises(RenderFailed, match="Chrome"):
        await render_viewport(browser, request_for(server, headers=firefox), address_check)

    assert server.requests == []


async def test_a_redirect_to_another_site_fails_the_render(server, browser, address_check):
    server.routes[("source.test", "/")] = (302, {"Location": f"http://other.test:{server.port}/"}, b"")
    server.serve("other.test", "/", "elsewhere")

    with pytest.raises(RenderFailed, match="navigation away"):
        await render_viewport(browser, request_for(server), address_check)


async def test_a_redirect_within_the_site_is_followed(server, browser, address_check):
    server.routes[("source.test", "/old")] = (301, {"Location": "/new"}, b"")
    server.serve("source.test", "/new", "<p>x</p>")

    result = await render_viewport(browser, request_for(server, path="/old"), address_check)

    assert result.final_url.endswith("/new")


async def test_a_proxy_failure_never_shows_the_proxy_credentials(server, browser, address_check):
    server.serve("source.test", "/", "<p>x</p>")

    with pytest.raises(RenderFailed) as failed:
        await render_viewport(browser, request_for(server, proxy="http://user:SECRETPW@127.0.0.1:1"), address_check)

    assert "SECRETPW" not in str(failed.value) and "127.0.0.1:1" not in str(failed.value)


def test_a_proxy_url_is_split_into_the_parts_playwright_wants():
    assert playwright_proxy("http://user:pw@proxy.test:8080") == {
        "server": "http://proxy.test:8080",
        "username": "user",
        "password": "pw",
    }
    assert playwright_proxy("http://proxy.test:8080") == {"server": "http://proxy.test:8080"}


def test_the_viewport_table_follows_the_contract():
    assert {n: (v.width, v.height, v.is_mobile, v.has_touch) for n, v in VIEWPORTS.items()} == {
        "desktop": (1440, 900, False, False),
        "tablet": (820, 1180, False, True),
        "mobile": (390, 844, True, True),
    }


async def test_every_identity_header_goes_out_exactly_once(server, browser, address_check):
    server.serve("source.test", "/", "<p>x</p>")

    await render_viewport(browser, request_for(server, "mobile", ANDROID_146), address_check)

    lines = server.raw_headers["/"]
    major = browser.version.split(".")[0]
    assert [v for n, v in lines if n == "accept-language"] == ["pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7"]
    assert [v for n, v in lines if n == "user-agent"] == [
        f"Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{major}.0.0.0 Mobile Safari/537.36"
    ]


@pytest.mark.parametrize("headers, platform, mobile", [(CHROME_146, "Windows", False), (ANDROID_146, "Android", True)])
async def test_the_page_sees_the_client_hints_of_the_identity(server, browser, address_check, headers, platform, mobile):
    server.serve(
        "localhost",
        "/",
        "<script>const d = navigator.userAgentData; "
        "fetch('/probe?p=' + d.platform + '&m=' + d.mobile + '&b=' + d.brands.map(b => b.brand + b.version).join('|'))</script>",
    )
    request = RenderRequest(
        url=f"http://localhost:{server.port}/", source_host="localhost", viewport="mobile" if mobile else "desktop",
        headers=headers, ports=(server.port,),
    )

    await render_viewport(browser, request, address_check)

    major = browser.version.split(".")[0]
    assert await probe(server) == {"p": platform, "m": str(mobile).lower(), "b": f"Chromium{major}|Not-A.Brand24|Google Chrome{major}"}


async def test_the_page_sees_a_polish_browser(server, browser, address_check):
    server.serve("source.test", "/", "<script>fetch('/probe?lang=' + navigator.language)</script>")

    await render_viewport(browser, request_for(server), address_check)

    assert (await probe(server)) == {"lang": "pl-PL"}


async def test_a_request_for_another_host_than_the_source_is_refused(server, browser, address_check):
    server.serve("other.test", "/", "elsewhere")
    elsewhere = RenderRequest(
        url=f"http://other.test:{server.port}/", source_host="source.test", viewport="desktop", headers=CHROME_146, ports=(server.port,)
    )

    with pytest.raises(RenderFailed, match="navigation away"):
        await render_viewport(browser, elsewhere, address_check)

    assert server.hits("other.test") == []
