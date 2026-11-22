import asyncio
import struct
import time

import pytest

from iw_renderer.render import RenderFailed, RenderRequest, Renderer, render_viewport
from iw_renderer.settings import RenderLimits

PNG = b"\x89PNG\r\n\x1a\n"


def png_size(png: bytes) -> tuple[int, int]:
    return struct.unpack(">II", png[16:24])


def request_for(server, viewport="desktop", path="/", **extra):
    return RenderRequest(
        url=f"http://source.test:{server.port}{path}",
        source_host="source.test",
        viewport=viewport,
        headers=(("user-agent", "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36"),),
        ports=(server.port,),
        **extra,
    )


def tall(height: int) -> str:
    return f"<body style='margin:0'><div style='height:{height}px;background:linear-gradient(red,blue)'></div></body>"


async def test_a_screenshot_is_a_full_page_png_at_the_viewport_width(server, browser, address_check):
    server.serve("source.test", "/", tall(2500))

    result = await render_viewport(browser, request_for(server), address_check)

    assert result.png.startswith(PNG)
    assert png_size(result.png) == (1440, 2500)
    assert result.truncated is False


async def test_each_viewport_is_captured_at_its_own_width(server, browser, address_check):
    server.serve("source.test", "/", tall(1000))

    widths = {
        name: png_size((await render_viewport(browser, request_for(server, name), address_check)).png)[0]
        for name in ("desktop", "tablet", "mobile")
    }

    assert widths == {"desktop": 1440, "tablet": 820, "mobile": 390}


async def test_a_page_taller_than_the_cap_is_cut_and_marked_truncated(server, browser, address_check):
    server.serve("source.test", "/", tall(5000))

    result = await render_viewport(browser, request_for(server, max_page_height=3000), address_check)

    assert png_size(result.png) == (1440, 3000)
    assert result.truncated is True


async def test_a_png_over_the_byte_cap_is_shortened_until_it_fits(server, browser, address_check):
    noise = "".join(f"<div style='height:20px;background:#{(i * 7919) % 0xFFFFFF:06x}'>{i}</div>" for i in range(400))
    server.serve("source.test", "/", f"<body style='margin:0'>{noise}</body>")
    full = await render_viewport(browser, request_for(server), address_check)

    capped = await render_viewport(browser, request_for(server, max_png_bytes=len(full.png) // 2), address_check)

    assert len(capped.png) <= len(full.png) // 2
    assert capped.truncated is True
    assert png_size(capped.png)[1] < png_size(full.png)[1]


async def test_a_png_that_cannot_fit_even_one_viewport_fails_the_render(server, browser, address_check):
    server.serve("source.test", "/", tall(1000))

    with pytest.raises(RenderFailed, match="size cap"):
        await render_viewport(browser, request_for(server, max_png_bytes=100), address_check)


async def test_a_page_that_never_finishes_loading_times_out_and_leaves_no_context(server, browser, address_check):
    server.serve("source.test", "/", "<img src='/hang.png'>")
    started = time.monotonic()

    async def hang(host: str) -> str:
        await asyncio.sleep(30)
        return "127.0.0.1"

    with pytest.raises(RenderFailed, match="timed out"):
        await render_viewport(browser, request_for(server, timeout_seconds=1.5), hang)

    assert time.monotonic() - started < 6
    assert browser.contexts == []


async def test_the_whole_render_shares_one_deadline(server, browser, address_check):
    server.serve("source.test", "/", "<p>x</p><script>new Promise(() => {})</script>")
    started = time.monotonic()

    with pytest.raises(RenderFailed, match="timed out"):
        await render_viewport(browser, request_for(server, timeout_seconds=0.001), address_check)

    assert time.monotonic() - started < 6
    assert browser.contexts == []


async def test_two_renders_at_once_run_one_after_the_other(server, browser, address_check):
    server.serve("source.test", "/", "<p>x</p>")
    renderer = Renderer(browser, address_check, RenderLimits(concurrency=1))
    running, peak = 0, 0
    original = render_viewport

    async def watched(*args, **kwargs):
        nonlocal running, peak
        running += 1
        peak = max(peak, running)
        try:
            return await original(*args, **kwargs)
        finally:
            running -= 1

    renderer._render = watched

    results = await asyncio.gather(renderer.render(request_for(server)), renderer.render(request_for(server, "mobile")))

    assert peak == 1 and all(r.png.startswith(PNG) for r in results)


def test_limits_come_from_the_environment_with_the_documented_defaults(monkeypatch):
    for name in ("RENDER_TIMEOUT_SECONDS", "RENDER_MAX_PAGE_HEIGHT", "RENDER_MAX_PNG_BYTES", "RENDER_CONCURRENCY"):
        monkeypatch.delenv(name, raising=False)
    defaults = RenderLimits.from_env()
    monkeypatch.setenv("RENDER_MAX_PAGE_HEIGHT", "500")
    monkeypatch.setenv("RENDER_CONCURRENCY", "2")
    custom = RenderLimits.from_env()

    assert (defaults.timeout_seconds, defaults.max_page_height, defaults.max_png_bytes, defaults.concurrency) == (
        90.0,
        12000,
        8_000_000,
        1,
    )
    assert (custom.max_page_height, custom.concurrency) == (500, 2)


def test_a_limit_that_is_not_a_positive_number_is_refused(monkeypatch):
    monkeypatch.setenv("RENDER_CONCURRENCY", "0")

    with pytest.raises(ValueError, match="RENDER_CONCURRENCY"):
        RenderLimits.from_env()


async def test_a_png_exactly_at_the_byte_cap_is_kept_whole(server, browser, address_check):
    server.serve("source.test", "/", tall(1500))
    whole = await render_viewport(browser, request_for(server), address_check)

    again = await render_viewport(browser, request_for(server, max_png_bytes=len(whole.png)), address_check)

    assert again.truncated is False and png_size(again.png) == png_size(whole.png)


async def test_a_page_exactly_as_tall_as_the_cap_is_not_truncated(server, browser, address_check):
    server.serve("source.test", "/", tall(3000))

    result = await render_viewport(browser, request_for(server, max_page_height=3000), address_check)

    assert result.truncated is False and png_size(result.png)[1] == 3000


async def test_the_renderers_own_limits_cap_what_a_request_asks_for(server, browser, address_check):
    server.serve("source.test", "/", tall(5000))
    renderer = Renderer(browser, address_check, RenderLimits(max_page_height=2000, timeout_seconds=60, max_png_bytes=8_000_000))

    result = await renderer.render(request_for(server, max_page_height=12000))

    assert png_size(result.png)[1] == 2000 and result.truncated is True


async def test_the_renderers_own_timeout_caps_what_a_request_asks_for(server, browser, address_check):
    server.serve("source.test", "/", "<p>x</p>")
    renderer = Renderer(browser, address_check, RenderLimits(timeout_seconds=0.001))

    with pytest.raises(RenderFailed, match="timed out"):
        await renderer.render(request_for(server, timeout_seconds=60))


async def test_the_renderers_own_png_cap_applies_to_a_request_that_asks_for_more(server, browser, address_check):
    server.serve("source.test", "/", tall(1000))
    renderer = Renderer(browser, address_check, RenderLimits(max_png_bytes=100))

    with pytest.raises(RenderFailed, match="size cap"):
        await renderer.render(request_for(server, max_png_bytes=8_000_000))


def test_an_empty_setting_means_the_default(monkeypatch):
    monkeypatch.setenv("RENDER_CONCURRENCY", "")

    assert RenderLimits.from_env().concurrency == 1


async def test_a_page_that_hangs_after_loading_is_cut_off_by_the_deadline(server, browser, address_check):
    server.serve("source.test", "/", "<p>x</p><script>addEventListener('load', () => setTimeout(() => { for (;;) {} }, 0))</script>")
    started = time.monotonic()

    with pytest.raises(RenderFailed, match="timed out"):
        await asyncio.wait_for(render_viewport(browser, request_for(server, timeout_seconds=4), address_check), 30)

    assert time.monotonic() - started < 20
    assert browser.contexts == []
