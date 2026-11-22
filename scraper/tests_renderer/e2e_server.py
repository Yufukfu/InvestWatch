"""Test-only server for the scraper's render end-to-end check (`scraper/tests/test_e2e_render.py`).

It runs the real renderer service on :8080 and serves the demo pages (`tests/fixtures/demo`) on :8081 under
`xtb.demo.test` and `mbank.demo.test`. The only difference from production is the address check: the demo hosts are
local, which the real check refuses. This file is not part of the runtime image.
"""

import asyncio
import os
from pathlib import Path

from aiohttp import web
from playwright.async_api import async_playwright

from iw_renderer.confine import LAUNCH_ARGS
from iw_renderer.render import Renderer
from iw_renderer.service import create_app
from iw_renderer.settings import RenderLimits

PAGES = {"xtb.demo.test": "xtb-ike.html", "mbank.demo.test": "mbank-ike.html"}
FIXTURES = Path(os.environ.get("DEMO_PAGES", "/app/scraper/tests/fixtures/demo"))


async def page(request: web.Request) -> web.Response:
    name = PAGES.get(request.host.split(":")[0])
    if name is None:
        return web.Response(status=404)
    return web.Response(body=(FIXTURES / name).read_bytes(), content_type="text/html", charset="utf-8")


async def robots(request: web.Request) -> web.Response:
    return web.Response(status=404)


async def allow_all(host: str) -> None:
    return None


async def main() -> None:
    site = web.Application()
    site.add_routes([web.get("/", page), web.get("/robots.txt", robots)])
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(args=list(LAUNCH_ARGS))
        runners = [
            web.AppRunner(site, access_log=None),
            web.AppRunner(create_app(Renderer(browser, allow_all, RenderLimits.from_env())), access_log=None),
        ]
        for runner, port in zip(runners, (8081, 8080)):
            await runner.setup()
            await web.TCPSite(runner, "0.0.0.0", port).start()
        await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
