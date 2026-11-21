"""Start the renderer: launch the pinned browser once (the start-up check), then serve until stopped.

If the browser cannot start, or later dies, the process exits non-zero so the container restarts it.
"""

import asyncio
import json
import logging
import os
import signal
import sys

from aiohttp import web
from playwright.async_api import async_playwright

from iw_renderer.confine import LAUNCH_ARGS
from iw_renderer.render import Renderer
from iw_renderer.service import create_app
from iw_renderer.settings import RenderLimits
from iw_scraper.addresses import AddressChecker

_log = logging.getLogger("iw_renderer")


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps({"level": record.levelname.lower(), "logger": record.name, "message": record.getMessage()})


async def serve() -> int:
    limits = RenderLimits.from_env()
    port = int(os.environ.get("RENDERER_PORT", "8080"))
    stopped = asyncio.Event()
    exit_code = 0

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(args=list(LAUNCH_ARGS))
        _log.info("browser started version=%s", browser.version)

        def browser_died(_: object) -> None:
            nonlocal exit_code
            if stopped.is_set():  # an intended shutdown closes the browser too
                return
            exit_code = 1
            _log.error("browser disconnected")
            stopped.set()

        browser.on("disconnected", browser_died)
        runner = web.AppRunner(create_app(Renderer(browser, AddressChecker().check, limits)), access_log=None)
        await runner.setup()
        await web.TCPSite(runner, "0.0.0.0", port).start()  # noqa: S104 (the private render network, no host port)
        _log.info("listening port=%d", port)

        loop = asyncio.get_running_loop()
        for name in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(name, stopped.set)
        await stopped.wait()
        await runner.cleanup()
    return exit_code


def main() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_JsonFormatter())
    logging.basicConfig(level=logging.INFO, handlers=[handler])
    sys.exit(asyncio.run(serve()))


if __name__ == "__main__":
    main()
